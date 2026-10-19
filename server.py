"""Local Study Assistant server. API keys stay on the server, never in browser code."""

from __future__ import annotations

import hashlib
import json
import os
import re
import traceback
import uuid
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from agents import rag, supervisor
from study_assistant.services import answers as _answer_service
from study_assistant.config import load_config, configured_providers
from study_assistant.services.answers import (
    latest_question, recent_learning_dialogue, relevant_note_excerpt,
    MAX_TAVILY_QUERY_LENGTH, K12_EDUCATION_DOMAINS, SYSTEM_INSTRUCTIONS,
)
from study_assistant.providers.tavily import request_json, tavily_search, relevant_images
from study_assistant.services.study_plans import generate_plan_answer
from study_assistant.storage.pdf_indexes import (
    PDF_INDEX_TTL_SECONDS, MAX_ACTIVE_PDF_INDEXES, PDF_INDEXES, PDF_INDEXES_LOCK,
    store_pdf_index, get_pdf_index, delete_pdf_index,
)

ROOT = Path(__file__).resolve().parent
STATIC_ASSETS = {"index.html", "styles.css", "live.css", "app.js"}
SOURCE_STOP_WORDS = {"the", "and", "for", "from", "with", "about", "what", "when", "where", "how", "why", "latest", "recent", "new", "student", "students", "standard", "school", "resource", "resources", "indian", "published", "last", "days", "today", "search", "technology"}


def source_topic_terms(text: str) -> set[str]:
    return {
        token.casefold()
        for token in re.findall(r"[\w]+", text, flags=re.UNICODE)
        if len(token) > 1 and token.casefold() not in SOURCE_STOP_WORDS
    }


def source_matches_topic(item: dict, topic: str) -> bool:
    """Require a result title, URL, or summary to share a meaningful topic term."""
    terms = source_topic_terms(topic)
    if not terms:
        return True
    text = " ".join(str(item.get(key, "")) for key in ("title", "url", "content", "summary"))
    matched = terms & source_topic_terms(text)
    return len(matched) >= min(2, len(terms))




















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
        relevance_topic = search_text or section["query"]
        if not source_matches_topic(item, relevance_topic):
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


def generate_answer(*args, **kwargs):
    """Compatibility wrapper that keeps server-level Tavily overrides injectable."""
    kwargs["search"] = tavily_search
    return _answer_service.generate_answer(*args, **kwargs)



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
        for result in data.get("results", [])
        if isinstance(result, dict)
        and isinstance(result.get("url"), str)
        and result["url"].startswith(("https://", "http://"))
        and source_matches_topic(result, topic)
    ]
    sources = sources[:3]
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
            self.send_json(200, {
                "providers": providers,
                "preferred": "tavily",
                "planner_provider": "groq" if config.get("GROQ_API_KEY") else None,
            })
            return

        relative = self.path.split("?", 1)[0].lstrip("/") or "index.html"
        if relative not in STATIC_ASSETS:
            self.send_error(404)
            return
        target = ROOT / relative
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
        route = urlsplit(self.path)
        if route.path == "/api/pdf-index":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > rag.MAX_PDF_BYTES:
                    raise ValueError("Choose a PDF file that is 200 MB or smaller.")
                if self.headers.get_content_type() != "application/pdf":
                    raise ValueError("Upload a PDF file to index course material.")
                pdf_bytes = self.rfile.read(length)
                if len(pdf_bytes) != length:
                    raise ValueError("The PDF upload did not finish. Please try again.")
                filename = parse_qs(route.query).get("filename", ["course-material.pdf"])[0]
                index = rag.build_index(pdf_bytes, filename)
                index_id = store_pdf_index(index)
                self.send_json(200, {
                    "id": index_id,
                    "name": index["file_name"],
                    "passages": len(index["chunks"]),
                })
            except (ValueError, UnicodeDecodeError) as error:
                self.send_json(400, {"error": str(error)})
            except Exception:
                self.send_json(502, {"error": "I could not index this PDF. Check that it is readable and try again."})
            return

        if route.path not in {"/api/chat", "/api/daily-question", "/api/discovery"}:
            self.send_error(404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 64_000:
                raise ValueError("The message is empty or too large.")
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if route.path == "/api/discovery":
                kind = body.get("kind", "")
                query = body.get("query", "")
                if not isinstance(query, str) or len(query) > 180:
                    raise ValueError("Keep a technology search under 180 characters.")
                self.send_json(200, search_discovery_section(kind, query, load_config()))
                return
            if route.path == "/api/daily-question":
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
            agent_mode = body.get("agent_mode", "Automatic")
            quiz_format = body.get("quiz_format", "Mixed")
            planning_details = body.get("planning_details", {})
            if agent_mode not in supervisor.MODE_TO_AGENT:
                raise ValueError("Choose Automatic, Tutor Agent, Quiz Agent, or Study Planner Agent.")
            if quiz_format not in supervisor.quiz_agent.QUESTION_TYPES:
                raise ValueError("Choose a supported quiz question format.")
            if not isinstance(planning_details, dict):
                raise ValueError("The study-planning details are invalid.")
            question = latest_question(messages)
            selected_agent = supervisor.route_request(question, agent_mode, messages)
            plan_uses_document = selected_agent == "planner" and supervisor.study_planner_agent.requests_document(question)
            document = body.get("document")
            if document is not None:
                if not isinstance(document, dict):
                    raise ValueError("The attached study file could not be read.")
                filename = document.get("name")
                contents = document.get("text")
                allowed_extensions = {".txt", ".md", ".csv", ".json"}
                if not isinstance(filename, str) or Path(filename).suffix.lower() not in allowed_extensions:
                    raise ValueError("Attach a TXT, Markdown, CSV, or JSON study file.")
                if not isinstance(contents, str) or not contents.strip() or "\x00" in contents:
                    raise ValueError("The selected study file is empty or has no readable text.")
                if "\ufffd" in contents:
                    raise ValueError("The selected text file has invalid text encoding. Save it as UTF-8 and upload it again.")
                if len(contents.encode("utf-8")) > 80_000:
                    raise ValueError("Text files must be 80,000 bytes or smaller.")
                if len(contents) > 8000:
                    raise ValueError("Study files must contain readable text and stay under 8,000 characters.")
                if Path(filename).suffix.lower() == ".json":
                    try:
                        json.loads(contents)
                    except json.JSONDecodeError:
                        raise ValueError("The JSON study file is malformed. Correct it or save it as TXT or Markdown.") from None
                # Uploaded file text is transient request data and is never written to chat history.
                document = {"name": filename[:160], "text": contents}
            pdf_index_id = body.get("pdf_index_id")
            source_passages = []
            document_source_only = False
            planning_document = document if plan_uses_document else None
            use_pdf = pdf_index_id is not None and (selected_agent != "planner" or plan_uses_document)
            if use_pdf:
                if body.get("pdf_consent") is not True:
                    raise ValueError("Enable the course-material consent box before sending selected PDF passages to an answer provider.")
                if not isinstance(pdf_index_id, str) or len(pdf_index_id) != 32:
                    raise ValueError("The selected PDF is no longer available. Upload it again.")
                pdf_index = get_pdf_index(pdf_index_id)
                if pdf_index is None:
                    raise ValueError("The selected PDF has expired from this session. Upload it again.")
                source_passages = rag.retrieve_passages(pdf_index, question)
                if not source_passages and selected_agent != "planner":
                    raise ValueError(f"I could not find a relevant passage in {pdf_index['file_name']}. Try asking with terms from the PDF.")
                retrieved_document = {
                    "name": pdf_index["file_name"],
                    "text": rag.format_passages(source_passages) if source_passages else "",
                }
                if document is not None:
                    retrieved_document["text"] += "\n\n" + document["text"]
                document = retrieved_document
                document_source_only = True
                if plan_uses_document:
                    planning_document = document
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
            config = load_config()
            provider_images = []

            def answer_with_provider(prompt: str) -> str:
                result = generate_answer(
                    provider,
                    [{"role": "user", "text": prompt}],
                    config,
                    document,
                    learning_context,
                    education_context,
                    answer_language,
                    document_source_only,
                )
                provider_images[:] = result.get("images", [])
                return result["answer"]

            def answer_with_groq(prompt: str) -> str:
                return generate_plan_answer(
                    prompt,
                    question,
                    config,
                    has_document=planning_document is not None,
                )

            routed = supervisor.dispatch(
                question,
                answer_with_provider,
                mode=agent_mode,
                history=messages,
                quiz_format=quiz_format,
                planning_details=planning_details,
                planner_answer=answer_with_groq,
                planning_document=planning_document,
                answer_language={"en": "English", "hi": "Hindi", "te": "Telugu"}[answer_language],
            )
            result = {"answer": routed["text"], "images": provider_images}
            if source_passages:
                citations = "; ".join(rag.source_labels(source_passages))
                result["answer"] += f"\n\nSources: {citations}"
            self.send_json(200, result)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except Exception as error:
            print(f"Chat request failed with {type(error).__name__}; stack follows:", flush=True)
            traceback.print_tb(error.__traceback__)
            self.send_json(502, {"error": "The study assistant could not get an answer. Check the server terminal for details."})

    def do_DELETE(self) -> None:
        route = urlsplit(self.path)
        if route.path != "/api/pdf-index":
            self.send_error(404)
            return
        index_id = parse_qs(route.query).get("id", [""])[0]
        if index_id:
            delete_pdf_index(index_id)
        self.send_json(200, {"deleted": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8508"))
    server = ThreadingHTTPServer(("0.0.0.0", port), StudyAssistantHandler)
    print(f"Study Assistant: http://localhost:{port}")
    server.serve_forever()
