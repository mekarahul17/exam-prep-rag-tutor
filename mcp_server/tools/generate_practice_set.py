
"""
MCP tool: generate_practice_set.

Generates NCERT-grounded structured MCQ practice questions.
Uses the student's weak topics through the DKT model when
no specific topic is provided.
"""

from __future__ import annotations

import json
import re

from common.llm_client import call_gemini
from knowledge_layer.retriever import format_results_for_llm, retrieve
from personalization_layer.sequence_tracker import get_weak_topics_lstm


def _parse_questions(response: str, count: int) -> str:
    """Validate and normalize Gemini's structured JSON response."""

    cleaned = response.strip()

    # Remove Markdown code fences if Gemini includes them.
    cleaned = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Gemini returned invalid JSON. Please generate the practice set again."
        ) from exc

    if not isinstance(data, dict):
        raise ValueError("Invalid practice set format.")

    questions = data.get("questions")

    if not isinstance(questions, list):
        raise ValueError("Practice set must contain a questions list.")

    if len(questions) != count:
        raise ValueError(
            f"Expected {count} questions, but received {len(questions)}."
        )

    validated_questions = []

    for index, question in enumerate(questions, start=1):

        if not isinstance(question, dict):
            raise ValueError(f"Question {index} has an invalid format.")

        question_text = question.get("question")
        options = question.get("options")
        correct_answer = question.get("correct_answer")
        explanation = question.get("explanation")

        if not isinstance(question_text, str) or not question_text.strip():
            raise ValueError(f"Question {index} has no valid question text.")

        if not isinstance(options, list) or len(options) != 4:
            raise ValueError(f"Question {index} must have exactly four options.")

        if not all(isinstance(option, str) and option.strip() for option in options):
            raise ValueError(f"Question {index} contains invalid options.")

        if len({option.strip().casefold() for option in options}) != 4:
            raise ValueError(f"Question {index} contains duplicate options.")

        if not isinstance(correct_answer, str):
            raise ValueError(f"Question {index} has no valid correct answer.")

        if correct_answer.strip().casefold() not in {
            option.strip().casefold() for option in options
        }:
            raise ValueError(
                f"Question {index} has an answer that does not match its options."
            )

        if not isinstance(explanation, str) or not explanation.strip():
            raise ValueError(f"Question {index} has no valid explanation.")

        validated_questions.append(
            {
                "id": index,
                "question": question_text.strip(),
                "type": "mcq",
                "options": options,
                "correct_answer": correct_answer.strip(),
                "explanation": explanation.strip(),
            }
        )

    result = {
        "questions": validated_questions
    }

    return json.dumps(result, ensure_ascii=False, indent=2)


def generate_practice_set(
    student_id: str,
    subject: str,
    topic: str | None = None,
    difficulty: str | None = None,
    count: int = 5,
) -> str:
    """
    Generate structured NCERT-grounded practice questions.

    Args:
        student_id: Unique identifier for the student.
        subject: Subject, e.g. Mathematics or Science.
        topic: Specific topic. If omitted, the student's
            weakest predicted topic in the subject is selected.
        difficulty: easy, medium, or hard.
        count: Number of questions to generate (1-10).

    Returns:
        JSON string containing structured MCQ questions.
    """

    if not student_id.strip():
        raise ValueError("Student ID cannot be empty.")

    if not subject.strip():
        raise ValueError("Subject cannot be empty.")

    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 10:
        raise ValueError("Question count must be between 1 and 10.")

    allowed_difficulties = {"easy", "medium", "hard"}

    difficulty = (difficulty or "medium").strip().lower()

    if difficulty not in allowed_difficulties:
        raise ValueError(
            "Difficulty must be easy, medium, or hard."
        )

    # Select a weak topic using DKT or EMA fallback.
    if not topic:
        weak_topics = get_weak_topics_lstm(
            student_id,
            subject=subject,
        )

        topic = weak_topics[0]["topic"] if weak_topics else subject

    topic = topic.strip()

    # Retrieve relevant NCERT curriculum material.
    retrieved_results = retrieve(
        topic,
        subject=subject,
        source_type="ncert",
        top_k=4,
    )

    context = format_results_for_llm(retrieved_results)

    if not context or not context.strip():
        raise ValueError(
            f"No NCERT reference material found for {subject}: {topic}."
        )

    prompt = f"""
You are an expert NCERT examination question generator.

Generate exactly {count} multiple-choice questions.

SUBJECT: {subject}
TOPIC: {topic}
DIFFICULTY: {difficulty}

STRICT CONTENT RULES:
1. Use only the NCERT reference material provided below.
2. Do not introduce facts that are not supported by the reference.
3. Questions must test conceptual understanding.
4. Every question must have exactly four distinct options.
5. Exactly one option must be correct.
6. Incorrect options must be plausible but unambiguously incorrect.
7. Explanations must be supported by the reference material.
8. Avoid duplicate or repeated questions.
9. Match the requested difficulty level.

OUTPUT RULES:
Return ONLY valid JSON.
Do not use Markdown code fences.
Do not include introductory or concluding text.

Use this exact JSON structure:

{{
    "questions": [
        {{
            "id": 1,
            "question": "Question text",
            "type": "mcq",
            "options": [
                "Option A",
                "Option B",
                "Option C",
                "Option D"
            ],
            "correct_answer": "Option A",
            "explanation": "Explanation based on NCERT reference material."
        }}
    ]
}}

Generate exactly {count} questions.

NCERT REFERENCE MATERIAL:
{context}
"""

    response = call_gemini(prompt)

    if not isinstance(response, str) or not response.strip():
        raise ValueError("Gemini returned an empty practice set.")

    return _parse_questions(response, count)
