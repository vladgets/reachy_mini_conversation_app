const dot      = document.getElementById('dot');
const statusEl = document.getElementById('status');
const urlInput = document.getElementById('url');
const saveBtn  = document.getElementById('save');
const analysisEl = document.getElementById('analysis');
const ageEl    = document.getElementById('age');

// Load saved URL
chrome.storage.sync.get({ reachyUrl: 'http://reachy-mini.local:7860' }, ({ reachyUrl }) => {
  urlInput.value = reachyUrl;
});

// Load last known status
chrome.storage.local.get(['connectionStatus', 'lastAnalysis', 'lastUpdate'], (data) => {
  const { connectionStatus, lastAnalysis, lastUpdate } = data;

  if (connectionStatus === 'connected') {
    dot.classList.add('ok');
    statusEl.textContent = 'Connected to Reachy';
  } else if (connectionStatus) {
    dot.classList.add('err');
    statusEl.textContent = connectionStatus;
  } else {
    statusEl.textContent = 'Not yet connected';
  }

  if (lastAnalysis) {
    const { best_move, best_line, evaluation, side_to_move, move_number } = lastAnalysis;
    analysisEl.style.display = 'block';
    analysisEl.innerHTML =
      `<strong>Move ${move_number} — ${side_to_move} to move</strong><br>` +
      `Best: <strong>${best_move}</strong> (${evaluation})<br>` +
      `Line: ${best_line}`;
  }

  if (lastUpdate) {
    const secs = Math.round((Date.now() - lastUpdate) / 1000);
    ageEl.textContent = `Last update: ${secs}s ago`;
  }
});

// Save URL
saveBtn.addEventListener('click', () => {
  const val = urlInput.value.trim();
  if (!val) return;
  chrome.storage.sync.set({ reachyUrl: val }, () => {
    saveBtn.textContent = 'Saved ✓';
    setTimeout(() => { saveBtn.textContent = 'Save'; }, 1500);
  });
});
