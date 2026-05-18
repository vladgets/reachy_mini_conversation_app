// Offscreen document — runs as an extension page (not a service worker),
// so it is exempt from Chrome's Private Network Access restrictions.

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type !== 'FETCH_CHESS') return;

  fetch(message.url, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(message.data),
  })
    .then(r => r.ok ? { ok: true } : { ok: false, status: r.status })
    .catch(err => ({ ok: false, error: err.message }))
    .then(sendResponse);

  return true; // keep message channel open for async response
});
