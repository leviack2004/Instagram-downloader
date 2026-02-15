const form = document.getElementById('resolver-form');
const urlInput = document.getElementById('url');
const statusBox = document.getElementById('status');
const resultsBox = document.getElementById('results');
const validation = document.getElementById('validation');
const submitBtn = document.getElementById('submit-btn');

function setStatus(message, tone = '') {
  statusBox.className = `status ${tone}`;
  statusBox.textContent = message;
}

function validateInput(value) {
  const trimmed = value.trim();
  if (!trimmed) return 'Paste an Instagram URL.';
  if (!/(instagram\.com)\/(p|reel|tv)\//i.test(trimmed)) {
    return 'Use a public Instagram post/reel/tv URL.';
  }
  return '';
}

urlInput.addEventListener('input', () => {
  validation.textContent = validateInput(urlInput.value);
});

function renderResults(items) {
  resultsBox.innerHTML = '';
  items.forEach((item) => {
    const card = document.createElement('article');
    card.className = 'media-card';

    const media = document.createElement(item.media_type === 'video' ? 'video' : 'img');
    if (item.media_type === 'video') {
      media.src = item.url;
      media.controls = true;
      media.poster = item.thumbnail_url;
    } else {
      media.src = item.thumbnail_url || item.url;
      media.alt = `Instagram media ${item.index}`;
      media.loading = 'lazy';
    }

    const link = document.createElement('a');
    link.href = item.url;
    link.download = item.filename;
    link.textContent = `Download item ${item.index}`;

    card.append(media, link);
    resultsBox.append(card);
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const validationMessage = validateInput(urlInput.value);
  validation.textContent = validationMessage;
  resultsBox.innerHTML = '';

  if (validationMessage) return;

  setStatus('Fetching media…');
  submitBtn.disabled = true;

  try {
    const response = await fetch('/api/resolve', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: urlInput.value })
    });

    const data = await response.json();
    if (!response.ok) {
      setStatus(`${data.message} ${data.next_step || ''}`.trim(), 'error');
      return;
    }

    setStatus(`Found ${data.items.length} downloadable item(s).`, 'success');
    renderResults(data.items);
  } catch (error) {
    setStatus('Unexpected error. Please retry.', 'error');
  } finally {
    submitBtn.disabled = false;
  }
});
