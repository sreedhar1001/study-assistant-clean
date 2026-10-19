"""Quiz agent: generate practice and evaluate learner attempts."""

from collections.abc import Callable, Sequence

from .common import build_agent_prompt

AnswerFunction = Callable[[str], str]
QUESTION_TYPES = {"Mixed", "Multiple choice", "Short answer"}


def respond(
    question: str,
    answer: AnswerFunction,
    history: Sequence[dict] = (),
    question_type: str = "Mixed",
) -> str:
    """Generate one or both quiz formats, or assess the latest learner attempt."""
    if question_type not in QUESTION_TYPES:
        raise ValueError("Choose Mixed, Multiple choice, or Short answer quiz format.")
    if question_type == "Mixed":
        format_instruction = (
            "Create one multiple-choice question with four labeled options and one short-answer question. "
            "Do not show the answer key until the learner attempts an answer."
        )
    elif question_type == "Multiple choice":
        format_instruction = (
            "Create one multiple-choice question with four labeled options. Do not show its answer yet."
        )
    else:
        format_instruction = "Create one short-answer question. Do not show its answer yet."

    instructions = (
        "You are the Quiz Agent. "
        "If the recent conversation contains an unanswered quiz and the learner has now responded, evaluate that "
        "response. Say whether it is correct or partly correct, explain briefly, and offer a hint if needed. "
        "Otherwise, make an age-neutral, topic-relevant practice quiz from the learner's request. "
        f"{format_instruction} Never invent facts; use the supplied search sources."
    )
    prompt = build_agent_prompt(instructions, question, history)
    return answer(prompt)
