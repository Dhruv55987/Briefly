const form = document.querySelector('#analysis-form');
const urlField = document.querySelector('#source-url');
const fileField = document.querySelector('#source-file');
const fileName = document.querySelector('#file-name');
const errorBox = document.querySelector('#error-message');
const progressCard = document.querySelector('#progress-card');
const analyzeButton = document.querySelector('#analyze-button');
let sourceMode = 'url';
let activeJobId = null;
let pollTimer = null;

document.querySelectorAll('.source-tab').forEach((tab) => {
  tab.addEventListener('click', () => {
    sourceMode = tab.dataset.mode;
    document.querySelectorAll('.source-tab').forEach((item) => item.classList.toggle('selected', item === tab));
    document.querySelector('#url-panel').classList.toggle('hidden', sourceMode !== 'url');
    document.querySelector('#file-panel').classList.toggle('hidden', sourceMode !== 'file');
    errorBox.hidden = true;
  });
});

fileField.addEventListener('change', () => {
  fileName.textContent = fileField.files[0]?.name || 'Choose a file or drag it here';
});

const dropzone = document.querySelector('.dropzone');
dropzone.addEventListener('dragover', (event) => {
  event.preventDefault();
  dropzone.classList.add('dragging');
});
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragging'));
dropzone.addEventListener('drop', (event) => {
  event.preventDefault();
  dropzone.classList.remove('dragging');
  const dropped = event.dataTransfer.files;
  if (!dropped.length) return;
  fileField.files = dropped;
  fileName.textContent = dropped[0].name;
});

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function renderText(elementId, value) {
  const element = document.getElementById(elementId);
  element.textContent = value?.trim() || 'No information found.';
}

function showResults(result) {
  renderText('summary-content', result.summary);
  renderText('actions-content', result.action_items);
  renderText('decisions-content', result.key_decisions);
  renderText('questions-content', result.open_questions);
  renderText('transcript-content', result.transcript);
  document.querySelector('#result-title').textContent = result.title || 'Meeting summary';
  progressCard.classList.add('hidden');
  document.querySelector('#results').classList.remove('hidden');
  document.querySelector('#results').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function updateProgress(job) {
  document.querySelector('#progress-message').textContent = job.message || 'Working…';
  const progress = Math.max(0, Math.min(100, Number(job.progress) || 0));
  document.querySelector('#progress-number').textContent = `${progress}%`;
  document.querySelector('#progress-bar').style.width = `${progress}%`;
}

async function pollJob(jobId) {
  try {
    const response = await fetch(`/api/jobs/${jobId}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.detail || 'Could not retrieve job status');
    updateProgress(job);
    if (job.status === 'completed') {
      clearInterval(pollTimer);
      analyzeButton.disabled = false;
      showResults(job.result);
      return true;
    } else if (job.status === 'failed') {
      clearInterval(pollTimer);
      analyzeButton.disabled = false;
      showError(job.error || 'Analysis failed. Check the server configuration and try again.');
      progressCard.classList.add('hidden');
      return true;
    }
    return false;
  } catch (error) {
    clearInterval(pollTimer);
    analyzeButton.disabled = false;
    progressCard.classList.add('hidden');
    showError(error.message);
    return true;
  }
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  errorBox.hidden = true;
  const data = new FormData();
  data.append('language', document.querySelector('#language').value);
  if (sourceMode === 'url') {
    const url = urlField.value.trim();
    if (!url) return showError('Paste a video or audio URL first.');
    data.append('source_url', url);
  } else {
    if (!fileField.files.length) return showError('Choose an audio or video file first.');
    data.append('file', fileField.files[0]);
  }
  analyzeButton.disabled = true;
  document.querySelector('#results').classList.add('hidden');
  progressCard.classList.remove('hidden');
  updateProgress({ message: 'Sending your source…', progress: 2 });
  try {
    const response = await fetch('/api/jobs', { method: 'POST', body: data });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Could not start analysis');
    activeJobId = payload.job_id;
    const finished = await pollJob(activeJobId);
    if (!finished) pollTimer = setInterval(() => pollJob(activeJobId), 1800);
  } catch (error) {
    analyzeButton.disabled = false;
    progressCard.classList.add('hidden');
    showError(error.message);
  }
});

document.querySelector('#new-analysis').addEventListener('click', () => {
  document.querySelector('#results').classList.add('hidden');
  form.scrollIntoView({ behavior: 'smooth', block: 'center' });
});

function appendChatMessage(role, text) {
  const messages = document.querySelector('#chat-messages');
  const welcome = messages.querySelector('.chat-welcome');
  if (welcome) welcome.remove();
  const node = document.createElement('div');
  node.className = `chat-message ${role}`;
  node.textContent = text;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
  return node;
}

document.querySelector('#chat-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const input = document.querySelector('#chat-question');
  const question = input.value.trim();
  if (!question || !activeJobId) return;
  input.value = '';
  appendChatMessage('user', question);
  const pending = appendChatMessage('assistant', 'Looking through the transcript…');
  const sendButton = event.currentTarget.querySelector('button');
  sendButton.disabled = true;
  try {
    const response = await fetch(`/api/jobs/${activeJobId}/chat`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || 'Could not answer that question');
    pending.textContent = payload.answer;
  } catch (error) {
    pending.textContent = error.message;
  } finally {
    sendButton.disabled = false;
    input.focus();
  }
});
