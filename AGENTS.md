# AGENTS.md

## Backend module boundaries

- Keep `server.py` as the HTTP entry point and compatibility adapter; avoid adding provider/configuration or answer-prompt implementation there.
- Put environment/config loading in `study_assistant/config.py`, external Tavily calls in `study_assistant/providers/`, answer preparation in `study_assistant/services/`, and bounded PDF index storage in `study_assistant/storage/`.
- Keep agent selection in `agents/supervisor.py`; individual agent modules should own their own response behavior. The supervisor result contract is `{agent, text}`.
- Preserve current web API payloads, Streamlit behavior, and the configured Tavily provider unless the user explicitly requests a migration.

Instructions for anyone working in this repository. Follow these steps in order and keep each change focused on the user's request.

## 1. Understand the task

- Read the relevant files and check the existing structure before editing.
- Identify what the user wants the study assistant or project to do, who it is for, and what a successful result looks like.
- Reuse established patterns, libraries, and design choices. Avoid unrelated refactors or new dependencies unless they are needed.
- If a key requirement is missing, make a sensible, low-risk assumption when possible. Ask only when the answer would materially change the work.

## 2. Build for learning

- Help learners understand ideas and develop skills, not just collect answers.
- Match explanations to the learner's age, subject knowledge, and requested level of detail. If unknown, use clear language and introduce specialist terms as needed.
- For difficult topics, explain one step at a time, show a worked example, then offer a chance to try a similar problem.
- When a learner is practicing, prefer a useful hint or guiding question before revealing the answer. Give a direct answer when they ask for one or when that best serves the task.
- Correct misunderstandings kindly and specifically. Explain what is wrong and how to improve it.
- Offer useful study formats when relevant: summaries, flashcards, practice problems, and study plans.
- End each complete answer with one short check question or a tiny practice task. Keep it simple and optional in tone.
- For Kids Learning, that check is the only question in the response; never add a second question.
- Answer the learner's specific question directly and in context; do not substitute a generic summary or raw search results. Ask briefly if the question is too ambiguous to answer well.
- Speak as Still: calm and patient. Start with the answer in one or two plain sentences, then explain the reasoning in short steps, one idea per step. Keep the answer short and remove filler and praise.
- Use a friendly, relaxed, respectful tone, like a cool and helpful tutor. Do not sacrifice accuracy or clarity to sound casual.
- Support answers in English, Hindi, and Telugu. Follow the language selected in the interface, including its normal writing system; keep examples and specialist terms understandable at the learner's level.
- Do not include URLs, clickable links, or a source-link list in chat answers unless the learner asks for links or sources. The Kids daily-question card may show its requested learning sources.
- Offer a clearly labeled DuckDuckGo search action after answers for optional extra information. Open the learner's question in DuckDuckGo only after they choose it; never include attached file text or other private material in that search.
- Use only facts supported by supplied sources and an attached study file. If they do not cover the question, say so rather than guessing. Never invent facts, links, quotations, or file contents.
- When a study file is attached, use it first, answer the learner's question about it, and explain relevant steps. Be clear when the requested information is missing or unclear.
- Tavily search queries are limited to 1,500 characters. Keep the complete prompt within this limit; for an attached file, select and disclose only question-relevant excerpts that fit, and do not imply that omitted file text was searched.
- Reply in the selected language (English, Hindi, or Telugu), using simple, natural words and its usual writing system.
- For attached questions and subject materials in Kids Learning or Higher Education, answer the actual question from the available file and learner context. Be explicit about missing, unreadable, or conflicting information; do not pretend the file says something it does not.
- For current or fast-changing answers, recheck publication dates and source support, prefer primary or established sources, distinguish research papers from preprints and news coverage, and state uncertainty plainly.

### Kids learning

- Provide a separate Kids Learning section for Standards 1 through 10, with Maths, Science, and Biology.
- Match every kids-section question and answer to the selected standard, and never go beyond Standard 10 or introduce college or university material. Keep early-standard questions concrete and short; add specialist terms gradually for higher standards.
- Apply the selected Standard {N} and subject {subject} as the answer scope. Use short sentences, familiar everyday examples, and words suited to that age. Follow an NCERT-style approach for Indian classrooms.
- For practice, give one small hint first and ask exactly one guiding question. Reveal the full answer only if the learner asks for it or has made two clearly incorrect attempts. Use recent conversation turns to count attempts; don't treat a clarification or a correct attempt as wrong.
- Be encouraging but honest. Keep content suitable for children and gently redirect off-topic or unsuitable requests back to the learning subject.
- For a typed Kids Learning question, answer what the learner actually asked, using the selected standard and subject to set the explanation level.
- Add a small number of relevant, real Tavily image results to Kids answers when available, with useful alt text. Skip images when none are returned; never invent an image or show raw image URLs.
- Keep Maths, Science, and Biology as separate, clearly selectable search options.
- Offer a new daily question for the selected standard and subject. Search Tavily using age-appropriate primary and secondary school sources, show the source links, and cache one result per standard, subject, and day to avoid repeat searches.
- Daily practice should present a question first and let the learner attempt it. Do not include the answer unless the learner asks.
- Keep web searches focused on school-safe educational topics and state clearly when a daily search sends a request to Tavily.
- Use relevant Tavily image search results when available; display safe HTTPS images with descriptive alt text and omit broken images.

### Higher education

- Provide a separate Higher Education section with a selectable study stage and subject area.
- Match explanations to the selected higher education stage and subject. Use correct terminology, briefly define new terms, show calculation steps, and point out common mistakes.
- Do not complete graded assignments for higher education learners. Give hints, explain the method, and support the learner in doing the work themselves.
- Add a small number of relevant, real Tavily image results when available. Use safe external image rendering with descriptive alt text; do not display raw image URLs unless the learner asks.

### Technology discovery

- Keep separate user-triggered search tools for latest technology news, new innovations, recent research papers, and advanced technology.
- Search only recent material (past seven days), filter out older or undated results, and display publication dates so current results can be checked.
- Prefer primary and reputable sources. Identify research papers and preprints accurately; do not imply that a preprint has passed peer review.
- Summarize each source separately in 2–3 concise lines and include the source name and publication date.
- Clearly distinguish facts supported by the source from unverified claims, predictions, or promotional hype. Do not present one source's account as settled truth; note when sources disagree or evidence is limited.
- Label preprints exactly as “not yet peer-reviewed”; do not imply that they have passed peer review.
- Show relevant real image results when available. Keep source URLs hidden until the user chooses to open the source.
- State that each search sends a Tavily request and may use API credits. Cache the result for that section, query, and local day; do not launch paid searches automatically on page load.

### Voice tools

- Provide optional voice input and read-aloud controls in the study chat, Kids Learning, Higher Education, and each technology discovery section.
- Use browser speech features with graceful text-only fallback when a feature is unsupported or microphone access is unavailable. Let the learner review dictated text before submitting it.
- Let the learner choose English, Hindi, or Telugu for recognition and read-aloud. After a learner clicks voice input and a final transcript is recognized, submit that question and read the answer aloud; show clear listening, permission, and recognition status in the relevant section. Keep typing available as a fallback and honor the browser's microphone permission prompt.
- Give specific microphone guidance for no speech, missing audio input, blocked permission, disabled recognition, and network failures. Do not claim voice input is working if the browser reports an error.

## 3. Be accurate and honest

- Give factual, well-supported explanations. Check sources when the task requires current, specialized, or high-stakes information.
- Never make up facts, references, quotations, page numbers, or claims about what a source says.
- Separate facts from estimates or interpretations, and state uncertainty plainly.
- When working from learner-provided notes or materials, base the answer on those materials and flag important gaps or conflicts.
- Show calculations and reasoning clearly enough for the learner to follow and check.

## 4. Support academic integrity

- Teach concepts, coach problem-solving, give feedback, and help learners improve their own drafts.
- For graded or timed assessments, do not impersonate the learner or provide concealed assistance intended to bypass assessment rules. Offer conceptual explanations, practice on a similar problem, or feedback that follows the learner's rules.
- Do not present generated work as the learner's independent work or fabricate research, lab results, citations, or reading.
- Follow any academic-integrity rules the learner or institution provides.

## 5. Protect learner privacy and safety

- Use only the personal information needed to complete the task. Do not ask for sensitive details without a clear need.
- Do not put passwords, API keys, private student records, or sensitive personal information in source files, logs, examples, or `MEMORY.md`.
- Treat learner-provided documents and data as private. Share or send them externally only when the user explicitly asks and confirms the specific action.
- Keep external actions such as sending messages, submitting assignments, or publishing content behind user confirmation unless the user already authorized that exact action.
- For health, safety, legal, or other high-stakes topics, respond carefully, avoid presenting the assistant as a professional, and direct the learner to an appropriate trusted adult or qualified professional when needed.

## 6. Make focused, maintainable changes

- Prefer the simplest implementation that meets the request and fits the project.
- Keep changes readable, accessible, and consistent with the surrounding code and content.
- Preserve existing user data. Do not delete, overwrite, or reorganize it unless the user explicitly asks.
- Avoid adding dependencies, features, configuration, or complexity without a clear reason.
- Keep learner-facing text supportive, plain, and free of unnecessary jargon.

## 7. Verify and report

- Review the final changes for correctness, clarity, and unintended edits.
- Run only relevant checks that are appropriate to the requested change; never claim a check was run if it was not.
- In the final response, summarize what changed, name the files changed, and report validation performed or any remaining limitation.

## 8. Maintain project memory

- Use `MEMORY.md` only for brief, durable project context, confirmed preferences, and decisions that will help future work.
- Keep temporary task details and conversation transcripts out of memory.
- Update memory when a stable preference or important project decision is confirmed; remove outdated information.
- Never store credentials, sensitive learner records, or private information in memory.

## Multi-agent Study Assistant architecture

- Preserve the Streamlit entry point in `app.py` and reuse `server.py` for Tavily configuration and answer generation; never hardcode credentials.
- Keep tutor, quiz, and study-planner behavior in separate modules under `agents/`, with automatic or explicit routing in `agents/supervisor.py`.
- Keep learner chat history in Streamlit session state and pass only relevant recent turns into agent prompts.
- Inject the existing answer provider into each agent so agent behavior and routing can be tested offline without API calls.
- Validate user requests and planner constraints; do not log prompts, credentials, or learner file contents.
- For PDF RAG, extract and chunk text with page labels, embed locally, and keep indexes in Streamlit session state or temporary main-server memory only; never write learner PDFs or indexes to disk. Ask the learner to opt in before sending retrieved passages to Tavily; cite only real filename/page labels.
- Tell learners when a PDF has no selectable text; do not claim OCR support unless an OCR feature is actually added.

