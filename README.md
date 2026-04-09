# 🎯 AI Interview Simulator

An AI-powered interview preparation tool that generates role-specific interview questions using **LLaMA 3**, evaluates your answers in real-time, and provides a detailed performance report.

## 🚀 Live Demo
**[Check out the App on Hugging Face Spaces](https://huggingface.co/spaces/ayushi3/AI-Interview-Simulator)**

## 💡 Features
- **Role-Based Generation:** Generates 5 tailored technical/behavioral questions for any job role.
- **Instant Evaluation:** Provides a score (0-10) and constructive feedback for every answer using Groq LLaMA 3.1.
- **Deep Insights:** Identifies specific weaknesses in your responses to help you improve.
- **Hiring Report:** Summarizes performance with an average score and a final AI hiring recommendation.
- **Dockerized Architecture:** Frontend and Backend are bundled into a single container for zero-latency communication and easy deployment.

## 🛠️ Tech Stack
- **Backend:** FastAPI (Python)
- **AI Engine:** Groq API (LLaMA 3.1 8b-instant)
- **Database:** SQLite + SQLAlchemy
- **Frontend:** Vanilla JavaScript, HTML5, CSS3
- **Deployment:** Docker on Hugging Face Spaces

## 📦 Local Installation
```bash
# Clone the repo
git clone [https://github.com/Ayushi-324/AI-Interview-Simulator.git](https://github.com/Ayushi-324/AI-Interview-Simulator.git)
cd AI-Interview-Simulator

# Install dependencies
pip install -r requirements.txt

# Set your Groq API key (Example for Windows PowerShell)
$env:GROQ_API_KEY="your_api_key_here"

# Run the app locally
uvicorn main:app --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.

## 🔑 Environment Variables

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | get ur Groq API key from the Groq Console.

## 📸 How It Works

1. Enter a job role (e.g. "backend engineer")
2. Answer 5 AI-generated interview questions
3. Get instant score and feedback after each answer
4. View your final report with weaknesses and hiring recommendation

## 📁 Project Structure

AI-Interview-Simulator/
├── main.py          # Unified FastAPI backend, Database logic & Routes
├── index.html       # Single-page Frontend UI
├── requirements.txt # Python dependencies (fastapi, httpx, sqlalchemy, etc.)
├── Dockerfile       # Deployment instructions for Hugging Face
└── README.md        # Project documentation

## 🌐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/generate-questions` | Generate 5 interview questions for a role |
| POST | `/evaluate` | Evaluate an answer and return score + feedback |
| GET | `/get-report/{session_id}` | Get final interview report |


Ayushi Tyagi — [GitHub](https://github.com/Ayushi-324)
