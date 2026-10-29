
from common.config import GEMINI_API_KEY, GEMINI_MODEL

_client = None


def _get_client():
    global _client

    if _client is None:
        from google import genai

        if not GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to your .env file."
            )

        _client = genai.Client(api_key=GEMINI_API_KEY)

    return _client


def call_gemini(
    prompt: str,
    system: str | None = None,
    max_tokens: int = 2048,
    response_mime_type: str | None = None,
) -> str:

    from google.genai import types

    full_prompt = prompt

    if system:
        full_prompt = (
            f"SYSTEM INSTRUCTIONS:\n{system}\n\n"
            f"USER REQUEST:\n{prompt}"
        )

    config = {
        "temperature": 0.3,
        "max_output_tokens": max_tokens,
    }

    if response_mime_type:
        config["response_mime_type"] = response_mime_type

    response = _get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=full_prompt,
        config=types.GenerateContentConfig(**config),
    )

    answer = response.text

    if not answer or not answer.strip():
        raise RuntimeError(
            "Gemini returned an empty response."
        )

    return answer.strip()


def call_gemini_with_image(
    prompt: str,
    image_b64: str,
    media_type: str,
    max_tokens: int = 2048,
) -> str:

    import base64
    from google.genai import types

    image_bytes = base64.b64decode(image_b64)

    response = _get_client().models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_text(text=prompt),
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=media_type,
            ),
        ],
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=max_tokens,
        ),
    )

    answer = response.text

    if not answer or not answer.strip():
        raise RuntimeError(
            "Gemini returned an empty image response."
        )

    return answer.strip()
