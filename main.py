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

# Database imports
from database import SessionLocal, SessionModel, EvaluationModel

# Groq client
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


# ---------------- HELPERS ----------------

def parse_json_response(text: str):
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    return json.loads(cleaned)


# ---------------- HOME ----------------

@app.get("/")
def home():
    return FileResponse("index.html")


# ---------------- GENERATE QUESTIONS ----------------

@app.post("/generate-questions")
def generate_questions(req: RoleRequest):
    try:
        print("Step 1: role received:", req.role)

        prompt = f"""
Generate exactly 5 interview questions for a {req.role} role.
Return only questions, one per line.
"""

        print("Step 2: calling Groq...")

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        if not response.choices:
            raise Exception("Empty response from Groq")

        text = response.choices[0].message.content.strip()

        print("Step 3: raw response:", text)

        questions = [
            re.sub(r"^\d+[\.\)]\s*", "", q).strip()
            for q in text.split("\n")
            if q.strip()
        ][:5]

        print("Step 4: parsed questions:", questions)

        # Save session
        db = SessionLocal()
        session_id = str(db.query(SessionModel).count() + 1)

        new_session = SessionModel(
            session_id=session_id,
            role=req.role
        )

        db.add(new_session)
        db.commit()
        db.close()

        return {
            "session_id": session_id,
            "questions": questions
        }

    except Exception as e:
        print("ERROR generate-questions:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- EVALUATE ANSWER ----------------

@app.post("/evaluate")
def evaluate(req: AnswerRequest):
    try:
        print("Step 1: evaluating:", req.session_id)

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

        print("Step 2: calling Groq...")

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
        )

        if not response.choices:
            raise Exception("Empty evaluation response")

        text = response.choices[0].message.content.strip()

        print("Step 3 raw:", text)

        try:
            result = parse_json_response(text)
        except:
            result = {
                "score": 5,
                "feedback": text,
                "weakness": "parsing error"
            }

        weakness = result.get("weakness", "none")

        new_eval = EvaluationModel(
            session_id=req.session_id,
            question=req.question,
            score=result["score"],
            feedback=result["feedback"],
            weakness=None if weakness.lower() == "none" else weakness
        )

        db.add(new_eval)
        db.commit()
        db.close()

        return result

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR evaluate:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))


# ---------------- REPORT ----------------

@app.get("/get-report/{session_id}")
def report(session_id: str):
    try:
        print("Step 1: report:", session_id)

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

        avg_score = round(
            sum(e.score for e in evaluations) / len(evaluations), 1
        )

        weaknesses = [e.weakness for e in evaluations if e.weakness]

        prompt = f"""
Role: {session.role}
Weaknesses: {weaknesses}
Average score: {avg_score}

Give 2-3 sentence hiring recommendation.
"""

        print("Step 2: calling Groq...")

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
        )

        recommendation = response.choices[0].message.content.strip()

        return {
            "session_id": session_id,
            "role": session.role,
            "average_score": avg_score,
            "weakness_summary": list(set(weaknesses)),
            "recommendation": recommendation
        }

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR report:", repr(e))
        raise HTTPException(status_code=500, detail=str(e))