"""Streamlit entry point for the full Study Assistant experience."""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import streamlit as st

from agents import rag, supervisor
from server import generate_answer, generate_daily_question, search_discovery_section
from study_assistant.config import load_config
from study_assistant.services.study_plans import generate_plan_answer


logger = logging.getLogger(__name__)


st.set_page_config(
    page_title="Study Assistant · Still",
    page_icon="✳",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700&display=swap');
      :root { --ink:#303831; --muted:#899087; --green:#648066; --paper:#f8f9f7; }
      html, body, [class*="css"] { font-family:'DM Sans',Arial,sans-serif; color:var(--ink); }
      .stApp { background:var(--paper); }
      [data-testid="stSidebar"] { background:#fff; border-right:1px solid #e9ece8; }
      h1, h2, h3 { font-family:'Manrope','DM Sans',sans-serif; color:var(--ink); letter-spacing:-.4px; }
      [data-testid="stAppViewContainer"] h1, [data-testid="stAppViewContainer"] h2,
      [data-testid="stAppViewContainer"] h3 { color:#303831 !important; }
      .brand { color:#303831 !important; }
      [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
      [data-testid="stSidebar"] [data-testid="stWidgetLabel"],
      [data-testid="stSidebar"] label,
      [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] { color:#303831 !important; }
      [data-testid="stCaptionContainer"] { color:#839080 !important; }
      [data-testid="stSidebar"] [data-testid="stCaptionContainer"] *,
      [data-testid="stSidebar"] [data-testid="stWidgetLabel"] * { color:#596458 !important; opacity:1 !important; }
      [data-testid="stFileUploaderDropzone"] { background:#fff !important; border-color:#dfe6dd !important; }
      [data-testid="stFileUploaderDropzone"] * { color:#303831 !important; }
      [data-testid="stFileUploaderDropzone"] button { background:#fff !important; border-color:#dfe6dd !important; color:#303831 !important; }
      h1 { font-size:clamp(2rem,4vw,3.2rem); line-height:1.12; }
      .brand { font:600 24px 'Manrope',sans-serif; letter-spacing:-1px; margin:.2rem 0 1.4rem; }
      .brand-mark { display:inline-grid; place-items:center; width:30px; height:30px; margin-right:8px; border-radius:10px 10px 10px 3px; background:#5b795f; color:#fff; font:italic 18px Georgia,serif; }
      .overline { color:#839080; font-size:11px; letter-spacing:2px; font-weight:700; }
      .welcome { text-align:center; padding:2.5rem 0 1rem; }
      .welcome-mark { display:grid; place-items:center; width:44px; height:44px; margin:0 auto 18px; border:1px solid #e4e9e1; background:white; border-radius:15px 15px 15px 4px; color:#6e8a69; font-size:20px; }
      .welcome-copy { color:var(--muted); line-height:1.8; margin:.8rem 0 1.7rem; }
      .privacy-note { color:#929a90; font-size:12px; text-align:center; padding-top:1rem; }
      [data-testid="stChatMessage"] { border:1px solid #ebeee8; border-radius:12px; background:#fff; }
      .stButton > button, .stFormSubmitButton > button { border-color:#e3e8e1; border-radius:9px; color:#4a5149; background:#fff; }
      .stButton > button:hover, .stFormSubmitButton > button:hover { border-color:#b7c7b2; color:#49664d; }
      [data-testid="stChatInput"] { border:1px solid #dfe6dd !important; background:#fff !important; }
      [data-testid="stChatInput"] textarea { color:#303831 !important; background:#fff !important; }
      [data-testid="stChatInput"] textarea::placeholder { color:#727b71 !important; opacity:1 !important; }
      .section-card { padding:1rem 1.2rem; border:1px solid #e8ece6; border-radius:14px; background:#fff; margin:.4rem 0 1rem; }
      div[data-testid="stMetric"] { background:#fff; border:1px solid #e8ece6; padding:12px 16px; border-radius:12px; }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_config() -> dict[str, str]:
    """Read server environment config and Streamlit Cloud secrets without displaying them."""
    config = load_config()
    try:
        for key in ("TAVILY_API_KEY", "GROQ_API_KEY", "GROQ_MODEL"):
            value = st.secrets.get(key)
            if value:
                config[key] = str(value)
    except Exception:
        # Local Streamlit runs may have no secrets.toml.
        pass
    return config


def tavily_error_message(error: Exception) -> str:
    """Return a safe, useful provider error without exposing request details."""
    error_name = type(error).__name__
    status_code = getattr(error, "status_code", None)
    if not isinstance(status_code, int):
        status_code = getattr(getattr(error, "response", None), "status_code", None)
    if not isinstance(status_code, int):
        status_code = None

    # Log only the exception type and numeric HTTP status. Never log its text,
    # which can contain request metadata or other sensitive provider details.
    logger.warning("Tavily request failed (type=%s, status=%s)", error_name, status_code)

    if isinstance(error, ValueError):
        return str(error)
    name = error_name.casefold()
    if status_code in (401, 403) or name in {"invalidapikeyerror", "missingapikeyerror"}:
        return "Tavily rejected the API key. Check TAVILY_API_KEY in Streamlit Cloud → App settings → Secrets, then reboot the app."
    if status_code == 429 or "usagelimit" in name or "keylesslimit" in name:
        return "Tavily's rate limit or account quota was reached. Check your Tavily account and try again later."
    if status_code is not None and status_code >= 500:
        return f"Tavily returned a temporary server error (HTTP {status_code}). Try again later."
    if isinstance(error, (TimeoutError, ConnectionError)) or "timeout" in name:
        return "The connection to Tavily timed out. Check the app's outbound connection and try again."
    if "connect" in name or "connection" in name or "network" in name:
        return "The app could not connect to Tavily. Check the app's outbound connection and try again."
    return f"Tavily request failed ({error_name}). Check the Streamlit Cloud app logs for deployment or network details."


def init_state() -> None:
    st.session_state.setdefault("sessions", [])
    st.session_state.setdefault("active_session_id", None)
    st.session_state.setdefault("daily_cache", {})
    st.session_state.setdefault("discovery_cache", {})
    st.session_state.setdefault("pdf_index", None)
    st.session_state.setdefault("text_document", None)


def active_session() -> dict | None:
    session_id = st.session_state.active_session_id
    return next((item for item in st.session_state.sessions if item["id"] == session_id), None)


def start_new_session() -> None:
    st.session_state.active_session_id = None


def load_attachment(uploaded) -> None:
    st.session_state.pdf_index = None
    st.session_state.text_document = None
    if uploaded is None:
        return
    filename = uploaded.name
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    raw = uploaded.getvalue()
    if suffix == "pdf":
        if len(raw) > rag.MAX_PDF_BYTES:
            raise ValueError("PDF files must be 200 MB or smaller.")
        fingerprint = hashlib.sha256(raw).hexdigest()
        previous = st.session_state.get("pdf_index")
        if not previous or previous.get("file_hash") != fingerprint:
            with st.spinner("Reading the PDF and preparing its study passages…"):
                st.session_state.pdf_index = rag.build_index(raw, filename)
        return
    if suffix not in {"txt", "md", "csv", "json"}:
        raise ValueError("Choose a PDF, TXT, Markdown, CSV, or JSON file.")
    if len(raw) > 80_000:
        raise ValueError("Text files must be 80,000 bytes or smaller.")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("Save the study file as UTF-8 and upload it again.") from None
    if not text.strip() or "\x00" in text or len(text) > 8_000:
        raise ValueError("Study files need readable text and must stay under 8,000 characters.")
    if suffix == "json":
        import json
        try:
            json.loads(text)
        except json.JSONDecodeError:
            raise ValueError("The JSON file is malformed. Save it as TXT or Markdown, or correct the JSON.") from None
    st.session_state.text_document = {"name": filename[:160], "text": text}


def submit_question(
    question: str,
    *,
    mode: str,
    language: str,
    quiz_format: str,
    planning_details: dict,
    learning_context: dict | None = None,
    education_context: dict | None = None,
    consent: bool = False,
) -> None:
    question = question.strip()
    if not question:
        st.warning("Type a question first.")
        return
    if len(question) > 2_000:
        st.error("Keep each question under 2,000 characters.")
        return
    config = get_config()
    history = active_session()
    messages = history["messages"] if history else []
    routing_history = [*messages, {"role": "user", "text": question}]
    try:
        selected_agent = supervisor.route_request(question, mode, routing_history)
    except ValueError as error:
        st.error(str(error))
        return
    except Exception:
        st.error("Could not prepare the attached study material. Try a smaller or readable file.")
        return
    if selected_agent != "planner" and not config.get("TAVILY_API_KEY"):
        st.error("Add TAVILY_API_KEY under Streamlit app Settings → Secrets, then restart the app.")
        return
    if selected_agent == "planner" and not config.get("GROQ_API_KEY"):
        st.error("Add GROQ_API_KEY under Streamlit app Settings → Secrets, then restart the app.")
        return
    if history is None:
        history = {"id": str(uuid.uuid4()), "title": question[:42], "messages": []}
        st.session_state.sessions.insert(0, history)
        st.session_state.active_session_id = history["id"]
        messages = history["messages"]
    messages.append({"role": "user", "text": question})
    requests_document = selected_agent != "planner" or supervisor.study_planner_agent.requests_document(question)
    document = None
    source_passages = []
    document_source_only = False
    pdf_index = st.session_state.pdf_index if requests_document else None
    attached_text = st.session_state.text_document if requests_document else None
    if (pdf_index or attached_text) and not consent:
        messages.pop()
        st.error("Check the study-file consent box before sending relevant material to the answer provider.")
        return
    planning_document = None
    try:
        if pdf_index:
            source_passages = rag.retrieve_passages(pdf_index, question)
            if not source_passages and selected_agent != "planner":
                raise ValueError(f"I could not find a relevant passage in {pdf_index['file_name']}. Try using terms from the PDF.")
            document = {"name": pdf_index["file_name"], "text": rag.format_passages(source_passages)}
            document_source_only = True
        elif attached_text:
            document = attached_text
        if selected_agent == "planner" and requests_document:
            planning_document = document
            if planning_document is None:
                raise ValueError("Attach the document you want the plan to use.")
    except ValueError as error:
        messages.pop()
        st.error(str(error))
        return
    except Exception:
        messages.pop()
        st.error("Could not prepare the attached study material. Try a smaller or readable file.")
        return
    images: list[dict] = []
    language_codes = {"English": "en", "हिन्दी": "hi", "తెలుగు": "te"}

    def answer_with_tavily(prompt: str) -> str:
        result = generate_answer(
            "tavily",
            [{"role": "user", "text": prompt}],
            config,
            document,
            learning_context,
            education_context,
            language_codes[language],
            document_source_only,
        )
        images[:] = result.get("images", [])
        return result["answer"]

    def answer_with_groq(prompt: str) -> str:
        return generate_plan_answer(
            prompt,
            question,
            config,
            has_document=planning_document is not None,
        )

    try:
        with st.spinner("Thinking through your question…"):
            result = supervisor.dispatch(
                question,
                answer_with_tavily,
                mode=mode,
                history=messages,
                quiz_format=quiz_format,
                planning_details=planning_details,
                planner_answer=answer_with_groq,
                planning_document=planning_document,
                answer_language=language,
            )
        text = result["text"]
        if source_passages:
            text += "\n\nSources: " + "; ".join(rag.source_labels(source_passages))
        messages.append({"role": "assistant", "text": text, "agent": result["agent"], "images": images, "search_query": question})
    except ValueError as error:
        messages.append({"role": "assistant", "text": str(error), "agent": selected_agent, "images": []})
    except Exception:
        messages.append({
            "role": "assistant",
            "text": "The Study Assistant could not get an answer. Check the API key and try again.",
            "agent": selected_agent,
            "images": [],
        })


def render_history() -> None:
    session = active_session()
    if not session:
        return
    for message in session["messages"]:
        with st.chat_message(message["role"], avatar="✳" if message["role"] == "assistant" else None):
            if message.get("agent"):
                provider = "Groq" if message["agent"] == "planner" else "Tavily Search + answer"
                st.caption(f"{message['agent'].title()} Agent · {provider}")
            st.markdown(message["text"])
            search_query = message.get("search_query")
            if search_query:
                st.link_button("Search DuckDuckGo for more", f"https://duckduckgo.com/?q={quote_plus(search_query)}")
            for item in message.get("images", [])[:3]:
                image_url = item.get("url") if isinstance(item, dict) else None
                alt = item.get("description") or item.get("title") or "Learning image" if isinstance(item, dict) else "Learning image"
                if isinstance(image_url, str) and image_url.startswith("https://"):
                    st.image(image_url, caption=alt)


def show_discovery(kind: str, title: str, description: str, query: str) -> None:
    st.markdown(f"<div class='section-card'><p class='overline'>FRESH WEB SEARCH</p><h3>{title}</h3><p>{description}</p></div>", unsafe_allow_html=True)
    with st.form(f"search-{kind}"):
        topic = st.text_input("Optional topic", value=query, max_chars=180, key=f"query-{kind}")
        search_clicked = st.form_submit_button("Search Tavily")
    cache_key = (kind, topic.strip(), datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat())
    if search_clicked:
        try:
            config = get_config()
            with st.spinner("Searching the past seven days…"):
                st.session_state.discovery_cache[cache_key] = search_discovery_section(kind, topic, config)
        except Exception as error:
            st.error(tavily_error_message(error))
    result = st.session_state.discovery_cache.get(cache_key)
    if result:
        if not result.get("results"):
            st.info("No relevant, dated sources were found for the past seven days.")
        for source in result.get("results", []):
            with st.container(border=True):
                st.markdown(f"**{source['title']}** · {source['published']}")
                st.write(source["summary"])
                if "arxiv.org" in source["url"] or "biorxiv.org" in source["url"]:
                    st.caption("Preprint · not yet peer-reviewed")
                st.link_button("Open source", source["url"])
        for image in result.get("images", [])[:3]:
            if image.get("url", "").startswith("https://"):
                st.image(image["url"], caption=image.get("description") or image.get("title") or "Related image")


init_state()
config = get_config()

with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-mark">s</span>Still</div>', unsafe_allow_html=True)
    st.caption("YOUR SPACE")
    page = st.radio(
        "Study sections",
        ["Study assistant", "Kids learning", "Higher education", "Technology & research"],
        label_visibility="collapsed",
    )
    if st.button("＋  New study session", use_container_width=True):
        start_new_session()
        st.rerun()
    st.caption("COURSE MATERIAL")
    st.caption("PDF uploads: 200 MB max. Text notes: 8,000 characters max.")
    uploaded_file = st.file_uploader("PDF or study notes", type=["pdf", "txt", "md", "csv", "json"], key="course_upload")
    if uploaded_file is not None:
        current_signature = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
        if st.session_state.get("attachment_signature") != current_signature:
            try:
                load_attachment(uploaded_file)
                st.session_state.attachment_signature = current_signature
                st.session_state.file_consent = False
                st.success(f"Attached: {uploaded_file.name}")
            except Exception as error:
                st.session_state.pdf_index = None
                st.session_state.text_document = None
                st.session_state.attachment_signature = None
                st.error(str(error) if isinstance(error, ValueError) else "Could not read that study file.")
    elif st.session_state.get("attachment_signature"):
        st.session_state.pdf_index = None
        st.session_state.text_document = None
        st.session_state.attachment_signature = None
        st.session_state.file_consent = False
    has_attachment = bool(st.session_state.pdf_index or st.session_state.text_document)
    consent = st.checkbox("Allow relevant study-file passages to be sent to the answer provider", disabled=not has_attachment, key="file_consent")
    st.caption("STUDY AGENT")
    mode = st.selectbox("Agent", list(supervisor.MODE_TO_AGENT))
    quiz_format = st.selectbox("Quiz format", ["Mixed", "Multiple choice", "Short answer"])
    language = st.selectbox("Answer language", ["English", "हिन्दी", "తెలుగు"])
    planning_details = {
        "subjects": st.text_input("Plan subjects", max_chars=120, placeholder="Maths, Biology"),
        "goal": st.text_input("Study goal", max_chars=120, placeholder="Review chapters 1–3"),
        "minutes_per_day": st.number_input("Minutes per day", min_value=5, max_value=720, step=5, value=60),
        "deadline": st.text_input("Deadline", max_chars=120, placeholder="Friday"),
        "skill_level": "beginner",
    }
    st.caption("RECENT SESSIONS")
    if st.session_state.sessions and st.button("Clear all", key="clear-sessions"):
        st.session_state.sessions = []
        st.session_state.active_session_id = None
        st.rerun()
    for saved in st.session_state.sessions[:8]:
        if st.button(saved["title"], key=f"session-{saved['id']}", use_container_width=True):
            st.session_state.active_session_id = saved["id"]
            st.rerun()
    st.divider()
    st.caption("◇ A calm place to learn. Your questions stay in this browser session.")


left, right = st.columns([3, 2])
with left:
    st.markdown("🟢 **Learn at your pace**")
with right:
    provider_label = "Selected by agent" if mode == "Automatic" else "Groq" if mode == "Study Planner Agent" else "Tavily Search + answer"
    st.markdown(f"**Answer provider:** {provider_label} · **Language:** {language}")

if not config.get("TAVILY_API_KEY"):
    st.warning("Add TAVILY_API_KEY in Streamlit Cloud → App settings → Secrets to enable tutor, quiz, and research answers.")
if not config.get("GROQ_API_KEY"):
    st.info("Add GROQ_API_KEY in Streamlit Cloud → App settings → Secrets to enable study plans.")


if page == "Study assistant":
    st.markdown('<div class="welcome"><div class="welcome-mark">✳</div><p class="overline">YOUR STUDY SPACE</p><h1>What would you like<br>to understand?</h1><p class="welcome-copy">Bring a question, a topic, or your study file.<br>We’ll work through it one step at a time.</p></div>', unsafe_allow_html=True)
    session = active_session()
    if not session or not session["messages"]:
        cards = st.columns(3)
        prompts = ["Explain a topic in simple steps", "Give me a practice question", "Help me make a short study plan"]
        labels = ["Understand an idea", "Practice a skill", "Make a small plan"]
        for column, label, prompt in zip(cards, labels, prompts):
            with column:
                if st.button(label, key=f"starter-{label}", use_container_width=True):
                    submit_question(prompt, mode=mode, language=language, quiz_format=quiz_format, planning_details=planning_details, consent=consent)
                    st.rerun()
    render_history()
    prompt = st.chat_input("Ask a question or topic · 2,000 characters max", max_chars=2_000)
    if prompt:
        submit_question(prompt, mode=mode, language=language, quiz_format=quiz_format, planning_details=planning_details, consent=consent)
        st.rerun()
    st.markdown('<p class="privacy-note">Still is a study companion. Check important facts with your class materials.</p>', unsafe_allow_html=True)

elif page == "Kids learning":
    st.markdown("<p class='overline'>FOR YOUNG LEARNERS · STANDARDS 1–10</p><h1>A little practice for today</h1><p>Choose a standard and subject. Answers stay within the selected level.</p>", unsafe_allow_html=True)
    grade_col, subject_col = st.columns(2)
    with grade_col:
        grade = st.selectbox("Standard", list(range(1, 11)), format_func=lambda value: f"{value}{'st' if value == 1 else 'nd' if value == 2 else 'rd' if value == 3 else 'th'} standard")
    with subject_col:
        subject = st.selectbox("Subject", ["Math", "Science", "Biology"], format_func=lambda value: "Maths" if value == "Math" else value)
    today_key = (datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat(), grade, subject)
    st.caption("Searches Tavily only when you ask. One result is saved per standard and subject for this day in your session.")
    if st.button("Search today’s question", disabled=today_key in st.session_state.daily_cache):
        try:
            with st.spinner("Searching for an age-matched question and learning sources…"):
                st.session_state.daily_cache[today_key] = generate_daily_question(grade, subject, config)
        except Exception as error:
            st.error(tavily_error_message(error))
    daily = st.session_state.daily_cache.get(today_key)
    if daily:
        st.markdown(f"**{daily['subject']} · Standard {grade} · {daily['topic']}**\n\n{daily['question']}")
        st.caption("Try the question first. The answer is not shown here.")
        for source in daily.get("sources", []):
            st.link_button(source["title"], source["url"])
        for image in daily.get("images", []):
            st.image(image["url"], caption=image.get("description") or "Learning image")
    with st.form("kids-question"):
        kids_question = st.text_input("Ask a question for this standard and subject", max_chars=2_000)
        kids_submit = st.form_submit_button("Ask Still")
    if kids_submit:
        submit_question(kids_question, mode=mode, language=language, quiz_format=quiz_format, planning_details=planning_details, learning_context={"grade": grade, "subject": subject}, consent=consent)
        st.rerun()
    render_history()

elif page == "Higher education":
    st.markdown("<p class='overline'>FOR COLLEGE AND UNIVERSITY LEARNERS</p><h1>Higher education</h1><p>Explore a course concept, get a method, or ask about your selected study file.</p>", unsafe_allow_html=True)
    stage = st.selectbox("Study level", ["Undergraduate", "Postgraduate", "Professional or other higher education"])
    area = st.selectbox("Subject area", ["Mathematics", "Physics", "Chemistry", "Biology", "Computer science", "Engineering", "Business and economics", "Humanities and social sciences", "Other"])
    with st.form("higher-question"):
        higher_question = st.text_input("What would you like to understand?", max_chars=2_000)
        higher_submit = st.form_submit_button("Ask Still")
    if higher_submit:
        submit_question(higher_question, mode=mode, language=language, quiz_format=quiz_format, planning_details=planning_details, education_context={"stage": stage, "subject": area}, consent=consent)
        st.rerun()
    render_history()

else:
    st.markdown("<p class='overline'>FRESH WEB SEARCH · UPDATED WHEN YOU SEARCH</p><h1>Technology, research & new ideas</h1><p>Searches cover the past seven days. Each search sends a Tavily request and may use API credits.</p>", unsafe_allow_html=True)
    show_discovery("technology_news", "Latest technology news", "Recent reporting and announcements", "")
    show_discovery("innovations", "New innovations", "New ideas, products, and inventions", "")
    show_discovery("research_papers", "Research papers", "Recent papers and preprints", "")
    show_discovery("advanced_technology", "Advanced technology", "AI, quantum, robotics, and more", "")

