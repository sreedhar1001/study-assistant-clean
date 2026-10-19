"""Question preparation and answer generation through an injected search provider."""

from __future__ import annotations

import re
from collections.abc import Callable

from study_assistant.providers.tavily import relevant_images, tavily_search

MAX_TAVILY_QUERY_LENGTH = 1500
K12_EDUCATION_DOMAINS = [
    "ncert.nic.in",
    "khanacademy.org",
    "bbc.co.uk",
    "sciencelearn.org.nz",
    "britannica.com",
]
SYSTEM_INSTRUCTIONS = (
    "You are Still, a calm, patient tutor. Answer first in 1–2 plain sentences, then give brief numbered reasoning "
    "steps. End with one short check or tiny practice. Be concise; no filler or praise. Use only supplied search "
    "results and attached notes for facts; say when they do not support an answer. Never guess or invent facts, "
    "links, or quotes. If unclear, ask one clarifying question and wait. Reply simply in the selected English, "
    "Hindi, or Telugu. Use an attached file first and state gaps."
)


def latest_question(messages: list[dict]) -> str:
    for item in reversed(messages):
        if item.get("role") == "user":
            question = str(item.get("text", "")).strip()
            if question:
                return question[:4000]
    raise ValueError("Enter a question and try again.")


def recent_learning_dialogue(messages: list[dict], limit: int = 6) -> str:
    """Keep a small amount of prior chat so Kids Learning can count attempts."""
    turns = []
    for item in messages[-(limit + 1):-1]:
        role = item.get("role")
        text = str(item.get("text", "")).strip()
        if role in {"user", "assistant"} and text:
            turns.append(f"{role.title()}: {text[:500]}")
    return "\n".join(turns)[-300:]


def relevant_note_excerpt(contents: str, question: str, max_chars: int) -> str:
    """Select question-related note sentences that fit the search provider's query limit."""
    if max_chars <= 0:
        return ""
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+|\n+", contents) if part.strip()]
    if not sentences:
        return contents[:max_chars]
    terms = {term.casefold() for term in re.findall(r"\w+", question) if len(term) > 2}
    scored = []
    for index, sentence in enumerate(sentences):
        words = {term.casefold() for term in re.findall(r"\w+", sentence)}
        score = len(terms & words)
        if score:
            scored.append((index, score, sentence))
    if not scored:
        scored = [(0, 0, sentences[0])]
    chosen = []
    used = 0
    for index, _, sentence in sorted(scored, key=lambda item: (-item[1], item[0])):
        extra = len(sentence) + (1 if chosen else 0)
        if used + extra <= max_chars:
            chosen.append((index, sentence))
            used += extra
    if not chosen:
        return scored[0][2][:max_chars]
    return " ".join(sentence for _, sentence in sorted(chosen))


def generate_answer(
    provider: str,
    messages: list[dict],
    config: dict[str, str],
    document: dict | None = None,
    learning_context: dict | None = None,
    education_context: dict | None = None,
    answer_language: str = "en",
    document_source_only: bool = False,
    *,
    search: Callable[..., dict] = tavily_search,
) -> dict:
    """Build a bounded, grounded search request and return the provider's answer contract."""
    if provider != "tavily":
        raise ValueError("Tavily is the supported answer provider.")
    question = latest_question(messages)
    language_names = {"en": "English", "hi": "Hindi", "te": "Telugu"}
    if answer_language not in language_names:
        raise ValueError("Choose English, Hindi, or Telugu for the answer language.")
    scope = ""
    if learning_context:
        subject = "Maths" if learning_context["subject"] == "Math" else learning_context["subject"]
        dialogue = recent_learning_dialogue(messages)
        scope = (
            f"Indian Standard {learning_context['grade']}, subject {subject}. Stay within Standards 1–10. "
            "Use short, age-level sentences, everyday examples, and NCERT-style Indian classroom steps. Be "
            "encouraging, honest, and child-safe; redirect unsuitable or off-topic requests. For practice, give "
            "one hint and one guiding question; reveal the answer only if asked or after two clearly wrong attempts "
            "shown in the recent dialogue. Ask only that one question.\n"
        )
        if dialogue:
            scope += f"Recent learning dialogue:\n{dialogue}\n"
    elif education_context:
        scope = (
            f"The learner is {education_context['stage']} studying {education_context['subject']}. "
            "Use correct terminology and briefly define new terms. Show worked steps for calculations and point out "
            "common mistakes. For graded assignments, do not complete the work on the learner's behalf; guide them "
            "with hints and explain the method so they can do it themselves.\n"
        )
    if document is not None and document_source_only:
        scope += (
            "For this answer, use only the supplied retrieved passages from the learner's PDF. "
            "Cite the exact filename and page labels shown in those passages. If they do not support the answer, "
            "say the PDF does not cover it; do not fill gaps with outside facts or invented citations.\n"
        )
    query = (
        f"{question}\n" + SYSTEM_INSTRUCTIONS + "\n"
        + f"Respond in {language_names[answer_language]}. Use that language's usual writing system.\n" + scope
    )
    if document:
        note_label = f"\nRelevant excerpts from attached study file {document['name']} (only excerpts fit the search limit):\n"
        note_budget = MAX_TAVILY_QUERY_LENGTH - len(query) - len(note_label)
        excerpt = relevant_note_excerpt(document["text"], question, note_budget)
        if not excerpt:
            raise ValueError("The question and learning instructions leave too little room for a study-file excerpt. Shorten the question and try again.")
        query += note_label + excerpt
    if len(query) > MAX_TAVILY_QUERY_LENGTH:
        raise ValueError("This question and its learning context exceed the search service's 1,500-character limit. Please shorten the question and try again.")
    data = search(
        config,
        query,
        search_depth="advanced",
        max_results=5,
        include_answer="advanced",
        safe_search=True,
        include_images=bool(learning_context or education_context),
        include_domains=K12_EDUCATION_DOMAINS if learning_context else None,
        include_domains_mode="prefer",
    )
    answer = str(data.get("answer") or "").strip()
    if not answer:
        raise ValueError("I couldn't find a clear answer to that question. Try rephrasing it or adding a little context.")
    return {"answer": answer, "images": relevant_images(data) if learning_context or education_context else []}
