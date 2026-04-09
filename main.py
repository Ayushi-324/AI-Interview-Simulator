import os
import json
import re
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ---------------- DATABASE SETUP ----------------
DATABASE_URL = "sqlite:////tmp/interview.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class SessionModel(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    role = Column(String)

class EvaluationModel(Base):
    __tablename__ = "evaluations"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String)
    question = Column(String)
    score = Column(Integer)
    feedback = Column(String)
    weakness = Column(String)

Base.metadata.create_all(bind=engine)

# ---------------- INIT ----------------
API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

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

# ---------------- HELPER: TALK TO GROQ ----------------
async def ask_groq(prompt, temperature=0.7):
    headers = {
        "Authorization": f"Bearer {API_KEY.strip()}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(GROQ_URL, headers=headers, json=data, timeout=30.0)
        if response.status_code != 200:
            print(f"Groq API Error: {response.text}")
            raise Exception(f"Groq API Error: {response.status_code}")
        result = response.json()
        return result['choices'][0]['message']['content'].strip()

# ---------------- ROUTES ----------------

@app.get("/", response_class=HTMLResponse)
def home():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<h1>index.html not found! Error: {str(e)}</h1>"

@app.post("/generate-questions")
async def generate_questions(req: RoleRequest):
    try:
        print(f"🚀 Role received: {req.role}")
        prompt = f"Generate exactly 5 interview questions for a {req.role} role. Return only the questions, one per line, no numbers."
        text = await ask_groq(prompt)
        
        # Split by lines and clean up any weird numbering the AI might add
        questions = [re.sub(r"^\d+[\.\)]\s*", "", q).strip() for q in text.split("\n") if q.strip()][:5]

        db = SessionLocal()
        session_id = str(db.query(SessionModel).count() + 1001) # Start at 1001 for looks
        db.add(SessionModel(session_id=session_id, role=req.role))
        db.commit()
        db.close()

        return {"session_id": session_id, "questions": questions}
    except Exception as e:
        print(f"❌ Error in /generate-questions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate")
async def evaluate(req: AnswerRequest):
    try:
        prompt = (
            f"Question: {req.question}\n"
            f"Answer: {req.answer}\n\n"
            "Evaluate this answer. Return ONLY a JSON object with these keys: "
            "'score' (0-10), 'feedback' (1-2 sentences), 'weakness' (1 word or 'none')."
        )
        text = await ask_groq(prompt, temperature=0.5)
        
        # Robust JSON Extraction
        try:
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                result = json.loads(match.group(0))
            else:
                result = {"score": 5, "feedback": "Could not parse AI response.", "weakness": "format"}
        except:
            result = {"score": 5, "feedback": "Answer analyzed but JSON was messy.", "weakness": "format"}

        # Force correct keys so Frontend doesn't get 'undefined'
        final_data = {
            "score": result.get("score", 5),
            "feedback": result.get("feedback", "Good effort on the response."),
            "weakness": result.get("weakness", "none")
        }

        db = SessionLocal()
        db.add(EvaluationModel(
            session_id=req.session_id,
            question=req.question,
            score=final_data["score"],
            feedback=final_data["feedback"],
            weakness=final_data["weakness"]
        ))
        db.commit()
        db.close()
        
        return final_data
        
    except Exception as e:
        print(f"❌ Error in /evaluate: {str(e)}")
        return {"score": 0, "feedback": "System error during evaluation.", "weakness": "system"}

@app.get("/get-report/{session_id}")
async def report(session_id: str):
    try:
        db = SessionLocal()
        session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
        evals = db.query(EvaluationModel).filter(EvaluationModel.session_id == session_id).all()
        db.close()
        
        if not session or not evals:
            return {"error": "Session data not found."}

        avg = round(sum(e.score for e in evals) / len(evals), 1)
        weaknesses = list(set([e.weakness for e in evals if e.weakness and e.weakness.lower() != 'none']))
        
        tip_prompt = f"Role: {session.role}, Average Score: {avg}/10. Give a 1-sentence career advice tip."
        recommendation = await ask_groq(tip_prompt)

        return {
            "session_id": session_id,
            "role": session.role,
            "average_score": avg,
            "weakness_summary": weaknesses if weaknesses else ["None identified"],
            "recommendation": recommendation
        }
    except Exception as e:
        print(f"❌ Error in /get-report: {str(e)}")
        return {"error": "Could not generate report."}