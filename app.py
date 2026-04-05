import google.generativeai as genai
import json

# Configure API key
genai.configure(api_key="AIzaSyAAtupEwzxGzEtLj6RAQeL5Kx2LcolMTSo")

# Model
model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")

# Storing weaknesses globally to generate final report at the end
weakness_list = []


def generate_questions(role):
    prompt = f"""
    You are a technical interviewer.

    Generate EXACTLY 5 interview questions for a {role} role.

    Rules:
    - Only return questions
    - One question per line
    - No numbering
    - No explanations
    """

    response = model.generate_content(prompt)
    text = response.text.strip()
    questions = text.split("\n")
    return [q.strip() for q in questions if q.strip()]


def evaluate_answer(question, answer):
    prompt = f"""
    You are a strict interviewer.

    Question: {question}
    Candidate Answer: {answer}

    Evaluate based on:
    - correctness
    - depth
    - clarity

    Return ONLY valid JSON in this format:
    {{
        "score": number(0-10),
        "feedback": "text",
        "weakness": "short phrase"
    }}
    """
    response = model.generate_content(prompt)

    text = response.text.strip()

    result = {}
    try:
        result = json.loads(text)
    except Exception:
        result = {
            "score": 5,
            "feedback": "Could not parse response properly.",
            "weakness": "parsing error"
        }

    weakness_list.append(result["weakness"])
    return result


def main():
    role = input("Enter role: ")

    questions = generate_questions(role)

    print("\n--- Interview Questions ---\n")

    for q in questions:
        print(q)
        answer = input("Your answer: ")

        result = evaluate_answer(q, answer)

        print("\nEvaluation:")
        print(f"Score: {result['score']}/10")
        print(f"Feedback: {result['feedback']}")
        print(f"Weakness Identified: {result['weakness']}")
        print("\n--------------------------\n")

    # Final Report
    print("\n=== FINAL REPORT ===")

    unique_weaknesses = list(set(weakness_list))

    print("Your Weak Areas:")
    for w in unique_weaknesses:
        print("-", w)


if __name__ == "__main__":
    main()