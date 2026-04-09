import os
import json
import re
import httpx # We use this instead for better stability
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
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(GROQ_URL, headers=headers, json=data, timeout=20.0)
        if response.status_code != 200:
            raise Exception(f"Groq API Error: {response.text}")
        result = response.json()
        return result['choices'][0]['message']['content'].strip()

# ---------------- ROUTES ----------------

@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/generate-questions")
async def generate_questions(req: RoleRequest):
    try:
        prompt = f"Generate 5 interview questions for a {req.role} role. Return only questions, one per line."
        text = await ask_groq(prompt)
        
        questions = [re.sub(r"^\d+[\.\)]\s*", "", q).strip() for q in text.split("\n") if q.strip()][:5]

        db = SessionLocal()
        session_id = str(db.query(SessionModel).count() + 1)
        db.add(SessionModel(session_id=session_id, role=req.role))
        db.commit()
        db.close()

        return {"session_id": session_id, "questions": questions}
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate")
async def evaluate(req: AnswerRequest):
    try:
        prompt = f"Question: {req.question}\nAnswer: {req.answer}\nReturn JSON: {{'score': 0-10, 'feedback': 'text', 'weakness': 'text'}}"
        text = await ask_groq(prompt, temperature=0.5)
        
        # Simple JSON extraction
        match = re.search(r"\{.*\}", text, re.DOTALL)
        result = json.loads(match.group(0)) if match else {"score": 5, "feedback": "Format error", "weakness": "none"}

        db = SessionLocal()
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
        print(f"❌ ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-report/{session_id}")
async def report(session_id: str):
    db = SessionLocal()
    session = db.query(SessionModel).filter(SessionModel.session_id == session_id).first()
    evals = db.query(EvaluationModel).filter(EvaluationModel.session_id == session_id).all()
    db.close()
    
    if not session: return {"error": "Not found"}

    avg = round(sum(e.score for e in evals) / len(evals), 1) if evals else 0
    tip = await ask_groq(f"Role: {session.role}, Score: {avg}. 1-sentence tip.")

    return {
        "session_id": session_id,
        "role": session.role,
        "average_score": avg,
        "recommendation": tip
    }