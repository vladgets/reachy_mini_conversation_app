// Service worker — stores analysis and connection state for the popup.

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === 'STORE_ANALYSIS') {
    chrome.storage.local.set({ lastAnalysis: message.data, lastUpdate: Date.now() });
  } else if (message.type === 'CONNECTION_STATUS') {
    const update = { connectionStatus: message.status };
    if (message.error) update.lastError = message.error;
    chrome.storage.local.set(update);
  }
});
