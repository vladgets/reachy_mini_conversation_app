// Service worker — receives analysis from content script and POSTs to Reachy.
// Runs in chrome-extension:// context, not subject to mixed-content restrictions.

chrome.runtime.onMessage.addListener((message) => {
  if (message.type !== 'ANALYSIS') return;

  chrome.storage.sync.get(
    { reachyUrl: 'http://reachy-mini.local:7860' },
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
          lastError:        `${err.name}: ${err.message}`,
        });
      }
    }
  );
});
