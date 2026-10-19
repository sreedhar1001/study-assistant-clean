"""Local Study Assistant server. API keys stay on the server, never in browser code."""

from __future__ import annotations

import json
import hashlib
import os
import re
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None


ROOT = Path(__file__).resolve().parent
CONFIG_FILES = (ROOT / ".env.example", ROOT / ".env")
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


def load_config() -> dict[str, str]:
    values: dict[str, str] = {}
    for config_file in CONFIG_FILES:
        if not config_file.is_file():
            continue
        for raw_line in config_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            name = name.strip()
            if name.startswith("export "):
                name = name[7:].strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[name] = value

    for name in ("TAVILY_API_KEY",):
        if os.environ.get(name):
            values[name] = os.environ[name]
    return values


def configured_providers() -> list[str]:
    config = load_config()
    return ["tavily"] if config.get("TAVILY_API_KEY") else []


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


def request_json(url: str, headers: dict[str, str], payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code in (401, 403):
            raise ValueError("The provider rejected its API key or the key lacks permission.") from None
        if error.code == 429:
            raise ValueError("The provider rate limit or account quota was reached.") from None
        raise ValueError(f"The provider request failed (HTTP {error.code}).") from None
    except URLError:
        raise ValueError("Could not reach Tavily. Check the internet connection and try again.") from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("The AI provider returned an unreadable response.") from None


def tavily_search(config: dict[str, str], query: str, *, search_depth: str, max_results: int, include_answer: str | bool, safe_search: bool = False, include_domains: list[str] | None = None, include_domains_mode: str = "restrict", include_images: bool = False, topic: str | None = None, time_range: str | None = None) -> dict:
    key = config.get("TAVILY_API_KEY", "")
    if not key:
        raise ValueError("Add TAVILY_API_KEY to .env or the server environment, then restart the local server.")
    payload = {
        "query": query,
        "search_depth": search_depth,
        "max_results": max_results,
        "include_answer": include_answer,
        "safe_search": safe_search,
    }
    if topic:
        payload["topic"] = topic
    if time_range:
        payload["time_range"] = time_range
    if include_images:
        payload["include_images"] = True
    if include_domains:
        payload["include_domains"] = include_domains
        payload["include_domains_mode"] = include_domains_mode
    if TavilyClient is not None:
        return TavilyClient(api_key=key).search(**payload)
    return request_json(
        "https://api.tavily.com/search",
        {"Authorization": f"Bearer {key}"},
        payload,
    )


def relevant_images(data: dict, limit: int = 2) -> list[dict[str, str]]:
    candidates = list(data.get("images", [])) if isinstance(data.get("images"), list) else []
    for result in data.get("results", []):
        if isinstance(result, dict) and isinstance(result.get("images"), list):
            candidates.extend(result["images"])
    images = []
    seen = set()
    for candidate in candidates:
        if isinstance(candidate, str):
            image_url, description = candidate, "Related learning image"
        elif isinstance(candidate, dict):
            image_url = candidate.get("url", "")
            description = candidate.get("description") or "Related learning image"
        else:
            continue
        if not isinstance(image_url, str) or not image_url.startswith("https://") or image_url in seen:
            continue
        seen.add(image_url)
        images.append({"url": image_url, "description": str(description)[:180]})
        if len(images) >= limit:
            break
    return images


DISCOVERY_SECTIONS = {
    "technology_news": {
        "title": "Latest technology news",
        "topic": "news",
        "query": "latest technology news announcements and developments",
        "sources": [],
    },
    "innovations": {
        "title": "New innovations",
        "topic": "news",
        "query": "newly announced technology innovations and inventions",
        "sources": [],
    },
    "research_papers": {
        "title": "Latest research papers",
        "topic": "general",
        "query": "recently published research papers and preprints in science technology engineering and computing",
        "sources": ["arxiv.org", "nature.com", "science.org", "ieeexplore.ieee.org", "dl.acm.org", "openreview.net", "biorxiv.org"],
    },
    "advanced_technology": {
        "title": "Advanced technology",
        "topic": "general",
        "query": "recent breakthroughs and advances in artificial intelligence quantum computing robotics semiconductors biotechnology and clean energy",
        "sources": [],
    },
}


def result_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return parsedate_to_datetime(value).date()
        except (TypeError, ValueError, OverflowError):
            return None


def search_discovery_section(kind: str, learner_query: str, config: dict[str, str]) -> dict:
    section = DISCOVERY_SECTIONS.get(kind)
    if not section:
        raise ValueError("Choose a technology search section and try again.")
    today = datetime.now(timezone.utc).date()
    search_text = learner_query.strip()[:180] if isinstance(learner_query, str) else ""
    query = f"{section['query']} {search_text} published in the last 7 days. Today is {today.isoformat()}."
    data = tavily_search(
        config,
        query,
        search_depth="advanced",
        max_results=5,
        include_answer=False,
        safe_search=True,
        include_domains=section["sources"] or None,
        include_domains_mode="prefer",
        include_images=True,
        topic=section["topic"],
        time_range="week",
    )
    results = []
    for item in data.get("results", []):
        if not isinstance(item, dict):
            continue
        published = str(item.get("published_date") or "")
        published_day = result_date(published)
        if not published_day or published_day > today or (today - published_day).days > 7:
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            continue
        results.append({
            "title": str(item.get("title") or "Recent result")[:240],
            "summary": str(item.get("content") or "No summary was provided.")[:900],
            "published": published[:80] if published else "Date not listed",
            "url": url,
        })
    return {
        "kind": kind,
        "title": section["title"],
        "searched_on": today.isoformat(),
        "results": results,
        "images": relevant_images(data, limit=3),
    }


def generate_answer(provider: str, messages: list[dict], config: dict[str, str], document: dict | None = None, learning_context: dict | None = None, education_context: dict | None = None, answer_language: str = "en") -> dict:
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
            f"Indian Standard {learning_context['grade']}, subject {subject}. Stay within Standards 1?10. "
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
    query = (
        f"{question}\n"
        + SYSTEM_INSTRUCTIONS
        + "\n"
        + f"Respond in {language_names[answer_language]}. Use that language's usual writing system.\n"
        + scope
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
    data = tavily_search(
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
    if not answer.strip():
        raise ValueError("I couldn't find a clear answer to that question. Try rephrasing it or adding a little context.")
    return {"answer": answer.strip(), "images": relevant_images(data) if learning_context or education_context else []}


def daily_topic(grade: int, subject: str, today: str) -> str:
    math_topics = {
        1: ["counting and adding small numbers", "taking away within 20", "comparing numbers", "simple shapes", "counting objects in groups", "measuring with everyday objects"],
        2: ["two-digit addition", "two-digit subtraction", "equal groups and multiplication", "simple fractions", "length and measurement", "number patterns"],
        3: ["multiplication facts", "division into equal groups", "fractions on a number line", "area of rectangles", "rounding numbers", "time and measurement"],
        4: ["multi-digit multiplication", "long division", "equivalent fractions", "factors and multiples", "area and perimeter", "decimal place value"],
        5: ["fractions and mixed numbers", "decimal operations", "volume of rectangular prisms", "coordinate grids", "percentages", "order of operations"],
        6: ["ratios and rates", "fractions and decimals", "integers", "expressions and equations", "area and surface area", "statistics and data"],
        7: ["proportions and percentages", "rational numbers", "linear equations", "scale drawings", "angle relationships", "probability"],
        8: ["linear equations", "functions and graphs", "Pythagorean theorem", "exponents", "transformations", "data and scatter plots"],
        9: ["linear equations and graphs", "polynomials", "geometry and similarity", "coordinate geometry", "surface area and volume", "statistics"],
        10: ["quadratic equations", "trigonometry", "arithmetic sequences", "circle geometry", "probability", "statistics"],
    }
    bands = {
        "Science": {
            "early": ["plants and what they need", "animals and their habitats", "weather and seasons", "light and shadows", "materials around us", "water and its uses"],
            "middle": ["the water cycle", "food chains", "forces and motion", "simple machines", "electric circuits", "states of matter"],
            "upper": ["ecosystems and energy flow", "cells and microscopes", "chemical changes", "electricity and resistance", "the human respiratory system", "Earth's climate"],
        },
        "Biology": {
            "early": ["the needs of plants", "animal life cycles", "living and non-living things", "how animals use their senses", "different habitats", "parts of a flower"],
            "middle": ["photosynthesis", "food chains and ecosystems", "the digestive system", "plant pollination", "cells and their parts", "how the lungs work"],
            "upper": ["cell structure and function", "inheritance and genes", "photosynthesis and respiration", "ecosystems and biodiversity", "the immune system", "variation in populations"],
        },
    }
    if subject == "Math":
        return math_topics[grade][0]
    band = "early" if grade <= 3 else "middle" if grade <= 6 else "upper"
    topics = bands[subject][band]
    seed = int.from_bytes(hashlib.sha256(f"{today}:{grade}:{subject}".encode()).digest()[:4], "big")
    return topics[seed % len(topics)]


def math_daily_question(grade: int, seed: int) -> str:
    if grade <= 1:
        a, b = 2 + seed % 8, 1 + (seed >> 3) % 8
        return f"There are {a} red flowers and {b} yellow flowers. How many flowers are there altogether? Show how you counted."
    if grade == 2:
        a, b = 20 + seed % 70, 10 + (seed >> 4) % 60
        return f"A library has {a} storybooks and gets {b} more. How many storybooks does it have now? Show your addition."
    if grade == 3:
        a, b = 2 + seed % 8, 2 + (seed >> 5) % 8
        return f"There are {a} baskets with {b} apples in each basket. How many apples are there altogether? Write a multiplication sentence."
    if grade == 4:
        divisor = 2 + seed % 8
        quotient = 12 + (seed >> 4) % 18
        return f"A teacher shares {divisor * quotient} pencils equally among {divisor} groups. How many pencils are in each group? Explain how division helps."
    if grade == 5:
        numerator = 1 + seed % 4
        denominator = 5 + (seed >> 4) % 5
        return f"A water bottle is {numerator}/{denominator} full. What fraction of the bottle is empty? Show your reasoning."
    if grade == 6:
        a, b = 2 + seed % 8, 2 + (seed >> 5) % 8
        return f"A recipe uses {a} cups of flour for {b} batches. How many cups are needed for 3 batches at the same rate? Show the proportion."
    if grade <= 8:
        a, x = 2 + seed % 8, 3 + (seed >> 4) % 9
        b = 5 + (seed >> 8) % 15
        return f"Solve {a}x + {b} = {a * x + b}. Show the steps you use to find x."
    if grade == 9:
        length, width = 5 + seed % 12, 3 + (seed >> 4) % 10
        return f"A rectangle has length {length} cm and width {width} cm. Find its area and perimeter, and explain the difference between them."
    a, b = 2 + seed % 8, 3 + (seed >> 4) % 8
    return f"A quadratic equation has factors (x − {a}) and (x + {b}). Expand the factors, then find both values of x that make the equation equal zero."


def generate_daily_question(grade: int, subject: str, config: dict[str, str]) -> dict:
    today = date.today().isoformat()
    seed = int.from_bytes(hashlib.sha256(f"{today}:{grade}:{subject}".encode()).digest()[:8], "big")
    topic = daily_topic(grade, subject, today)
    if subject == "Math":
        question = math_daily_question(grade, seed)
        query = f"Reliable primary and secondary school resources explaining {topic} for Indian Standard {grade} students. Exclude college and university material. Date: {today}."
    elif subject == "Biology":
        question = f"What is one important idea about {topic}? Explain it in a way a Standard {grade} learner can understand, using an example."
        query = f"Age-appropriate primary and secondary school biology resource about {topic} for Indian Standard {grade}. Exclude college and university material. Date: {today}."
    else:
        question = f"What is one important idea about {topic}? Explain it in a way a Standard {grade} learner can understand, using an example."
        query = f"Age-appropriate primary and secondary school science resource about {topic} for Indian Standard {grade}. Exclude college and university material. Date: {today}."
    data = tavily_search(
        config,
        query,
        search_depth="basic",
        max_results=3,
        include_answer=False,
        safe_search=True,
        include_domains=K12_EDUCATION_DOMAINS,
        include_images=True,
    )
    sources = [
        {"title": str(result.get("title") or result.get("url") or "Source"), "url": result.get("url")}
        for result in data.get("results", [])[:3]
        if isinstance(result.get("url"), str) and result["url"].startswith(("https://", "http://"))
    ]
    return {"question": question, "topic": topic, "grade": grade, "subject": subject, "day": today, "sources": sources, "images": relevant_images(data, limit=1)}


class StudyAssistantHandler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/api/config":
            config = load_config()
            providers = configured_providers()
            self.send_json(200, {"providers": providers, "preferred": "tavily"})
            return

        relative = self.path.split("?", 1)[0].lstrip("/") or "index.html"
        if any(part.startswith(".") for part in Path(relative).parts):
            self.send_error(404)
            return
        target = (ROOT / relative).resolve()
        if ROOT not in target.parents and target != ROOT:
            self.send_error(403)
            return
        if not target.is_file():
            self.send_error(404)
            return
        content_types = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".js": "text/javascript; charset=utf-8"}
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_types.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path not in {"/api/chat", "/api/daily-question", "/api/discovery"}:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 64_000:
                raise ValueError("The message is empty or too large.")
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/api/discovery":
                kind = body.get("kind", "")
                query = body.get("query", "")
                if not isinstance(query, str) or len(query) > 180:
                    raise ValueError("Keep a technology search under 180 characters.")
                self.send_json(200, search_discovery_section(kind, query, load_config()))
                return
            if self.path == "/api/daily-question":
                grade = body.get("grade")
                subject = body.get("subject")
                if type(grade) is not int or not 1 <= grade <= 10:
                    raise ValueError("Choose a standard from 1 to 10.")
                if subject not in {"Math", "Science", "Biology"}:
                    raise ValueError("Choose Math, Science, or Biology.")
                self.send_json(200, generate_daily_question(grade, subject, load_config()))
                return
            provider = body.get("provider", "")
            messages = body.get("messages", [])
            if provider != "tavily" or not isinstance(messages, list):
                raise ValueError("Choose a supported answer provider and try again.")
            document = body.get("document")
            if document is not None:
                if not isinstance(document, dict):
                    raise ValueError("The attached study file could not be read.")
                filename = document.get("name")
                contents = document.get("text")
                if not isinstance(filename, str) or not isinstance(contents, str) or len(contents) > 8000:
                    raise ValueError("Study files must contain readable text and stay under 8,000 characters.")
                # Uploaded file text is transient request data and is never written to chat history.
                document = {"name": filename[:160], "text": contents}
            learning_context = body.get("learning_context")
            education_context = body.get("education_context")
            answer_language = body.get("answer_language", "en")
            if answer_language not in {"en", "hi", "te"}:
                raise ValueError("Choose English, Hindi, or Telugu for the answer language.")
            if learning_context is not None:
                if not isinstance(learning_context, dict):
                    raise ValueError("The selected standard or subject is invalid.")
                grade = learning_context.get("grade")
                subject = learning_context.get("subject")
                if type(grade) is not int or not 1 <= grade <= 10 or not isinstance(subject, str) or subject not in {"Math", "Science", "Biology"}:
                    raise ValueError("Choose a standard from 1 to 10 and a supported subject.")
                learning_context = {"grade": grade, "subject": subject}
            if education_context is not None:
                if learning_context is not None or not isinstance(education_context, dict):
                    raise ValueError("Choose either Kids Learning or Higher Education for this question.")
                stage = education_context.get("stage")
                subject = education_context.get("subject")
                allowed_stages = {"Undergraduate", "Postgraduate", "Professional or other higher education"}
                allowed_subjects = {"Mathematics", "Physics", "Chemistry", "Biology", "Computer science", "Engineering", "Business and economics", "Humanities and social sciences", "Other"}
                if not isinstance(stage, str) or stage not in allowed_stages or not isinstance(subject, str) or subject not in allowed_subjects:
                    raise ValueError("Choose a valid higher education level and subject area.")
                education_context = {"stage": stage, "subject": subject}
            result = generate_answer(provider, messages, load_config(), document, learning_context, education_context, answer_language)
            self.send_json(200, result)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except Exception:
            self.send_json(502, {"error": "The study assistant could not get an answer. Check the server terminal for details."})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8508"))
    server = ThreadingHTTPServer(("0.0.0.0", port), StudyAssistantHandler)
    print(f"Study Assistant: http://localhost:{port}")
    server.serve_forever()
