from groq import Groq
import json
import os

# Configure API key
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Storing weaknesses globally
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

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    text = response.choices[0].message.content.strip()
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

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    text = response.choices[0].message.content.strip()

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