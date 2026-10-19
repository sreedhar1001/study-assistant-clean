# Study Assistant Memory

This file stores only stable context that will make future work on the study assistant more useful. Keep it short, factual, and up to date. Do not use it as a conversation transcript.

## Project purpose

Create a clear, attractive study assistant that helps learners understand topics, practice skills, and plan their learning, from school through higher education.

## Intended learners

- Audience or age range: Children in Standards 1–10 and higher education learners
- Subjects or learning levels: Maths, Science, and Biology for Standards 1–10; higher education subjects and stages
- Accessibility or language needs: Answer language selector for English, Hindi, and Telugu; browser voice input and read-aloud where supported

## Learning experience

- Preferred explanation style: Clear, supportive, and matched to the learner's level
- Assistant voice: Still is calm and patient. Begin with a one- or two-sentence answer, explain in brief steps, and finish with one short check question or tiny practice task.
- Evidence rule: Use only the supplied search results and attached study file for factual claims; state when they do not cover the answer instead of guessing.
- Answer the specific question directly and in context. Do not provide URLs, clickable links, or source-link lists unless asked.
- Add an optional “Search DuckDuckGo for more” action after chat answers; only open a search when clicked and send the question without attached file contents.
- Keep responses calm and proportionate: answer directly, then explain the relevant reasoning without unnecessary detail.
- Use the selected language (English, Hindi, or Telugu) and its usual writing system; keep wording simple, short, and natural.
- Recheck current claims and publication dates, prioritize primary sources, and state uncertainty instead of presenting stale or unverified information as new.
- When a study file is attached, use it as the primary source and answer the question about its contents; explain gaps rather than inventing details.
- For file-based questions in Kids Learning or Higher Education, use both the file and selected learner context. State when the file is unclear, incomplete, or conflicts with reliable information.
- Practice approach: Use hints and guided steps when helpful; provide direct explanations when requested
- Useful study formats: Summaries, flashcards, quizzes, practice problems, and study plans, as relevant
- Other confirmed preferences: None recorded

## Product decisions

- Name the product Study Assistant and keep the interface clean, attractive, and easy to navigate.
- The web app gets answers through Tavily Search via a local Python server; daily practice cards show their learning sources. The server reads `TAVILY_API_KEY`; never put API keys in browser code.
- `streamlit.py` is a separate sample preview; the API-backed answer flow belongs to the existing web app and its local server.
- The primary website runs from `index.html` and `app.js`, served by `server.py` on port 8508; `app.py` is the separate Streamlit interface.
- Save study history only in the learner's browser using local storage.
- Allow TXT, Markdown, CSV, and JSON notes as transient chat attachments, with explicit confirmation before sending their contents to Tavily.
- Support selectable-text PDF course material up to 200 MB with local FastEmbed retrieval, page citations, and explicit consent before sending retrieved passages to Tavily. Keep main-server PDF indexes in memory with an expiry; do not write them to disk.
- Tavily limits each search query to 1,500 characters; send confirmed, question-relevant file excerpts that fit, and be clear that omitted file text was not searched.
- Include a separate Kids Learning section with Standards 1–10 only, separate Maths, Science, and Biology search options, and one Tavily-sourced daily question per standard, subject, and day.
- Let kids type their own questions; use the selected standard and subject to guide answers, and never go above Standard 10.
- Include a separate Higher Education section with stage and subject selectors.
- Higher Education answers should use precise terminology with brief definitions, worked calculation steps, and common-mistake notes. For graded assignments, coach with hints and methods instead of completing the submission.
- Show a small number of relevant real Tavily images for Kids and Higher Education answers when available; do not show raw image URLs unless asked.
- Add separate user-triggered daily search tools for technology news, innovations, recent research papers, and advanced technology; show recent dates and images, cache results per section/query/day, and avoid surprise API usage.
- Offer browser voice input and read-aloud controls for chat and each learning/discovery section. A recognized spoken question submits automatically and its answer is read aloud; show visible status and keep typing as a fallback.
- Voice errors should explain whether speech was not detected, the microphone is missing or blocked, recognition is disabled, or the browser could not connect.
- Keep kids-section answers and sources at or below Standard 10; exclude college and university material.
- For Kids Learning, use the selected Indian Standard and subject, NCERT-style sequencing, short age-appropriate language, everyday examples, and child-safe content. Give one hint and one guiding question for practice; reveal the answer only when asked or after two clearly wrong attempts, tracked from recent chat turns.

## Current priorities

- Keep the browser app focused on learning, and make clear that prompts and daily-question searches go to Tavily. Browser history stays local to each browser.

## Important constraints

- Protect learner privacy; never store credentials or sensitive student records here.
- Support learning and academic integrity; do not help learners misrepresent work or bypass assessment rules.

## Update rules

- Add information only when it is confirmed and likely to matter in future sessions.
- Record decisions with enough context to explain why they were made.
- Remove or revise details when they become outdated.
- Leave unknown preferences marked as unspecified; do not guess or infer sensitive traits.
