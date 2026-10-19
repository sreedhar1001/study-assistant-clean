"""A local Streamlit version of the Still study assistant preview."""

from __future__ import annotations

import uuid

import streamlit as st


st.set_page_config(
    page_title="Still — your study space",
    page_icon="✳",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700&display=swap');
      :root { --ink:#303831; --muted:#899087; --green:#648066; --paper:#f8f9f7; }
      html, body, [class*="css"] { font-family:'DM Sans',Arial,sans-serif; }
      .stApp { background:var(--paper); color:var(--ink); }
      [data-testid="stSidebar"] { background:#fff; border-right:1px solid #e9ece8; }
      [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:#596458; }
      h1, h2, h3 { font-family:'Manrope','DM Sans',sans-serif; color:var(--ink); }
      .brand { font:600 22px 'Manrope',sans-serif; letter-spacing:-1px; margin:0 0 1.5rem; }
      .brand-mark { display:inline-grid; place-items:center; width:29px; height:29px; margin-right:8px;
        border-radius:9px 9px 9px 3px; background:#5b795f; color:#fff; font:italic 18px Georgia,serif; }
      .welcome { text-align:center; padding:2.6rem 0 1rem; }
      .welcome-mark { display:grid; place-items:center; width:42px; height:42px; margin:0 auto 18px;
        border:1px solid #e4e9e1; background:#fff; border-radius:14px 14px 14px 4px; color:#6e8a69; font-size:20px; }
      .overline { color:#8b9489; font-size:11px; letter-spacing:2px; font-weight:700; }
      .welcome h1 { font-size:clamp(2.1rem,5vw,3rem); line-height:1.15; letter-spacing:-2px; margin:.4rem 0; }
      .welcome h1 em { color:var(--green); font:italic 400 1em Georgia,serif; }
      .welcome-copy { color:var(--muted); line-height:1.8; margin:.8rem 0 1.8rem; }
      .stButton > button { border-color:#e3e8e1; border-radius:8px; color:#4a5149; background:#fff; }
      .stButton > button:hover { border-color:#b7c7b2; color:#49664d; }
      [data-testid="stChatMessage"] { border:1px solid #ebeee8; border-radius:10px; background:#fff; }
      [data-testid="stChatInput"] { border-color:#dfe6dd; }
      .privacy-note { color:#929a90; font-size:12px; text-align:center; padding-top:1rem; }
      @media(max-width:700px) { .welcome { padding-top:1rem; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def init_state() -> None:
    st.session_state.setdefault("sessions", [])
    st.session_state.setdefault("active_session_id", None)
    st.session_state.setdefault("pending_prompt", None)


def active_session() -> dict | None:
    session_id = st.session_state.active_session_id
    return next(
        (item for item in st.session_state.sessions if item["id"] == session_id),
        None,
    )


def make_reply(prompt: str) -> dict:
    lower = prompt.casefold()
    if "practice" in lower or "quiz" in lower:
        return {"text": "Choose one topic, such as fractions or seasons, and try explaining what you know. I can offer a hint or a worked example."}
    if "season" in lower:
        return {"text": "Earth’s axis is tilted. As Earth orbits the Sun, each hemisphere takes a turn tilting toward it. A tilt toward the Sun brings more direct light and longer days, making that season warmer. Seasons happen mainly because of Earth’s tilt, not because Earth moves much closer to the Sun.", "hint_label": "Try a practice question", "hint": "If your hemisphere tilts away from the Sun, would you expect longer or shorter days?"}
    if "fraction" in lower:
        return {"text": "A fraction describes part of a whole. In ¾, the bottom number (4) tells us the whole is split into four equal parts. The top number (3) tells us we have three of those parts. Imagine a pizza cut into four equal slices: ¾ means three slices.", "hint_label": "Try one yourself", "hint": "A chocolate bar has 8 equal pieces. If you eat 3, what fraction is left?"}
    if "plan" in lower:
        return {"text": "A small study plan: choose one topic, spend 15 minutes reviewing or practicing it, then write down one thing you understand and one question you still have. Adjust the time to fit your day."}
    return {"text": "This local Streamlit preview uses sample lessons for seasons and fractions. For general questions, use the main web study assistant with the configured local answer server."}

def queue_prompt(prompt: str) -> None:
    st.session_state.pending_prompt = prompt


def submit_prompt(prompt: str) -> None:
    prompt = prompt.strip()
    if not prompt:
        return
    session = active_session()
    if session is None:
        session = {"id": str(uuid.uuid4()), "title": prompt[:42], "messages": []}
        st.session_state.sessions.insert(0, session)
        st.session_state.active_session_id = session["id"]
    session["messages"].append({"role": "user", "text": prompt})
    session["messages"].append({"role": "assistant", **make_reply(prompt)})


init_state()

with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-mark">s</span>still</div>', unsafe_allow_html=True)
    if st.button("＋  New study session", use_container_width=True):
        st.session_state.active_session_id = None
        st.rerun()
    st.caption("YOUR SPACE")
    st.markdown("🟢  Study assistant  \n📚  Explore a topic")
    st.caption("RECENT SESSIONS")
    for saved in st.session_state.sessions[:8]:
        if st.button(saved["title"], key=f"session-{saved['id']}", use_container_width=True):
            st.session_state.active_session_id = saved["id"]
            st.rerun()
    st.divider()
    st.caption("◇  A calm place to learn.\n\nYour questions stay in this browser session.")

session = active_session()
if session is None or not session["messages"]:
    st.markdown(
        '<div class="welcome"><div class="welcome-mark">✳</div>'
        '<div class="overline">YOUR STUDY SPACE</div>'
        '<h1>What would you like<br>to <em>understand?</em></h1>'
        '<div class="welcome-copy">Bring a question, a topic, or a half-formed thought.<br>We’ll work through it one step at a time.</div></div>',
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns(3)
    starters = [
        ("Understand an idea", "Explain the seasons in simple steps", col1),
        ("Practice a skill", "Give me a practice question about fractions", col2),
        ("Make a small plan", "Help me make a short study plan", col3),
    ]
    for label, prompt, column in starters:
        with column:
            if st.button(label, key=f"starter-{label}", use_container_width=True):
                queue_prompt(prompt)
                st.rerun()
else:
    for message in session["messages"]:
        with st.chat_message(message["role"], avatar="✳" if message["role"] == "assistant" else None):
            st.markdown(message["text"])
            if message.get("hint"):
                with st.expander(message["hint_label"]):
                    st.write(message["hint"])

st.markdown('<div class="privacy-note">Still is a study companion. Check important facts with your class materials.</div>', unsafe_allow_html=True)
typed_prompt = st.chat_input("Ask anything you’re learning…", max_chars=2000)
prompt_to_send = st.session_state.pending_prompt or typed_prompt
st.session_state.pending_prompt = None
if prompt_to_send:
    submit_prompt(prompt_to_send)
    st.rerun()

