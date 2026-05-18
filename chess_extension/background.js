// Service worker — stores analysis and delegates the HTTP fetch to an offscreen
// document, which is an extension page and exempt from Private Network Access.

async function ensureOffscreen() {
  try {
    await chrome.offscreen.createDocument({
      url:           'offscreen.html',
      reasons:       ['DOM_SCRAPING'],
      justification: 'POST chess analysis to local Reachy device',
    });
  } catch (_) {
    // Document already exists
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === 'TEST_CONNECTION') {
    chrome.storage.sync.get(
      { reachyUrl: 'http://reachy-mini.local:7860' },
      async ({ reachyUrl }) => {
        const url = `${reachyUrl.replace(/\/$/, '')}/chess`;
        await ensureOffscreen();
        chrome.runtime.sendMessage({ type: 'FETCH_CHESS', url, data: message.data }, sendResponse);
      }
    );
    return true;
  }

  if (message.type !== 'ANALYSIS') return;

  chrome.storage.local.set({ lastAnalysis: message.data, lastUpdate: Date.now() });

  chrome.storage.sync.get(
    { reachyUrl: 'http://reachy-mini.local:7860' },
    async ({ reachyUrl }) => {
      const url = `${reachyUrl.replace(/\/$/, '')}/chess`;
      await ensureOffscreen();

      chrome.runtime.sendMessage(
        { type: 'FETCH_CHESS', url, data: message.data },
        (result) => {
          if (chrome.runtime.lastError) {
            chrome.storage.local.set({
              connectionStatus: 'disconnected',
              lastError:        chrome.runtime.lastError.message,
            });
            return;
          }
          chrome.storage.local.set({
            connectionStatus: result?.ok ? 'connected' : `error ${result?.status ?? result?.error}`,
          });
        }
      );
    }
  );
});
