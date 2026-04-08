from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from groq import Groq

import os
import json
import re

# DB
from database import SessionLocal, SessionModel, EvaluationModel

# ---------------- INIT ----------------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


# ---------------- REQUEST MODELS ----------------

class RoleRequest(BaseModel):
    role: str


class AnswerRequest(BaseModel):
    session_id: str
    question: str
    answer: str


# ---------------- UTIL ----------------

def safe_json_parse(text: str):
    """
    Extract JSON even if LLM returns extra text.
    """
    try:
        return json.loads(text)
    except:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass

    return None


# ---------------- ROUTES ----------------

@app.get("/")
def health():
    return {"status": "ok"}


# ---------------- GENERATE QUESTIONS ----------------

@app.post("/generate-questions")
def generate_questions(req: RoleRequest):
    try:
        if not req.role:
            raise HTTPException(status_code=400, detail="Role is required")

        prompt = f"""
You are a senior technical interviewer.

Generate exactly 5 interview questions for a {req.role} role.

Rules:
- Only questions
- No numbering
- One per line
"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        text = response.choices[0].message.content.strip()

        if not text:
            raise HTTPException(status_code=500, detail="Empty model response")

        questions = [
            re.sub(r"^\d+[\.\)]\s*", "", q).strip()
            for q in text.split("\n")
            if q.strip()
        ][:5]

        # DB session create
        db = SessionLocal()
        session_id = str(db.query(SessionModel).count() + 1)

        session = SessionModel(
            session_id=session_id,
            role=req.role
        )

        db.add(session)
        db.commit()
        db.close()

        return {
            "session_id": session_id,
            "questions": questions
        }

    except Exception as e:
        print("ERROR generate-questions:", repr(e))
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
            temperature=0.5
        )

        text = response.choices[0].message.content.strip()

        result = safe_json_parse(text)

        if not result:
            result = {
                "score": 5,
                "feedback": "Failed to parse model response",
                "weakness": "parsing error"
            }

        new_eval = EvaluationModel(
            session_id=req.session_id,
            question=req.question,
            score=result.get("score", 5),
            feedback=result.get("feedback", ""),
            weakness=result.get("weakness", "none")
        )

        db.add(new_eval)
        db.commit()
        db.close()

        return result

    except Exception as e:
        print("ERROR evaluate:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- REPORT ----------------

@app.get("/get-report/{session_id}")
def get_report(session_id: str):
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
                "recommendation": "No evaluations yet"
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
            temperature=0.6
        )

        recommendation = response.choices[0].message.content.strip()

        return {
            "session_id": session_id,
            "role": session.role,
            "average_score": avg,
            "weakness_summary": weaknesses,
            "recommendation": recommendation
        }

    except Exception as e:
        print("ERROR report:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))