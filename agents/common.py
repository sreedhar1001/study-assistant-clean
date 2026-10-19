"""Shared prompt validation and conversation context for study agents."""

from collections.abc import Sequence

MAX_QUESTION_CHARS = 600
MAX_AGENT_PROMPT_CHARS = 900
MAX_HISTORY_CHARS = 180


def build_agent_prompt(
    instructions: str,
    question: str,
    history: Sequence[dict] = (),
    extra_context: str = "",
) -> str:
    """Build a bounded prompt; recent chat is included only when it fits."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Type a question or study request first.")
    question = question.strip()
    if len(question) > MAX_QUESTION_CHARS:
        raise ValueError(f"Keep each request under {MAX_QUESTION_CHARS} characters.")

    base = f"{instructions.strip()}\n"
    if extra_context.strip():
        base += f"Planning details: {extra_context.strip()}\n"
    context_lines = []
    for message in history[-6:]:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        text = message.get("text")
        if role in {"user", "assistant"} and isinstance(text, str) and text.strip():
            context_lines.append(f"{role.title()}: {text.strip()[:100]}")
    history_text = "\n".join(context_lines)[-MAX_HISTORY_CHARS:]
    request_line = f"Current learner request: {question}"
    context_block = f"Recent conversation:\n{history_text}\n" if history_text else ""
    prompt = f"{base}{context_block}{request_line}"
    if len(prompt) > MAX_AGENT_PROMPT_CHARS and context_block:
        prompt = f"{base}{request_line}"
    if len(prompt) > MAX_AGENT_PROMPT_CHARS:
        raise ValueError("This request is too long for the answer service. Shorten it and try again.")
    return prompt
