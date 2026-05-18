// Service worker — receives analysis from the content script and POSTs it
// to Reachy's /chess endpoint. Runs outside the page context so no CORS issues.

chrome.runtime.onMessage.addListener((message) => {
  if (message.type !== 'ANALYSIS') return;

  chrome.storage.sync.get(
    { reachyUrl: 'http://localhost:8766' },
    async ({ reachyUrl }) => {
      const url = `${reachyUrl.replace(/\/$/, '')}/chess`;
      chrome.storage.local.set({ lastAnalysis: message.data, lastUpdate: Date.now() });

      try {
        const resp = await fetch(url, {
          method:  'POST',
          headers: { 'Content-Type': 'application/json' },
          body:    JSON.stringify(message.data),
        });
        chrome.storage.local.set({
          connectionStatus: resp.ok ? 'connected' : `error ${resp.status}`,
        });
      } catch (err) {
        chrome.storage.local.set({
          connectionStatus: 'disconnected',
          lastError:        err.message,
        });
      }
    }
  );
});
