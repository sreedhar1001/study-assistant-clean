"""Small Groq chat-completions client using the existing standard library."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_MODEL = "openai/gpt-oss-20b"
GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"


def chat_completion(config: dict[str, str], prompt: str) -> str:
    """Generate one bounded completion without logging credentials or prompts."""
    api_key = config.get("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Add GROQ_API_KEY to .env or the server environment, then restart the app.")

    payload = {
        "model": config.get("GROQ_MODEL", DEFAULT_MODEL),
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 4096,
    }
    request = Request(
        GROQ_CHAT_COMPLETIONS_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in (401, 403):
            raise ValueError("Groq rejected the API key or the key lacks permission.") from None
        if error.code == 429:
            raise ValueError("Groq rate limit or account quota was reached. Try again shortly.") from None
        raise ValueError(f"Groq request failed (HTTP {error.code}).") from None
    except (URLError, TimeoutError):
        raise ValueError("Could not reach Groq. Check the internet connection and try again.") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Groq returned an unreadable response. Please try again.") from None

    choices = data.get("choices") if isinstance(data, dict) else None
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ValueError("Groq returned an incomplete response. Please try again.")
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Groq returned an empty response. Please try again.")
    return content.strip()
