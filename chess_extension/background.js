// Service worker — stores analysis and POSTs it to the Reachy app.
// Fetches are made directly from the service worker, which has host_permissions
// for the robot's IP and is not subject to the renderer-process sandbox that
// blocks private-network access in offscreen documents.

async function postToReachy(data) {
  const { reachyUrl } = await chrome.storage.sync.get({ reachyUrl: 'http://reachy-mini.local:7860' });
  const url = `${reachyUrl.replace(/\/$/, '')}/chess`;
  const resp = await fetch(url, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(data),
  });
  return resp.ok ? { ok: true } : { ok: false, status: resp.status };
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'TEST_CONNECTION') {
    postToReachy(message.data)
      .then(sendResponse)
      .catch(e => sendResponse({ ok: false, error: e.message }));
    return true;
  }

  if (message.type !== 'ANALYSIS') return;

  chrome.storage.local.set({ lastAnalysis: message.data, lastUpdate: Date.now() });

  postToReachy(message.data)
    .then(result => chrome.storage.local.set({
      connectionStatus: result.ok ? 'connected' : `error ${result.status}`,
    }))
    .catch(e => chrome.storage.local.set({
      connectionStatus: 'disconnected',
      lastError: e.message,
    }));
});
