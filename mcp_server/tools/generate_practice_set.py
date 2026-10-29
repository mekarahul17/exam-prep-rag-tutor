"""MCP tool for NCERT-grounded adaptive MCQ practice generation."""

from __future__ import annotations

import json

import logging

import re

from common.llm_client import call_gemini

from knowledge_layer.retriever import format_results_for_llm, retrieve

from personalization_layer.sequence_tracker import get_weak_topics_lstm

from personalization_layer.tracker import get_all_topics_by_mastery

logger = logging.getLogger(__name__)

_GENERIC_TOPIC_NAMES = {"science", "math", "maths", "mathematics"}

def _is_generic_topic(subject: str, topic: object) -> bool:

    if not isinstance(topic, str) or not topic.strip():

        return True

    return topic.strip().casefold() in (_GENERIC_TOPIC_NAMES | {subject.strip().casefold()})

def _extract_json(response: str) -> dict:

    cleaned = re.sub(r"```(?:json)?", "", response.strip(), flags=re.IGNORECASE)

    cleaned = cleaned.replace("```", "").strip()

    decoder = json.JSONDecoder()

    try:

        data = json.loads(cleaned)

        if isinstance(data, dict):

            return data

    except json.JSONDecodeError:

        pass

    for match in re.finditer(r"\{", cleaned):

        try:

            data, _ = decoder.raw_decode(cleaned[match.start():])

            if isinstance(data, dict) and "questions" in data:

                return data

        except json.JSONDecodeError:

            continue

    raise ValueError("Gemini did not return a valid JSON object.")

def _parse_questions(

    response: str,

    count: int,

    topic: str,

    subject: str,

    allow_topic_variation: bool = False,

) -> list[dict]:

    data = _extract_json(response)

    questions = data.get("questions")

    if not isinstance(questions, list):

        raise ValueError("Practice set must contain a questions list.")

    if len(questions) != count:

        raise ValueError(f"Expected {count} questions, received {len(questions)}.")

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

        normalized_options = [option.strip() for option in options]

        if len({option.casefold() for option in normalized_options}) != 4:

            raise ValueError(f"Question {index} contains duplicate options.")

        if not isinstance(correct_answer, str) or not correct_answer.strip():

            raise ValueError(f"Question {index} has no valid correct answer.")

        matching_options = [

            option for option in normalized_options

            if option.casefold() == correct_answer.strip().casefold()

        ]

        if not matching_options:

            raise ValueError(f"Question {index} answer does not match its options.")

        if not isinstance(explanation, str) or not explanation.strip():

            raise ValueError(f"Question {index} has no valid explanation.")

        if allow_topic_variation:

            question_topic = question.get("topic")

            if _is_generic_topic(subject, question_topic):

                raise ValueError(

                    f"Question {index} must have a specific NCERT subtopic, "

                    "not a generic subject label."

                )

            question_topic = question_topic.strip()

        else:

            question_topic = topic

        validated_questions.append({

            "id": index,

            "topic": question_topic,

            "question": question_text.strip(),

            "type": "mcq",

            "options": normalized_options,

            "correct_answer": matching_options[0],

            "explanation": explanation.strip(),

        })

    return validated_questions

def _select_adaptive_topic_with_mastery(
    student_id: str,
    subject: str,
) -> dict | None:
    """Choose the weakest specific topic and return its mastery estimate."""
    try:
        weak_topics = get_weak_topics_lstm(student_id, subject=subject)
        for item in weak_topics or []:
            selected = item.get("topic")
            mastery = item.get("mastery_score")
            if not _is_generic_topic(subject, selected):
                return {
                    "topic": selected.strip(),
                    "mastery_score": float(mastery) if mastery is not None else None,
                    "source": "dkt",
                }
    except Exception:
        logger.exception("DKT topic selection failed")

    try:
        all_topics = get_all_topics_by_mastery(student_id, subject=subject)
        for item in all_topics or []:
            selected = item.get("topic")
            mastery = item.get("mastery_score")
            if not _is_generic_topic(subject, selected):
                return {
                    "topic": selected.strip(),
                    "mastery_score": float(mastery) if mastery is not None else None,
                    "source": "ema",
                }
    except Exception:
        logger.exception("Database mastery fallback failed")

    logger.info("No specific topic history found for student=%s, subject=%s", student_id, subject)
    return None


def _select_adaptive_topic(student_id: str, subject: str) -> str | None:
    """Backward-compatible helper returning only the selected topic."""
    selection = _select_adaptive_topic_with_mastery(student_id, subject)
    return selection["topic"] if selection else None


def _difficulty_from_mastery(mastery_score: float | None) -> str:
    """Map estimated mastery to a practice difficulty."""
    if mastery_score is None:
        return "medium"
    if mastery_score < 0.40:
        return "easy"
    if mastery_score <= 0.70:
        return "medium"
    return "hard"


def generate_practice_set(

    student_id: str,

    subject: str,

    topic: str | None = None,

    difficulty: str | None = None,

    count: int = 5,

) -> str:

    """Generate NCERT-grounded MCQs with question-level topic attribution."""

    if not isinstance(student_id, str) or not student_id.strip():

        raise ValueError("Student ID cannot be empty.")

    if not isinstance(subject, str) or not subject.strip():

        raise ValueError("Subject cannot be empty.")

    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 10:

        raise ValueError("Question count must be between 1 and 10.")

    requested_difficulty = difficulty.strip().lower() if isinstance(difficulty, str) else None
    if requested_difficulty is not None and requested_difficulty not in {"easy", "medium", "hard"}:
        raise ValueError("Difficulty must be easy, medium, or hard.")

    student_id = student_id.strip()
    subject = subject.strip()

    adaptive_selection = None
    user_selected_topic = isinstance(topic, str) and bool(topic.strip())
    if user_selected_topic:
        topic = topic.strip()
        general_practice = False
    else:
        adaptive_selection = _select_adaptive_topic_with_mastery(student_id, subject)
        topic = adaptive_selection["topic"] if adaptive_selection else None
        general_practice = topic is None

    if requested_difficulty is not None:
        difficulty = requested_difficulty
    elif adaptive_selection is not None:
        difficulty = _difficulty_from_mastery(adaptive_selection.get("mastery_score"))
    else:
        difficulty = "medium"

    if adaptive_selection is not None:
        logger.info(
            "Adaptive difficulty: topic=%s mastery=%s source=%s difficulty=%s",
            adaptive_selection["topic"],
            adaptive_selection.get("mastery_score"),
            adaptive_selection.get("source"),
            difficulty,
        )

    if general_practice:

        # Keep the subject at quiz level for existing API compatibility;

        # every individual question below receives its own real subtopic.

        topic = subject

        logger.info("No topic-level history; generating general %s practice", subject)

    if not isinstance(topic, str) or not topic.strip():

        raise ValueError("Topic cannot be empty.")

    topic = topic.strip()

    logger.info(

        "Generating practice: student=%s subject=%s topic=%s general=%s difficulty=%s",

        student_id, subject, topic, general_practice, difficulty,

    )

    retrieved_results = retrieve(topic, subject=subject, source_type="ncert", top_k=4)

    context = format_results_for_llm(retrieved_results)

    if not context or not context.strip():

        raise ValueError(f"No NCERT reference material found for {subject}: {topic}.")

    if general_practice:

        topic_rules = (

            "The student selected only the subject, not a topic. Create questions "

            "across concepts in the supplied NCERT material. For EVERY question, "

            "return its most specific meaningful NCERT chapter/concept/subtopic "

            "in a string field named topic. Use only concepts supported by the "

            "reference material. Never use generic labels such as Science, Math, "

            "or Mathematics. Different questions may have different topics."

        )

        topic_field = '"topic": "Specific NCERT subtopic",'

    else:

        topic_rules = (

            f"All questions must be about this fixed topic: {topic}. "

            "The application will assign this topic to every question."

        )

        topic_field = ""

    prompt = f"""

You are an expert NCERT examination question generator.

Generate exactly {count} multiple-choice questions.

SUBJECT: {subject}

TOPIC: {topic}

DIFFICULTY: {difficulty}

TOPIC ATTRIBUTION RULES:

{topic_rules}

STRICT CONTENT RULES:

1. Use only the NCERT reference material below; do not introduce unsupported facts.

2. Test conceptual understanding.

3. Every question must have exactly four distinct options.

4. Exactly one option must be correct.

5. Incorrect options must be plausible but unambiguously incorrect.

6. Explanations must be supported by the reference material.

7. Avoid duplicate questions and match the requested difficulty.

OUTPUT RULES:

Return one valid JSON object only. No Markdown fences or extra text.

Use double quotes for all JSON keys and string values. No trailing commas.

Use this exact structure:

{{

  "questions": [

    {{

      "id": 1,

      {topic_field}

      "question": "Question text",

      "type": "mcq",

      "options": ["Option A", "Option B", "Option C", "Option D"],

      "correct_answer": "Option A",

      "explanation": "Explanation based on NCERT reference material."

    }}

  ]

}}

Generate exactly {count} questions.

NCERT REFERENCE MATERIAL:

{context}

"""

    last_error = None

    for attempt in range(2):

        current_prompt = prompt

        if attempt == 1:

            current_prompt += (

                "\nRETRY: Return only valid JSON, exactly the requested number "

                "of questions. For general practice, every question MUST have "

                "a specific, non-generic NCERT subtopic in its topic field.\n"

            )

        response = call_gemini(

            current_prompt,

            max_tokens=8192,

            response_mime_type="application/json",

        )

        if not isinstance(response, str) or not response.strip():

            last_error = ValueError("Gemini returned an empty practice set.")

            continue

        try:

            questions = _parse_questions(

                response=response,

                count=count,

                topic=topic,

                subject=subject,

                allow_topic_variation=general_practice,

            )

            result = {

                "student_id": student_id,

                "subject": subject,

                "topic": topic,

                "difficulty": difficulty,
                "adaptive_mastery": (
                    adaptive_selection.get("mastery_score")
                    if adaptive_selection is not None
                    else None
                ),
                "questions": questions,

            }

            return json.dumps(result, ensure_ascii=False, indent=2)

        except ValueError as exc:

            last_error = exc

            logger.warning("Practice generation validation failed on attempt %s: %s", attempt + 1, exc)

    raise ValueError(f"Practice generation failed after two attempts: {last_error}")
