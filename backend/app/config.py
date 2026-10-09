import os


def get_groq_api_key() -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. Set it as an environment variable."
        )

    return api_key