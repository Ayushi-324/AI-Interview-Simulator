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

# Groq setup
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class RoleRequest(BaseModel):
    role: str

class AnswerRequest(BaseModel):
    session_id: str
    question: str
    answer: str

def parse_json_response(text: str) -> dict:
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    return json.loads(cleaned)

@app.get("/")
def read_index():
    return FileResponse("index.html")

# -------------------------------
# GENERATE QUESTIONS
# -------------------------------
@app.post("/generate-questions")
def generate_questions(req: RoleRequest):
    try:
        print("Step 1: received role:", req.role)

        prompt = f"""
        Generate exactly 5 interview questions for a {req.role} role.
        Return only the questions as a plain numbered list.
        """

        print("Step 2: calling Groq...")

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.choices[0].message.content
        print("Step 3: response:", text)

        if not text:
            return {"session_id": None, "questions": ["Error generating questions"]}

        raw_lines = text.strip().split("\n")

        questions = [
            re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            for line in raw_lines if line.strip()
        ]

        print("Step 4: parsed questions:", questions)

        # Save session
        db = SessionLocal()
        session_id = str(db.query(SessionModel).count() + 1)
        new_session = SessionModel(session_id=session_id, role=req.role)
        db.add(new_session)
        db.commit()
        db.close()

        return {"session_id": session_id, "questions": questions[:5]}

    except Exception as e:
        print("ERROR:", str(e))
        return {"session_id": None, "questions": ["Server error"]}

# -------------------------------
# EVALUATE ANSWER
# -------------------------------
@app.post("/evaluate")
def evaluate(req: AnswerRequest):
    try:
        print("Step 1: evaluating session:", req.session_id)

        db = SessionLocal()
        session = db.query(SessionModel).filter(
            SessionModel.session_id == req.session_id
        ).first()

        if not session:
            db.close()
            raise HTTPException(status_code=404, detail="Session not found")

        prompt = f"""
        You are a technical interviewer. Evaluate the following answer.

        Question: {req.question}
        Answer: {req.answer}

        Return a JSON object with exactly these fields:
        {{
            "score": <integer from 1 to 10>,
            "feedback": "<2-3 sentence constructive feedback>",
            "weakness": "<short 3-5 word phrase or 'none'>"
        }}
        Return only JSON.
        """

        print("Step 2: calling Groq...")

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}]
        )

        text = response.choices[0].message.content
        print("Step 3: response:", text)

        try:
            result = parse_json_response(text)
        except:
            result = {
                "score": 5,
                "feedback": "Could not parse response",
                "weakness": "unclear"
            }

        print("Step 4: parsed result:", result)

        weakness = result.get("weakness", "none")

        new_eval = EvaluationModel(
            session_id=req.session_id,
            question=req.question,
            score=result["score"],
            feedback=result["feedback"],
            weakness=weakness if weakness.lower() != "none" else None
        )

        db.add(new_eval)
        db.commit()
        db.close()

        return result

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR:", str(e))
        return {"score": 0, "feedback": "Server error", "weakness": "error"}

# -------------------------------
# REPORT GENERATION
# -------------------------------
@app.get("/get-report/{session_id}")
def report(session_id: str):
    try:
        print("Step 1: generating report:", session_id)

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
                "recommendation": "No answers evaluated yet."
            }

        avg_score = round(sum(e.score for e in evaluations) / len(evaluations), 1)
        weaknesses = [e.weakness for e in evaluations if e.weakness]

        synthesis_prompt = f"""
        Candidate role: {session.role}
        Weaknesses: {weaknesses if weaknesses else ["none"]}
        Average score: {avg_score}/10

        Write a short hiring recommendation (2-3 sentences).
        """

        print("Step 2: calling Groq...")

        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": synthesis_prompt}]
        )

        recommendation = response.choices[0].message.content

        return {
            "session_id": session_id,
            "role": session.role,
            "average_score": avg_score,
            "weakness_summary": list(set(weaknesses)),
            "recommendation": recommendation.strip()
        }

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR:", str(e))
        return {
            "session_id": session_id,
            "role": None,
            "average_score": None,
            "weakness_summary": [],
            "recommendation": "Error generating report"
        }