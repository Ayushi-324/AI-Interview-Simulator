from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq

import json
import re
import os

from database import SessionLocal, SessionModel, EvaluationModel

# ---------------- INIT ----------------

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- MODELS ----------------

class RoleRequest(BaseModel):
    role: str

class AnswerRequest(BaseModel):
    session_id: str
    question: str
    answer: str

# ---------------- SAFE PARSER ----------------

def parse_json_response(text: str):
    try:
        cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
        return json.loads(cleaned)
    except:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass

    return {
        "score": 5,
        "feedback": "Auto fallback due to invalid model output",
        "weakness": "format issue"
    }

# ---------------- HOME ----------------

@app.get("/")
def home():
    return {"status": "running"}

# ---------------- GENERATE QUESTIONS ----------------

@app.post("/generate-questions")
def generate_questions(req: RoleRequest):
    try:
        prompt = f"""
Generate exactly 5 interview questions for a {req.role} role.
Return only questions, one per line.
"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        text = response.choices[0].message.content.strip()

        questions = [
            re.sub(r"^\d+[\.\)]\s*", "", q).strip()
            for q in text.split("\n")
            if q.strip()
        ][:5]

        db = SessionLocal()
        session_id = str(db.query(SessionModel).count() + 1)

        db.add(SessionModel(session_id=session_id, role=req.role))
        db.commit()
        db.close()

        return {
            "session_id": session_id,
            "questions": questions
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------- EVALUATE ----------------

@app.post("/evaluate")
def evaluate(req: AnswerRequest):
    try:
        db = SessionLocal()

        session = db.query(SessionModel).filter(
            SessionModel.session_id == req.session_id
        ).first()

        if not session:
            db.close()
            raise HTTPException(status_code=404, detail="Session not found")

        prompt = f"""
You are a strict technical interviewer.

Question: {req.question}
Answer: {req.answer}

Return ONLY valid JSON:
{{
  "score": 0-10,
  "feedback": "2-3 lines",
  "weakness": "short phrase"
}}
"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )

        text = response.choices[0].message.content.strip()
        result = parse_json_response(text)

        db.add(EvaluationModel(
            session_id=req.session_id,
            question=req.question,
            score=result.get("score", 5),
            feedback=result.get("feedback", ""),
            weakness=result.get("weakness", "none")
        ))

        db.commit()
        db.close()

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------- REPORT ----------------

@app.get("/get-report/{session_id}")
def report(session_id: str):
    try:
        db = SessionLocal()

        session = db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).first()

        if not session:
            db.close()
            raise HTTPException(status_code=404, detail="Session not found")

        evaluations = db.query(EvaluationModel).filter(
            EvaluationModel.session_id == session_id
        ).all()

        db.close()

        if not evaluations:
            return {
                "session_id": session_id,
                "role": session.role,
                "average_score": None,
                "weakness_summary": [],
                "recommendation": "No evaluations yet."
            }

        avg = round(sum(e.score for e in evaluations) / len(evaluations), 1)
        weaknesses = list(set([e.weakness for e in evaluations if e.weakness]))

        prompt = f"""
Role: {session.role}
Average score: {avg}
Weaknesses: {weaknesses}

Give a 2-3 sentence hiring recommendation.
"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
        )

        return {
            "session_id": session_id,
            "role": session.role,
            "average_score": avg,
            "weakness_summary": weaknesses,
            "recommendation": response.choices[0].message.content.strip()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))