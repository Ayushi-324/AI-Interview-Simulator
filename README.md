# 🎯 AI Interview Simulator

An AI-powered interview preparation tool that generates role-specific interview questions, evaluates your answers in real-time, and provides a detailed performance report.

## 🚀 Live Demo
[https://ai-interview-simulator-569n.onrender.com](https://ai-interview-simulator-569n.onrender.com)

## 💡 Features
- Generate 5 tailored interview questions for any job role
- Real-time answer evaluation with score and feedback
- Weakness identification per answer
- Final report with average score and hiring recommendation
- Data persistence with SQLite database

## 🛠️ Tech Stack
- **Backend:** FastAPI (Python)
- **AI:** Groq API(LLaMA3)
- **Database:** SQLite + SQLAlchemy
- **Frontend:** HTML, CSS, JavaScript
- **Deployment:** Render

## 📦 Installation
```bash
# Clone the repo
git clone https://github.com/Ayushi-324/AI-Interview-Simulator.git
cd AI-Interview-Simulator

# Install dependencies
pip install -r requirements.txt

# Set your API key
$env:GROQ_API_KEY="your_api_key"

# Run the app
uvicorn main:app --reload
```

Open `http://localhost:8000` in your browser.

## 🔑 Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | get ur Groq API key

## 📸 How It Works

1. Enter a job role (e.g. "backend engineer")
2. Answer 5 AI-generated interview questions
3. Get instant score and feedback after each answer
4. View your final report with weaknesses and hiring recommendation

## 📁 Project Structure

AI-Interview-Simulator/
├── main.py          # FastAPI backend with all API endpoints
├── database.py      # SQLAlchemy database models
├── app.py           # CLI version of the app
├── index.html       # Frontend UI
├── requirements.txt # Python dependencies
└── render.yaml      # Render deployment config


## 🌐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/generate-questions` | Generate 5 interview questions for a role |
| POST | `/evaluate` | Evaluate an answer and return score + feedback |
| GET | `/get-report/{session_id}` | Get final interview report |


Ayushi Tyagi — [GitHub](https://github.com/Ayushi-324)