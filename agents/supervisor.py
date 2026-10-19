"""Supervisor/router for selecting and invoking a specialized study agent."""

from collections.abc import Callable, Sequence
import re
from typing import TypedDict

from . import quiz_agent, study_planner_agent, tutor_agent

MODE_TO_AGENT = {
    "Automatic": None,
    "Tutor Agent": "tutor",
    "Quiz Agent": "quiz",
    "Study Planner Agent": "planner",
}


class AgentResponse(TypedDict):
    """Stable result shape returned by supervisor dispatch."""

    agent: str
    text: str


QUIZ_PATTERN = re.compile(
    r"\b(quiz|practice questions?|test me|mcq|multiple[- ]choice|short answer|check my answer|mark my answer|the answer is)\b",
    re.IGNORECASE,
)
PLANNER_PATTERN = re.compile(
    r"\b(study plan|study planner|study schedule|timetable|revision plan|"
    r"plan my (studies|study|week)|(?:make|create|build|draft) (?:me )?(?:a )?(?:study )?plan|"
    r"(?:make|create|build) (?:me )?(?:a )?schedule)\b",
    re.IGNORECASE,
)
EXPLICIT_QUESTION_PATTERN = re.compile(
    r"\b(what|how|why|when|where|who|explain|define|teach me|tell me)\b",
    re.IGNORECASE,
)


def route_request(
    request: str,
    mode: str = "Automatic",
    history: Sequence[dict] = (),
) -> str:
    """Route explicit requests first; keep short quiz attempts with the Quiz Agent."""
    if not isinstance(request, str) or not request.strip():
        raise ValueError("Type a question or study request first.")
    if mode not in MODE_TO_AGENT:
        raise ValueError("Choose Automatic, Tutor Agent, Quiz Agent, or Study Planner Agent.")
    if MODE_TO_AGENT[mode]:
        return MODE_TO_AGENT[mode]

    if QUIZ_PATTERN.search(request):
        return "quiz"
    if PLANNER_PATTERN.search(request):
        return "planner"

    for message in reversed(history):
        if not isinstance(message, dict):
            continue
        if message.get("role") == "assistant" and message.get("agent"):
            if (
                message["agent"] == "quiz"
                and len(request.strip()) <= 120
                and not EXPLICIT_QUESTION_PATTERN.search(request)
            ):
                return "quiz"
            break
    return "tutor"


def dispatch(
    request: str,
    answer: Callable[[str], str],
    *,
    mode: str = "Automatic",
    history: Sequence[dict] = (),
    quiz_format: str = "Mixed",
    planning_details: dict | None = None,
    planner_answer: Callable[[str], str] | None = None,
    planning_document: dict | None = None,
    answer_language: str = "English",
) -> AgentResponse:
    """Route a request and return the selected agent with its response."""
    agent_id = route_request(request, mode, history)
    prior_turns = history[:-1] if history and history[-1].get("role") == "user" else history
    if agent_id == "quiz":
        response = quiz_agent.respond(request, answer, prior_turns, quiz_format)
    elif agent_id == "planner":
        response = study_planner_agent.respond(
            request,
            planner_answer or answer,
            prior_turns,
            planning_details,
            planning_document,
            answer_language,
        )
    else:
        response = tutor_agent.respond(request, answer, prior_turns)
    return {"agent": agent_id, "text": response}
