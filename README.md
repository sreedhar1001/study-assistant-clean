# Study Assistant

Study Assistant offers calm, direct explanations, practice prompts, and study planning for school and higher education learners. The web app sends questions through `server.py`; provider keys stay on the server and are never included in browser code. Tutor and quiz answers use Tavily. General study plans use Groq without web search; Tavily is added only when a plan explicitly needs current information.

The backend keeps `server.py` as the HTTP entry point and compatibility layer. Configuration is in `study_assistant/config.py`, Tavily transport and image normalization are in `study_assistant/providers/tavily.py`, answer prompt construction is in `study_assistant/services/answers.py`, and the main server's bounded in-memory PDF index store is in `study_assistant/storage/pdf_indexes.py`. `agents/supervisor.py` routes work to the individual tutor, quiz, and planner modules and returns an `{agent, text}` response. Both the web API and Streamlit interface continue to call through the server adapter so the existing request flow and test seams stay stable.

## Run locally

Set `TAVILY_API_KEY` and `GROQ_API_KEY` in local `.env` or server environment secrets. `.env.example` contains placeholders only. Then run `python server.py` and open `http://localhost:8508`.

Install the Tavily client with `pip install -r requirements.txt`.

To run the Streamlit interface locally, install the requirements and start it with `streamlit run app.py`. It uses Tavily for tutor and quiz answers and Groq for study plans. The default Groq model is `openai/gpt-oss-20b`; set `GROQ_MODEL` to override it.

The Streamlit interface includes automatic routing and manual Tutor, Quiz, and Study Planner agent choices. Quiz mode can create multiple-choice and short-answer practice and evaluate a learner's next response. Planner mode accepts subjects, a goal, daily study time, and an optional deadline. Conversation history stays in Streamlit session state.

Drag and drop a course PDF into the main website sidebar or the Streamlit sidebar to use document-grounded answers or plans. Uploads are limited to 200 MB; indexing also limits PDFs to 120 pages and 600 passages. The app extracts page text, chunks it with page labels, creates local multilingual embeddings with FastEmbed, and retrieves relevant passages for each question. PDF indexes are kept in memory (the main server expires them after one hour) and are not written to disk. Before a document-based response, the learner must enable the consent checkbox; for study plans, retrieved passages go to Groq, while other agents use Tavily. A PDF is used for a plan only when the learner asks for it. The first upload downloads the embedding model. Scanned PDFs without selectable text need OCR before upload; OCR is not included.

Run the offline agent and provider regression tests with `python -m unittest discover -s tests -v`. These tests mock Tavily and do not make API requests.

The server reads `.env` and `.env.example` at request time and does not serve hidden files. Tutor and quiz requests are sent to Tavily, which supplies the answer and search results. Planner requests use Groq to generate a validated day-by-day schedule; Tavily search is used only when the learner asks for current or recent information. Chat answers omit URLs and links unless the learner asks for them. API use may incur charges. The local config filenames are ignored by Git; do not put real keys in `.env.example`, browser code, or chat.

The chat can attach TXT, Markdown, CSV, or JSON study files up to 8,000 characters. Answers use question-related excerpts from the attached file as the primary source, respond to the learner's question, and explain the relevant reasoning. Tavily search queries have a 1,500-character limit, so only matching excerpts that fit are sent after the learner confirms. File text is kept out of saved chat history.

The Kids Learning section offers separate Maths, Science, and Biology searches for Standards 1–10 only. Learners can type a question; its answer follows the selected standard and subject and stays within Standard 10. Relevant Tavily image results appear when available. The daily question search uses age-appropriate primary and secondary sources, excludes higher-education material, and caches one question per standard, subject, and date in the browser.

The Higher Education section lets learners select an academic stage and subject area, then ask a question for a level-matched explanation. Relevant Tavily image results appear when available. Chat answers do not include raw URLs or links unless requested.

Technology Discovery has separate searches for technology news, new innovations, recent research papers, and advanced technology. Searches use the past-seven-days window, omit results without a verifiable recent publication date, show dates and relevant images where available, and cache results for that section, query, and day. Searches start only when selected, and may use Tavily API credits. Source links stay folded until opened.

Voice input and read-aloud use browser speech features where supported. Typing remains available as a fallback. Browser speech recognition support and microphone permission vary by browser.

Choose English, Hindi, or Telugu from the answer-language menu. The selection controls answer language, speech recognition, and read-aloud voice. Clicking a microphone button starts listening; after a question is recognized, the app submits it and reads the answer aloud. The relevant section shows listening and microphone errors. Browser support and available voices vary; allow microphone access in the browser or type the question instead.

Each chat answer also has a “Search DuckDuckGo for more” button. It opens a separate DuckDuckGo search only when selected and sends the question, not attached file contents.

## Deploy on Render

This repository includes a Render Blueprint for the Python web service. It runs `server.py`, serves the website and API together, and checks `/api/config` for service health. The server binds to `0.0.0.0` and uses Render's `PORT` environment variable.

1. Push this repository to GitHub or GitLab and sign in to [Render](https://render.com/).
2. In the Render Dashboard, choose **New** ? **Blueprint**, connect this repository, and select the branch to deploy. Render reads `render.yaml` and creates the web service.
3. When prompted, enter `TAVILY_API_KEY` as a secret environment variable. You can also add it under the service's **Environment** settings. Do not put the key in `render.yaml`, source code, or a committed file.
4. Click **Apply** or **Deploy**. Once the deploy succeeds, open the `onrender.com` URL shown on the service page.

The Blueprint uses Render's free plan, which may spin down when idle. If you already created a Render Static Site for this project, create a new Blueprint web service because the app needs its Python API to answer questions.

Render requires web services to listen on `0.0.0.0` and recommends using the `PORT` environment variable. The Blueprint keeps the Tavily credential out of source control using a dashboard-supplied secret. See [Render web services](https://render.com/docs/web-services) and [Render environment variables](https://render.com/docs/configure-environment-variables).
