const form = document.querySelector('#chat-form');
const input = document.querySelector('#prompt-input');
const conversation = document.querySelector('#conversation');
const welcome = document.querySelector('#welcome');
const liveStatus = document.querySelector('#live-status');
const sendButton = form.querySelector('.send-button');
const composerHint = document.querySelector('#composer-hint');
const sessionList = document.querySelector('#session-list');
const providerSelect = document.querySelector('#provider-select');
const answerLanguageSelect = document.querySelector('#answer-language');
const fileInput = document.querySelector('#study-file');
const attachButton = document.querySelector('#attach-file');
const fileStatus = document.querySelector('#file-status');
const removeFileButton = document.querySelector('#remove-file');
const pdfInput = document.querySelector('#course-pdf-input');
const pdfDropzone = document.querySelector('#pdf-dropzone');
const pdfStatus = document.querySelector('#course-pdf-status');
const pdfConsentWrap = document.querySelector('#pdf-consent-wrap');
const pdfConsent = document.querySelector('#pdf-consent');
const removePdfButton = document.querySelector('#remove-pdf');
const agentSelect = document.querySelector('#agent-select');
const quizFormatSelect = document.querySelector('#quiz-format');
const quizAgentSettings = document.querySelector('#quiz-agent-settings');
const plannerAgentSettings = document.querySelector('#planner-agent-settings');
const kidsGradeSelect = document.querySelector('#kids-grade');
const kidsSubjectButtons = [...document.querySelectorAll('.subject-choice')];
const dailyQuestionButton = document.querySelector('#daily-question-button');
const dailyStatus = document.querySelector('#daily-status');
const dailyResult = document.querySelector('#daily-result');
const dailyResultLabel = document.querySelector('#daily-result-label');
const dailyQuestionText = document.querySelector('#daily-question');
const dailyReadButton = document.querySelector('#daily-read-button');
const dailySources = document.querySelector('#daily-sources');
const kidsQuestionForm = document.querySelector('#kids-question-form');
const kidsQuestionInput = document.querySelector('#kids-question');
const kidsAskButton = document.querySelector('#kids-ask-button');
const dailyImages = document.querySelector('#daily-images');
const higherQuestionForm = document.querySelector('#higher-question-form');
const higherQuestionInput = document.querySelector('#higher-question');
const higherStageSelect = document.querySelector('#higher-stage');
const higherSubjectSelect = document.querySelector('#higher-subject');
const higherAskButton = document.querySelector('#higher-ask-button');
const discoveryGrid = document.querySelector('#discovery-grid');
const discoveryStatus = document.querySelector('#discovery-status');
const HISTORY_KEY = 'still-study-history-v1';
const DAILY_CACHE_PREFIX = 'still-kids-daily-v2:';
const DISCOVERY_CACHE_PREFIX = 'study-assistant-discovery-v1:';
const MAX_PROMPT_LENGTH = 2000;
const MAX_FILE_CHARACTERS = 8000;
let sessions = readSessions();
let activeSessionId = null;
let isResponding = false;
let attachedDocument = null;
let attachedPdf = null;
let selectedKidsSubject = 'Math';
let activeVoiceRecognition = null;
function updateAgentSettings() {
  quizAgentSettings.hidden = agentSelect.value !== 'Quiz Agent';
  plannerAgentSettings.hidden = agentSelect.value !== 'Study Planner Agent';
}
agentSelect.addEventListener('change', updateAgentSettings);
updateAgentSettings();
const ANSWER_LANGUAGE_KEY = 'study-assistant-answer-language-v1';
const LANGUAGE_TAGS = { en: 'en-IN', hi: 'hi-IN', te: 'te-IN' };
try {
  const savedLanguage = window.localStorage.getItem(ANSWER_LANGUAGE_KEY);
  if (Object.hasOwn(LANGUAGE_TAGS, savedLanguage)) answerLanguageSelect.value = savedLanguage;
} catch { /* Keep the default English setting when storage is unavailable. */ }
answerLanguageSelect.addEventListener('change', () => {
  try { window.localStorage.setItem(ANSWER_LANGUAGE_KEY, answerLanguageSelect.value); } catch { /* The choice still applies for this page. */ }
});
const DISCOVERY_TOOLS = [
  { kind: 'technology_news', title: 'Latest technology news', subtitle: 'Recent reporting and announcements', icon: '◉', placeholder: 'Search technology news…' },
  { kind: 'innovations', title: 'New innovations', subtitle: 'New ideas, products, and inventions', icon: '✧', placeholder: 'Search new innovations…' },
  { kind: 'research_papers', title: 'Research papers', subtitle: 'Recent papers and preprints', icon: '▤', placeholder: 'Search recent research…' },
  { kind: 'advanced_technology', title: 'Advanced technology', subtitle: 'AI, quantum, robotics, and more', icon: '⌘', placeholder: 'Search advanced technology…' },
];

function readSessions() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(HISTORY_KEY) || '[]');
    return Array.isArray(saved) ? saved.filter((session) => session && typeof session.id === 'string' && Array.isArray(session.turns)) : [];
  } catch {
    return [];
  }
}

function saveSessions() {
  try {
    window.localStorage.setItem(HISTORY_KEY, JSON.stringify(sessions.slice(0, 20)));
  } catch {
    liveStatus.textContent = 'This browser could not save study history. Your current session is still available until you close this page.';
  }
  renderSessions();
}

function renderSessions() {
  sessionList.replaceChildren();
  const clearHistoryButton = document.querySelector('#clear-history');
  clearHistoryButton.disabled = sessions.length === 0 || isResponding;
  sessions.forEach((session) => {
    const row = document.createElement('div');
    row.className = 'session-row';
    const button = document.createElement('button');
    button.className = 'recent-topic';
    button.type = 'button';
    button.textContent = session.title || 'Study session';
    button.title = session.title || 'Study session';
    button.addEventListener('click', () => openSession(session.id));
    const remove = document.createElement('button');
    remove.className = 'delete-session';
    remove.type = 'button';
    remove.textContent = '×';
    remove.title = `Delete ${session.title || 'study session'}`;
    remove.setAttribute('aria-label', remove.title);
    remove.disabled = isResponding;
    remove.addEventListener('click', () => deleteSession(session.id));
    row.append(button, remove);
    sessionList.append(row);
  });
}

function resetDeletedActiveSession() {
  activeSessionId = null;
  conversation.replaceChildren();
  welcome.hidden = false;
}

function deleteSession(id) {
  if (isResponding) return;
  sessions = sessions.filter((session) => session.id !== id);
  if (activeSessionId === id) resetDeletedActiveSession();
  saveSessions();
  liveStatus.textContent = 'Study session deleted from this browser.';
}

document.querySelector('#clear-history').addEventListener('click', () => {
  if (isResponding || sessions.length === 0) return;
  if (!window.confirm('Delete all saved study sessions from this browser? This cannot be undone.')) return;
  sessions = [];
  resetDeletedActiveSession();
  saveSessions();
  liveStatus.textContent = 'All saved study sessions were deleted from this browser.';
});

function renderDiscoveryTools() {
  discoveryGrid.replaceChildren();
  DISCOVERY_TOOLS.forEach((tool) => {
    const card = document.createElement('section');
    card.className = 'discovery-card';
    card.dataset.kind = tool.kind;
    const head = document.createElement('div');
    head.className = 'discovery-card-head';
    const icon = document.createElement('span');
    icon.className = 'discovery-card-icon';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = tool.icon;
    const intro = document.createElement('div');
    const title = document.createElement('h3');
    title.textContent = tool.title;
    const subtitle = document.createElement('p');
    subtitle.textContent = tool.subtitle;
    intro.append(title, subtitle);
    const listen = document.createElement('button');
    listen.className = 'voice-read-button';
    listen.type = 'button';
    listen.dataset.speakSection = tool.kind;
    listen.textContent = '🔊 Listen';
    listen.setAttribute('aria-label', `Read ${tool.title} results aloud`);
    head.append(icon, intro, listen);

    const form = document.createElement('form');
    form.className = 'discovery-search-form';
    form.dataset.discoveryForm = tool.kind;
    const inputField = document.createElement('input');
    inputField.type = 'search';
    inputField.maxLength = 180;
    inputField.placeholder = tool.placeholder;
    inputField.setAttribute('aria-label', `${tool.title} search terms`);
    inputField.dataset.discoveryInput = tool.kind;
    const voice = document.createElement('button');
    voice.className = 'discovery-mic-button';
    voice.type = 'button';
    voice.dataset.voiceFor = inputField.id = `discovery-input-${tool.kind}`;
    voice.textContent = '🎙';
    voice.setAttribute('aria-label', `Speak a ${tool.title} search`);
    const search = document.createElement('button');
    search.className = 'discovery-search-button';
    search.type = 'submit';
    search.textContent = 'Search';
    form.append(inputField, voice, search);

    const status = document.createElement('p');
    status.className = 'discovery-card-status';
    status.setAttribute('aria-live', 'polite');
    const images = document.createElement('div');
    images.className = 'discovery-images';
    const results = document.createElement('div');
    results.className = 'discovery-results';
    card.append(head, form, status, images, results);
    discoveryGrid.append(card);
  });
}

renderDiscoveryTools();

function speakText(text, button) {
  if (!('speechSynthesis' in window) || !text.trim()) {
    showVoiceStatus(button, 'Read aloud is not available in this browser.');
    return;
  }
  if (button?.dataset.speaking === 'true') {
    window.speechSynthesis.cancel();
    button.dataset.speaking = 'false';
    button.textContent = button.dataset.defaultLabel || '🔊 Listen';
    return;
  }
  window.speechSynthesis.cancel();
  document.querySelectorAll('[data-speaking="true"]').forEach((activeButton) => {
    activeButton.dataset.speaking = 'false';
    activeButton.textContent = activeButton.dataset.defaultLabel || '🔊 Listen';
  });
  const utterance = new SpeechSynthesisUtterance(text.slice(0, 5000));
  utterance.lang = LANGUAGE_TAGS[answerLanguageSelect.value] || 'en-IN';
  if (button) {
    button.dataset.speaking = 'true';
    button.textContent = '■ Stop';
    utterance.onend = () => {
      button.dataset.speaking = 'false';
      button.textContent = button.dataset.defaultLabel || '🔊 Listen';
    };
  }
  window.speechSynthesis.speak(utterance);
}

function showVoiceStatus(target, message) {
  const cardStatus = target?.closest('.discovery-card')?.querySelector('.discovery-card-status');
  const status = cardStatus
    || (target?.closest('#kids-learning') && dailyStatus)
    || (target?.closest('#higher-learning') && document.querySelector('#higher-status'))
    || document.querySelector('#main-voice-status');
  if (status) status.textContent = message;
  liveStatus.textContent = message;
}

function startVoiceInput(button, isRetry = false) {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    showVoiceStatus(button, 'Voice input is not supported in this browser. Try Chrome or Edge, or type your question.');
    return;
  }
  if (activeVoiceRecognition) {
    activeVoiceRecognition.stop();
    showVoiceStatus(button, 'Listening stopped.');
    return;
  }
  const target = document.getElementById(button.dataset.voiceFor);
  if (!target) return;
  if (!isRetry) button.dataset.networkRetries = '0';
  const recognition = new Recognition();
  recognition.lang = LANGUAGE_TAGS[answerLanguageSelect.value] || 'en-IN';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  let transcript = '';
  activeVoiceRecognition = recognition;
  button.setAttribute('aria-pressed', 'true');
  button.classList.add('listening');
  showVoiceStatus(target, `Listening in ${answerLanguageSelect.selectedOptions[0].text}. Speak your question now.`);
  recognition.onresult = (event) => {
    transcript = event.results?.[0]?.[0]?.transcript?.trim() || '';
    if (transcript) {
      target.value = transcript;
      target.dispatchEvent(new Event('input', { bubbles: true }));
      showVoiceStatus(target, 'I heard your question. Sending it now…');
    }
  };
  recognition.onerror = (event) => {
    button.dataset.voiceError = 'true';
    button.dataset.voiceErrorCode = event.error || '';
    const messages = {
      'not-allowed': 'Microphone access is blocked. Allow it for this localhost site in your browser settings, then try again.',
      'service-not-allowed': 'This browser has disabled speech recognition. Try Chrome or Edge, or type your question.',
      'no-speech': 'I did not detect speech. Check that your microphone is not muted, then speak after Listening appears.',
      'audio-capture': 'No microphone was detected. Connect a microphone and check that the correct input is enabled in your computer settings.',
      network: 'The browser speech service could not connect. Check your internet connection and try again.',
      aborted: 'Listening stopped before I heard a question. Try again and speak after Listening appears.',
    };
    const message = messages[event.error] || 'I could not hear that. Check your microphone and browser permissions, then try again.';
    showVoiceStatus(target, message);
  };
  recognition.onend = () => {
    if (activeVoiceRecognition === recognition) activeVoiceRecognition = null;
    button.setAttribute('aria-pressed', 'false');
    button.classList.remove('listening');
    if (transcript) {
      const targetForm = target.closest('form');
      if (targetForm) {
        targetForm.dataset.voiceSubmit = 'true';
        targetForm.requestSubmit();
      }
    } else if (button.dataset.voiceErrorCode === 'network' && button.dataset.networkRetries !== '1') {
      button.dataset.networkRetries = '1';
      showVoiceStatus(target, 'Speech service connection failed. Retrying once…');
      window.setTimeout(() => startVoiceInput(button, true), 500);
    } else if (!button.dataset.voiceError) {
      showVoiceStatus(target, 'I did not catch a question. Try speaking again or type it.');
    } else if (button.dataset.voiceErrorCode === 'network') {
      showVoiceStatus(target, 'The browser speech service could not connect. Check your internet connection, try the microphone again, or type your question.');
    }
    button.dataset.voiceError = '';
    button.dataset.voiceErrorCode = '';
  };
  try {
    recognition.start();
  } catch {
    activeVoiceRecognition = null;
    button.setAttribute('aria-pressed', 'false');
    button.classList.remove('listening');
    showVoiceStatus(target, 'Microphone access is unavailable. Check browser permissions or type your question.');
  }
}

document.addEventListener('click', (event) => {
  const voiceButton = event.target.closest('[data-voice-for]');
  if (voiceButton) startVoiceInput(voiceButton);
  const readButton = event.target.closest('[data-speak-section]');
  if (readButton) {
    const card = readButton.closest('.discovery-card');
    const text = [...card.querySelectorAll('.discovery-result')].map((item) => item.innerText).join('. ');
    speakText(text || 'Search this section to hear its latest results.', readButton);
  }
});

function openSession(id) {
  if (isResponding) return;
  const session = sessions.find((item) => item.id === id);
  if (!session) return;
  activeSessionId = id;
  welcome.hidden = true;
  conversation.replaceChildren();
  session.turns.forEach((turn) => addMessage(turn.text, turn.role, { images: turn.images }));
  liveStatus.textContent = 'Saved study session opened.';
}

function getActiveSession() {
  return sessions.find((session) => session.id === activeSessionId);
}

function clearAttachedDocument() {
  attachedDocument = null;
  fileInput.value = '';
  fileStatus.textContent = 'TXT, MD, CSV, or JSON · up to 8,000 characters';
  attachButton.textContent = '＋ Add study file';
  removeFileButton.hidden = true;
}

function setPdfStatus(message, isError = false) {
  pdfStatus.textContent = message;
  pdfStatus.classList.toggle('error', isError);
}

async function removePdfIndex() {
  const oldPdf = attachedPdf;
  attachedPdf = null;
  pdfInput.value = '';
  pdfConsent.checked = false;
  pdfConsent.disabled = true;
  pdfConsentWrap.hidden = true;
  removePdfButton.hidden = true;
  setPdfStatus('');
  if (oldPdf) {
    try { await fetch(`/api/pdf-index?id=${encodeURIComponent(oldPdf.id)}`, { method: 'DELETE' }); } catch { /* The server also expires indexes automatically. */ }
  }
}

async function indexPdf(file) {
  if (!file) return;
  if (!/\.pdf$/i.test(file.name)) {
    setPdfStatus('Choose a PDF file.', true);
    pdfInput.value = '';
    return;
  }
  if (file.size > 200 * 1024 * 1024) {
    setPdfStatus('This file is over 200 MB. Choose a smaller PDF.', true);
    pdfInput.value = '';
    return;
  }
  if (attachedDocument) clearAttachedDocument();
  await removePdfIndex();
  pdfInput.value = '';
  setPdfStatus(`Uploading ${file.name} and creating local embeddings…`);
  pdfDropzone.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(`/api/pdf-index?filename=${encodeURIComponent(file.name)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/pdf' },
      body: file,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not index this PDF.');
    attachedPdf = { id: result.id, name: result.name, passages: result.passages };
    pdfConsent.checked = false;
    pdfConsent.disabled = false;
    pdfConsentWrap.hidden = false;
    removePdfButton.hidden = false;
    setPdfStatus(`${result.name} · ${result.passages} passages indexed for this session.`);
    liveStatus.textContent = 'Your PDF is indexed locally. Allow sharing selected passages before asking a question about it.';
  } catch (error) {
    setPdfStatus(error.message || 'Could not index this PDF. Check the server and try again.', true);
  } finally {
    pdfDropzone.removeAttribute('aria-busy');
  }
}

pdfInput.addEventListener('change', () => indexPdf(pdfInput.files?.[0]));
pdfDropzone.addEventListener('dragover', (event) => {
  event.preventDefault();
  pdfDropzone.classList.add('drag-over');
});
pdfDropzone.addEventListener('dragleave', () => pdfDropzone.classList.remove('drag-over'));
pdfDropzone.addEventListener('drop', (event) => {
  event.preventDefault();
  pdfDropzone.classList.remove('drag-over');
  indexPdf(event.dataTransfer?.files?.[0]);
});
pdfDropzone.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    pdfInput.click();
  }
});
removePdfButton.addEventListener('click', removePdfIndex);

attachButton.addEventListener('click', () => fileInput.click());
removeFileButton.addEventListener('click', clearAttachedDocument);

fileInput.addEventListener('change', async () => {
  const file = fileInput.files?.[0];
  if (!file) return;
  if (attachedPdf) {
    clearAttachedDocument();
    fileStatus.textContent = 'Remove the course PDF before attaching another study file.';
    return;
  }
  if (!/\.(txt|md|csv|json)$/i.test(file.name)) {
    clearAttachedDocument();
    fileStatus.textContent = 'Choose a TXT, Markdown, CSV, or JSON file.';
    return;
  }
  if (file.size > 80000) {
    clearAttachedDocument();
    fileStatus.textContent = 'That file is too large. Choose a smaller text file.';
    return;
  }
  try {
    const text = await file.text();
    if (!text.trim() || text.includes('\0') || text.length > MAX_FILE_CHARACTERS) {
      clearAttachedDocument();
      fileStatus.textContent = text.length > MAX_FILE_CHARACTERS
        ? 'That file is over 8,000 characters. Choose a shorter file.'
        : 'That file has no readable text.';
      return;
    }
    attachedDocument = { name: file.name.slice(0, 160), text };
    fileStatus.textContent = `${attachedDocument.name} · relevant excerpts only`;
    attachButton.textContent = 'Change file';
    removeFileButton.hidden = false;
    liveStatus.textContent = `Attached ${attachedDocument.name}. The file is sent to the relevant answer provider only when you confirm and ask a question about it.`;
  } catch {
    clearAttachedDocument();
    fileStatus.textContent = 'Could not read that file. Try a text, Markdown, CSV, or JSON file.';
  }
});

renderSessions();

async function loadProviderConfig() {
  try {
    const response = await fetch('/api/config');
    if (!response.ok) throw new Error('Local answer server is unavailable.');
    const config = await response.json();
    const providers = Array.isArray(config.providers) ? config.providers : [];
    const providerBadge = document.querySelector('.provider-badge');
    if (providerBadge) {
      providerBadge.textContent = config.planner_provider
        ? 'Tavily answers · Groq study plans'
        : 'Tavily answers · Groq plan key missing';
    }
    [...providerSelect.options].forEach((option) => {
      option.disabled = !providers.includes(option.value);
    });
    if (providers.length) {
      providerSelect.value = providers.includes(config.preferred) ? config.preferred : providers[0];
      liveStatus.textContent = `Answers use ${providerSelect.options[providerSelect.selectedIndex].text}.`;
    } else {
      providerSelect.disabled = true;
      liveStatus.textContent = 'No Tavily key found. Add TAVILY_API_KEY to .env or .env.example, then restart the local server.';
    }
  } catch {
    providerSelect.disabled = true;
    liveStatus.textContent = 'Start the local answer server with python server.py to connect the study assistant.';
  }
}

loadProviderConfig();

function localDayKey() {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

function displayDailyQuestion(result, fromCache = false) {
  dailyResult.hidden = false;
  const subjectLabel = result.subject === 'Math' ? 'Maths' : result.subject;
  dailyResultLabel.textContent = `${subjectLabel} · Standard ${result.grade} · ${result.topic}`;
  dailyQuestionText.textContent = result.question;
  dailyReadButton.onclick = () => speakText(`${dailyResultLabel.textContent}. ${result.question}`, dailyReadButton);
  dailyReadButton.dataset.defaultLabel = '🔊 Listen to question';
  renderImages(dailyImages, result.images || []);
  dailySources.replaceChildren();
  (result.sources || []).forEach((source) => {
    try {
      const url = new URL(source.url);
      if (!['http:', 'https:'].includes(url.protocol)) return;
      const item = document.createElement('li');
      const link = document.createElement('a');
      link.href = url.href;
      link.textContent = source.title || url.hostname;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      item.append(link);
      dailySources.append(item);
    } catch {
      // Skip malformed source links.
    }
  });
  if (!dailySources.children.length) {
    const item = document.createElement('li');
    item.textContent = 'No relevant learning sources were found for this question.';
    dailySources.append(item);
  }
  dailyStatus.textContent = fromCache ? "Today's question is ready." : 'Found a new question and learning sources for today.';
}

function displayDiscoveryResult(card, result, fromCache = false) {
  const resultsBox = card.querySelector('.discovery-results');
  const status = card.querySelector('.discovery-card-status');
  resultsBox.replaceChildren();
  renderImages(card.querySelector('.discovery-images'), result.images || []);
  (result.results || []).forEach((item) => {
    const article = document.createElement('article');
    article.className = 'discovery-result';
    const heading = document.createElement('h4');
    heading.textContent = item.title || 'Recent result';
    const published = document.createElement('time');
    published.textContent = item.published ? `Published: ${item.published}` : 'Publication date not listed';
    const summary = document.createElement('p');
    summary.textContent = item.summary || 'No summary was provided.';
    article.append(heading, published, summary);
    try {
      const url = new URL(item.url);
      if (url.protocol === 'https:') {
        const disclosure = document.createElement('details');
        disclosure.className = 'source-disclosure';
        const prompt = document.createElement('summary');
        prompt.textContent = 'Show source link';
        const link = document.createElement('a');
        link.href = url.href;
        link.textContent = 'Open publication';
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        disclosure.append(prompt, link);
        article.append(disclosure);
      }
    } catch {
      // Keep the result text when a source URL is missing or malformed.
    }
    resultsBox.append(article);
  });
  if (!resultsBox.children.length) {
    const empty = document.createElement('p');
    empty.className = 'discovery-empty';
    empty.textContent = 'No relevant sources with a verifiable date from the past 7 days were found. Try a more specific search.';
    resultsBox.append(empty);
  }
  card.dataset.speakText = (result.results || []).map((item) => `${item.title}. ${item.summary}`).join('. ');
  status.textContent = `Searched ${result.searched_on}${fromCache ? ' · saved for today' : ''}.`;
  discoveryStatus.textContent = `${result.title} is ready.`;
}

discoveryGrid.addEventListener('submit', async (event) => {
  const formEl = event.target.closest('[data-discovery-form]');
  if (!formEl) return;
  event.preventDefault();
  const card = formEl.closest('.discovery-card');
  const kind = formEl.dataset.discoveryForm;
  const voiceSubmit = formEl.dataset.voiceSubmit === 'true';
  delete formEl.dataset.voiceSubmit;
  const query = formEl.querySelector('input').value.trim();
  const day = localDayKey();
  const cacheKey = `${DISCOVERY_CACHE_PREFIX}${day}:${kind}:${encodeURIComponent(query).slice(0, 220)}`;
  try {
    const cached = JSON.parse(window.localStorage.getItem(cacheKey) || 'null');
    if (cached && cached.searched_on === day) {
      displayDiscoveryResult(card, cached, true);
      if (voiceSubmit) speakText(card.dataset.speakText || 'Search complete.', card.querySelector('[data-speak-section]'));
      return;
    }
  } catch {
    // Ignore damaged or unavailable cached data and fetch fresh results.
  }
  const button = formEl.querySelector('.discovery-search-button');
  button.disabled = true;
  card.querySelector('.discovery-card-status').textContent = 'Searching recent reporting and images…';
  discoveryStatus.textContent = 'Searching the selected section. This may use Tavily API credits.';
  try {
    const response = await fetch('/api/discovery', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind, query }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not search this section.');
    try {
      for (let index = window.localStorage.length - 1; index >= 0; index -= 1) {
        const key = window.localStorage.key(index);
        if (key?.startsWith(DISCOVERY_CACHE_PREFIX) && !key.startsWith(`${DISCOVERY_CACHE_PREFIX}${day}:`)) window.localStorage.removeItem(key);
      }
      window.localStorage.setItem(cacheKey, JSON.stringify(result));
    } catch {
      // Continue to display the results if browser storage is unavailable.
    }
    displayDiscoveryResult(card, result);
    if (voiceSubmit) speakText(card.dataset.speakText || 'Search complete.', card.querySelector('[data-speak-section]'));
  } catch (error) {
    card.querySelector('.discovery-card-status').textContent = error.message || 'Could not reach the search service.';
    discoveryStatus.textContent = 'Search failed. Check the server connection and try again.';
  } finally {
    button.disabled = false;
  }
});

dailyQuestionButton.addEventListener('click', async () => {
  const grade = Number(kidsGradeSelect.value);
  const subject = selectedKidsSubject;
  const day = localDayKey();
  const cacheKey = `${DAILY_CACHE_PREFIX}${day}:${grade}:${subject}`;
  try {
    const cached = JSON.parse(window.localStorage.getItem(cacheKey) || 'null');
    if (cached && cached.day === day) {
      displayDailyQuestion(cached, true);
      return;
    }
  } catch {
    // Ignore damaged or unavailable cached data and fetch a fresh question.
  }

  dailyQuestionButton.disabled = true;
  dailyStatus.textContent = 'Searching for today’s question and learning sources…';
  try {
    const response = await fetch('/api/daily-question', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ grade, subject }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not find today’s question.');
    try {
      for (let index = window.localStorage.length - 1; index >= 0; index -= 1) {
        const key = window.localStorage.key(index);
        if (key?.startsWith(DAILY_CACHE_PREFIX) && key !== cacheKey) window.localStorage.removeItem(key);
      }
      window.localStorage.setItem(cacheKey, JSON.stringify(result));
    } catch {
      // A privacy setting or full storage should not prevent showing the fetched result.
    }
    displayDailyQuestion(result);
  } catch (error) {
    dailyStatus.textContent = error.message || 'Could not connect to Tavily. Try again later.';
  } finally {
    dailyQuestionButton.disabled = false;
  }
});

kidsQuestionForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const grade = Number(kidsGradeSelect.value);
  const subject = selectedKidsSubject;
  const question = kidsQuestionInput.value.trim();
  if (!question) {
    dailyStatus.textContent = 'Type a question first, then choose Ask Still.';
    kidsQuestionInput.focus();
    return;
  }
  const speak = event.currentTarget.dataset.voiceSubmit === 'true';
  delete event.currentTarget.dataset.voiceSubmit;
  submitPrompt(question, { input: kidsQuestionInput, learningContext: { grade, subject }, speak });
});

higherQuestionForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const question = higherQuestionInput.value.trim();
  if (!question) {
    liveStatus.textContent = 'Type a question first, then choose Ask.';
    higherQuestionInput.focus();
    return;
  }
  const speak = event.currentTarget.dataset.voiceSubmit === 'true';
  delete event.currentTarget.dataset.voiceSubmit;
  submitPrompt(question, {
    input: higherQuestionInput,
    educationContext: { stage: higherStageSelect.value, subject: higherSubjectSelect.value },
    speak,
  });
});

kidsSubjectButtons.forEach((button) => {
  button.addEventListener('click', () => {
    selectedKidsSubject = button.dataset.subject;
    kidsSubjectButtons.forEach((choice) => {
      const selected = choice === button;
      choice.classList.toggle('selected', selected);
      choice.setAttribute('aria-pressed', String(selected));
    });
    dailyStatus.textContent = `${button.textContent} selected. Search for today’s question when you’re ready.`;
  });
});

function currentTime() {
  return new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(new Date());
}

function renderImages(container, images) {
  container.replaceChildren();
  const figures = (Array.isArray(images) ? images : []).slice(0, 2).flatMap((image) => {
    const rawUrl = typeof image === 'string' ? image : image?.url;
    let parsed;
    try { parsed = new URL(rawUrl); } catch { return []; }
    if (parsed.protocol !== 'https:') return [];
    const figure = document.createElement('figure');
    figure.className = 'learning-image-card';
    const img = document.createElement('img');
    img.src = parsed.href;
    img.alt = (typeof image === 'object' && image.description) || 'Related learning image';
    img.loading = 'lazy';
    img.referrerPolicy = 'no-referrer';
    img.addEventListener('error', () => figure.remove(), { once: true });
    const caption = document.createElement('figcaption');
    caption.textContent = (typeof image === 'object' && image.description) || 'Related learning image';
    figure.append(img, caption);
    return [figure];
  });
  figures.forEach((figure) => container.append(figure));
  container.hidden = figures.length === 0;
}

function addMessage(text, role, options = {}) {
  const row = document.createElement('div');
  row.className = `chat-row ${role}`;
  if (role === 'assistant') {
    const avatar = document.createElement('span');
    avatar.className = 'chat-avatar';
    avatar.setAttribute('aria-hidden', 'true');
    avatar.textContent = '✳';
    row.append(avatar);
  }
  const content = document.createElement('div');
  content.className = 'chat-content';
  const bubble = document.createElement('div');
  bubble.className = 'chat-bubble';
  bubble.textContent = text;
  if (options.streaming) bubble.setAttribute('aria-hidden', 'true');
  const time = document.createElement('time');
  time.className = 'message-time';
  time.dateTime = new Date().toISOString();
  time.textContent = currentTime();
  content.append(bubble);
  if (role === 'assistant' && !options.streaming) {
    const readButton = document.createElement('button');
    readButton.className = 'voice-read-button';
    readButton.type = 'button';
    readButton.textContent = '🔊 Read answer';
    readButton.dataset.defaultLabel = '🔊 Read answer';
    readButton.setAttribute('aria-label', 'Read answer aloud');
    readButton.addEventListener('click', () => speakText(text, readButton));
    content.append(readButton);
  }
  if (role === 'assistant' && options.images?.length) {
    const visuals = document.createElement('div');
    visuals.className = 'chat-visuals';
    renderImages(visuals, options.images);
    if (visuals.children.length) content.append(visuals);
  }
  content.append(time);
  row.append(content);
  conversation.append(row);
  conversation.scrollTop = conversation.scrollHeight;
  return bubble;
}

function addHint(bubble, label, hint) {
  const button = document.createElement('button');
  button.className = 'hint-toggle';
  button.type = 'button';
  button.textContent = `＋ ${label}`;
  const content = document.createElement('div');
  content.className = 'hint-text';
  content.textContent = hint;
  button.setAttribute('aria-expanded', 'false');
  button.addEventListener('click', () => {
    const open = content.classList.toggle('visible');
    button.setAttribute('aria-expanded', String(open));
    button.textContent = open ? '− Hide hint' : `＋ ${label}`;
  });
  bubble.append(button, content);
}

function showTyping() {
  const row = document.createElement('div');
  row.className = 'chat-row assistant typing-row';
  row.setAttribute('aria-hidden', 'true');
  const avatar = document.createElement('span');
  avatar.className = 'chat-avatar';
  avatar.textContent = '✳';
  const bubble = document.createElement('div');
  bubble.className = 'typing-bubble';
  bubble.innerHTML = '<span></span><span></span><span></span>';
  row.append(avatar, bubble);
  conversation.append(row);
  conversation.scrollTop = conversation.scrollHeight;
  liveStatus.textContent = 'Study assistant is responding.';
  return row;
}

function wait(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

async function streamReply(reply, typingRow, searchQuery) {
  typingRow.remove();
  const bubble = addMessage('', 'assistant', { streaming: true });
  const characters = [...reply.text];
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const step = reducedMotion ? characters.length : 4;
  const interval = reducedMotion ? 0 : 15;
  for (let index = 0; index < characters.length; index += step) {
    bubble.textContent += characters.slice(index, index + step).join('');
    conversation.scrollTop = conversation.scrollHeight;
    if (interval) await wait(interval);
  }
  bubble.textContent = reply.text;
  bubble.removeAttribute('aria-hidden');
  const readButton = document.createElement('button');
  readButton.className = 'voice-read-button';
  readButton.type = 'button';
  readButton.textContent = '🔊 Read answer';
  readButton.dataset.defaultLabel = '🔊 Read answer';
  readButton.setAttribute('aria-label', 'Read answer aloud');
  readButton.addEventListener('click', () => speakText(reply.text, readButton));
  bubble.after(readButton);
  const searchButton = document.createElement('button');
  searchButton.className = 'duckduckgo-search-button';
  searchButton.type = 'button';
  searchButton.textContent = 'Search DuckDuckGo for more';
  searchButton.title = 'Opens DuckDuckGo and sends your question only; attached file text is not included.';
  searchButton.addEventListener('click', () => {
    const url = new URL('https://duckduckgo.com/');
    url.searchParams.set('q', searchQuery);
    window.open(url.href, '_blank', 'noopener,noreferrer');
  });
  readButton.after(searchButton);
  if (reply.images?.length) {
    const visuals = document.createElement('div');
    visuals.className = 'chat-visuals';
    renderImages(visuals, reply.images);
    if (visuals.children.length) bubble.after(visuals);
  }
  if (reply.hint) addHint(bubble, ...reply.hint);
  liveStatus.textContent = 'Study assistant replied.';
  return readButton;
}

function isPlannerRequest(prompt) {
  return agentSelect.value === 'Study Planner Agent'
    || (agentSelect.value === 'Automatic' && /\b(study plan|study planner|study schedule|timetable|revision plan|plan my (studies|study|week)|(?:make|create|build|draft) (?:me )?(?:a )?(?:study )?plan|(?:make|create|build) (?:me )?(?:a )?schedule)\b/i.test(prompt));
}

function plannerExplicitlyUsesStudyFile(prompt) {
  return isPlannerRequest(prompt) && /\b(based on|from|using|according to|use)\b.{0,50}\b(pdf|document|uploaded file|attached file|study file|course material|notes)\b|\b(pdf|uploaded document|attached document|uploaded file|attached file|study file|course material)\b.{0,50}\b(plan|schedule|timetable)\b/i.test(prompt);
}

async function submitPrompt(value, options = {}) {
  const prompt = value.trim();
  const sourceInput = options.input || input;
  if (isResponding) return;
  if (!prompt) {
    liveStatus.textContent = 'Type a question or topic to get started.';
    return;
  }
  if (prompt.length > MAX_PROMPT_LENGTH) {
    liveStatus.textContent = `Please keep your question under ${MAX_PROMPT_LENGTH} characters.`;
    composerHint.textContent = `Your question is too long · ${prompt.length}/${MAX_PROMPT_LENGTH}`;
    return;
  }
  if (attachedPdf && (!isPlannerRequest(prompt) || plannerExplicitlyUsesStudyFile(prompt)) && !pdfConsent.checked) {
    liveStatus.textContent = 'Enable the course-material consent box before sending selected PDF passages and your question to an answer provider.';
    pdfConsent.focus();
    return;
  }
  const sendDocument = attachedDocument && (!isPlannerRequest(prompt) || plannerExplicitlyUsesStudyFile(prompt));
  const answerProviderName = isPlannerRequest(prompt) ? 'Groq' : 'Tavily';
  if (sendDocument && !window.confirm(`Send "${attachedDocument.name}" and your question to ${answerProviderName}?`)) {
    liveStatus.textContent = 'The file was not sent. You can remove it or try again when ready.';
    return;
  }
  const documentForRequest = sendDocument ? attachedDocument : null;
  isResponding = true;
  welcome.hidden = true;
  sourceInput.value = '';
  sourceInput.style.height = 'auto';
  composerHint.textContent = `A question is a good place to start · ${MAX_PROMPT_LENGTH} characters max`;
  input.disabled = true;
  kidsQuestionInput.disabled = true;
  higherQuestionInput.disabled = true;
  sendButton.disabled = true;
  kidsAskButton.disabled = true;
  higherAskButton.disabled = true;
  const displayPrompt = documentForRequest ? `${prompt}\n[Study file: ${documentForRequest.name}]` : prompt;
  addMessage(displayPrompt, 'user');
  if (!getActiveSession()) {
    activeSessionId = (window.crypto && window.crypto.randomUUID) ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
    sessions.unshift({ id: activeSessionId, title: prompt.slice(0, 42), updatedAt: Date.now(), turns: [] });
  }
  const activeSession = getActiveSession();
  activeSession.turns.push({ role: 'user', text: displayPrompt });
  activeSession.updatedAt = Date.now();
  sessions = [activeSession, ...sessions.filter((session) => session.id !== activeSessionId)].slice(0, 20);
  saveSessions();
  const typingRow = showTyping();
  let reply;
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        provider: providerSelect.value,
        messages: activeSession.turns,
        document: documentForRequest,
        pdf_index_id: attachedPdf?.id || null,
        pdf_consent: Boolean(pdfConsent.checked),
        agent_mode: agentSelect.value,
        quiz_format: quizFormatSelect.value,
        planning_details: {
          subjects: document.querySelector('#planner-subjects').value,
          goal: document.querySelector('#planner-goal').value,
          minutes_per_day: Number(document.querySelector('#planner-minutes').value),
          deadline: document.querySelector('#planner-deadline').value,
        },
        learning_context: options.learningContext || null,
        education_context: options.educationContext || null,
        answer_language: answerLanguageSelect.value,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'The study assistant could not get an answer.');
    reply = { text: result.answer, images: result.images || [] };
  } catch (error) {
    reply = { text: error.message || 'The local answer server is unavailable. Start it in the terminal and try again.' };
  }
  const readButton = await streamReply(reply, typingRow, prompt);
  if (options.speak) speakText(reply.text, readButton);
  activeSession.turns.push({ role: 'assistant', text: reply.text, images: reply.images || [] });
  activeSession.updatedAt = Date.now();
  saveSessions();
  if (documentForRequest && attachedDocument === documentForRequest) clearAttachedDocument();
  isResponding = false;
  input.disabled = false;
  kidsQuestionInput.disabled = false;
  higherQuestionInput.disabled = false;
  sendButton.disabled = false;
  kidsAskButton.disabled = false;
  higherAskButton.disabled = false;
  renderSessions();
  sourceInput.focus();
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  const speak = event.currentTarget.dataset.voiceSubmit === 'true';
  delete event.currentTarget.dataset.voiceSubmit;
  submitPrompt(input.value, { speak });
});

input.addEventListener('input', () => {
  input.style.height = 'auto';
  input.style.height = `${Math.min(input.scrollHeight, 100)}px`;
  composerHint.textContent = `${input.value.length}/${MAX_PROMPT_LENGTH} characters`;
});

input.addEventListener('keydown', (event) => {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll('[data-prompt]').forEach((button) => {
  button.addEventListener('click', () => submitPrompt(button.dataset.prompt));
});

document.querySelector('#new-chat').addEventListener('click', () => {
  if (isResponding) return;
  conversation.replaceChildren();
  activeSessionId = null;
  welcome.hidden = false;
  liveStatus.textContent = 'New study session started.';
  input.value = '';
  input.style.height = 'auto';
  clearAttachedDocument();
  input.focus();
});
