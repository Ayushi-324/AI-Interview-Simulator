from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai
import json
import re
import os

# Database imports
from database import SessionLocal, SessionModel, EvaluationModel

# API setup
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")

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


@app.post("/generate-questions")
def generate_questions(req: RoleRequest):
    try:
        print("Step 1: received role:", req.role)
        prompt = f"Generate exactly 5 interview questions for a {req.role} role. Return only the questions as a plain numbered list."
        print("Step 2: calling Gemini...")
        response = model.generate_content(prompt)
        print("Step 3: Gemini response:", response.text)

        raw_lines = response.text.strip().split("\n")
        questions = [
            re.sub(r"^\d+[\.\)]\s*", "", line).strip()
            for line in raw_lines
            if line.strip()
        ]
        print("Step 4: questions parsed:", questions)

        # Save session to database
        db = SessionLocal()
        session_id = str(db.query(SessionModel).count() + 1)
        new_session = SessionModel(session_id=session_id, role=req.role)
        db.add(new_session)
        db.commit()
        db.close()

        return {"session_id": session_id, "questions": questions}

    except Exception as e:
        print("ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/evaluate")
def evaluate(req: AnswerRequest):
    try:
        print("Step 1: evaluating session:", req.session_id)

        # Check session exists in database
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
            "weakness": "<short 3-5 word phrase describing the main gap, or 'none' if strong>"
        }}
        Return only the JSON object, no explanation.
        """

        print("Step 2: calling Gemini...")
        response = model.generate_content(prompt)
        print("Step 3: Gemini response:", response.text)

        result = parse_json_response(response.text)
        print("Step 4: parsed result:", result)

        # Save evaluation to database
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
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get-report/{session_id}")
def report(session_id: str):
    try:
        print("Step 1: generating report for session:", session_id)

        db = SessionLocal()

        # Check session exists
        session = db.query(SessionModel).filter(
            SessionModel.session_id == session_id
        ).first()

        if not session:
            db.close()
            raise HTTPException(status_code=404, detail="Session not found")

        # Get all evaluations for this session
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
        A candidate interviewed for a {session.role} role.
        Their identified weaknesses were: {weaknesses if weaknesses else ["none"]}.
        Their average score was {avg_score}/10.

        Write a 2-3 sentence hiring recommendation summary.
        Be direct and constructive.
        """

        print("Step 2: calling Gemini for synthesis...")
        synthesis = model.generate_content(synthesis_prompt)
        print("Step 3: synthesis done")

        return {
            "session_id": session_id,
            "role": session.role,
            "average_score": avg_score,
            "weakness_summary": list(set(weaknesses)),
            "recommendation": synthesis.text.strip()
        }

    except HTTPException:
        raise
    except Exception as e:
        print("ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))