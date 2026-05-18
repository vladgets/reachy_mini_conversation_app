const dot      = document.getElementById('dot');
const statusEl = document.getElementById('status');
const urlInput = document.getElementById('url');
const saveBtn  = document.getElementById('save');
const testBtn  = document.getElementById('test');
const analysisEl = document.getElementById('analysis');
const ageEl    = document.getElementById('age');
const errorEl  = document.getElementById('error');

// Load saved URL
chrome.storage.sync.get({ reachyUrl: 'http://localhost:7862' }, ({ reachyUrl }) => {
  urlInput.value = reachyUrl;
});

// Load last known status
chrome.storage.local.get(['connectionStatus', 'lastAnalysis', 'lastUpdate', 'lastError'], (data) => {
  const { connectionStatus, lastAnalysis, lastUpdate, lastError } = data;

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

  if (lastError && connectionStatus !== 'connected') {
    errorEl.style.display = 'block';
    errorEl.textContent = `Error: ${lastError}`;
  }
});

// Test connection — delegate to background so the fetch goes via the offscreen document
testBtn.addEventListener('click', () => {
  testBtn.textContent = '…';
  testBtn.disabled = true;
  chrome.runtime.sendMessage(
    { type: 'TEST_CONNECTION', data: { best_move: 'e2e4', evaluation: '+0.30', side_to_move: 'white', move_number: 1, depth: 18 } },
    (result) => {
      if (result?.ok) {
        dot.className = 'dot ok';
        statusEl.textContent = 'Connected to Reachy';
        errorEl.style.display = 'none';
        testBtn.textContent = 'OK ✓';
      } else {
        dot.className = 'dot err';
        statusEl.textContent = 'disconnected';
        errorEl.style.display = 'block';
        errorEl.textContent = `Error: ${result?.error ?? result?.status ?? 'unknown'}`;
        testBtn.textContent = 'Failed';
      }
      testBtn.disabled = false;
      setTimeout(() => { testBtn.textContent = 'Test'; }, 2000);
    }
  );
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
