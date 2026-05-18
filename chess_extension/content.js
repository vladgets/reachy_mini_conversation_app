// Reads the chess.com board every 2 seconds, runs Stockfish when position
// changes, and forwards the analysis to the background service worker.

const DEPTH = 18;
const POLL_MS = 2000;

const PIECE_MAP = {
  wp:'P', wr:'R', wn:'N', wb:'B', wq:'Q', wk:'K',
  bp:'p', br:'r', bn:'n', bb:'b', bq:'q', bk:'k',
};

// ── Board reading ─────────────────────────────────────────────────────────────

function readFen() {
  const pieces = document.querySelectorAll('.piece');
  const board = Array.from({length: 8}, () => Array(8).fill(null));
  let found = 0;

  for (const el of pieces) {
    const cls = el.className.split(' ');
    const piece = cls.map(c => PIECE_MAP[c]).find(Boolean);
    const sq = cls.find(c => c.startsWith('square-') && c.length === 9);
    if (!piece || !sq) continue;
    const f = parseInt(sq[7]) - 1;
    const r = parseInt(sq[8]) - 1;
    if (f >= 0 && f < 8 && r >= 0 && r < 8) { board[r][f] = piece; found++; }
  }

  if (found < 2) return null;

  // Active color detection
  let active = 'w';
  let fullmove = 1;

  const isPuzzle = /\/(puzzles|training)\b/.test(window.location.pathname);

  if (isPuzzle) {
    // Puzzles always orient the board from the perspective of the player to move
    const flipped = !!document.querySelector('chess-board.flipped, .board.flipped');
    active = flipped ? 'b' : 'w';
  } else {
    // Regular game: use data-ply move count
    const plies = document.querySelectorAll('[data-ply]');
    const ply = plies.length
      ? (parseInt(plies[plies.length - 1].getAttribute('data-ply')) || 0)
      : 0;
    active   = ply % 2 === 1 ? 'b' : 'w';
    fullmove = Math.floor(ply / 2) + 1;

    // Override with running clock if available
    const blackClockRunning = document.querySelector(
      '.clock-bottom.clock-running, .clock-black.clock-running'
    );
    const whiteClockRunning = document.querySelector(
      '.clock-top.clock-running, .clock-white.clock-running'
    );
    if (blackClockRunning) active = 'b';
    else if (whiteClockRunning) active = 'w';
  }

  // Castling from starting square positions
  let castling = '';
  if (board[0][4]==='K') { if (board[0][7]==='R') castling+='K'; if (board[0][0]==='R') castling+='Q'; }
  if (board[7][4]==='k') { if (board[7][7]==='r') castling+='k'; if (board[7][0]==='r') castling+='q'; }

  // FEN placement
  const rows = [];
  for (let rank = 7; rank >= 0; rank--) {
    let empty = 0, row = '';
    for (let file = 0; file < 8; file++) {
      const p = board[rank][file];
      if (p) { if (empty) { row += empty; empty = 0; } row += p; } else { empty++; }
    }
    if (empty) row += empty;
    rows.push(row);
  }

  return `${rows.join('/')} ${active} ${castling || '-'} - 0 ${fullmove}`;
}

// ── Main (async to allow blob Worker creation) ────────────────────────────────

(async () => {
  // Content scripts can't construct Workers from chrome-extension:// URLs directly.
  // Workaround: create an inline worker that calls importScripts() with the
  // extension URL — importScripts inside a worker CAN load extension resources.
  const sfUrl = chrome.runtime.getURL('stockfish.js');
  const workerBlob = new Blob(
    [`importScripts('${sfUrl}');`],
    { type: 'text/javascript' }
  );
  const engine = new Worker(URL.createObjectURL(workerBlob));

  let analyzing  = false;
  let pendingFen = null;
  let currentFen = null;
  let pvMoves    = [];
  let evalStr    = '';
  let depth      = 0;

  engine.onmessage = (event) => {
    const line = typeof event === 'string' ? event : event.data;

    if (line.startsWith('info') && line.includes(' pv ')) {
      const dm = line.match(/depth (\d+)/);
      const sm = line.match(/score (cp|mate) (-?\d+)/);
      const pm = line.match(/ pv (.+)/);
      if (dm) depth = parseInt(dm[1]);
      if (sm) {
        const [, type, val] = sm, v = parseInt(val);
        evalStr = type === 'mate'
          ? (v > 0 ? `mate in ${v}` : `being mated in ${Math.abs(v)}`)
          : `${v >= 0 ? '+' : ''}${(v / 100).toFixed(2)}`;
      }
      if (pm) pvMoves = pm[1].trim().split(' ');
    }

    if (line.startsWith('bestmove')) {
      const bm = line.match(/bestmove (\S+)/)?.[1];
      if (bm && bm !== '(none)') {
        const parts      = currentFen.split(' ');
        const sideToMove = parts[1] === 'w' ? 'white' : 'black';
        const moveNumber = parseInt(parts[5]);

        chrome.runtime.sendMessage({
          type: 'ANALYSIS',
          data: {
            fen:          currentFen,
            best_move:    bm,
            best_line:    pvMoves.slice(0, 8).join(' '),
            evaluation:   evalStr,
            side_to_move: sideToMove,
            move_number:  moveNumber,
            depth,
          },
        });
      }

      analyzing = false;
      if (pendingFen) { const next = pendingFen; pendingFen = null; analyze(next); }
    }
  };

  function analyze(fen) {
    if (analyzing) { pendingFen = fen; return; }
    analyzing  = true;
    currentFen = fen;
    pvMoves    = [];
    evalStr    = '';
    engine.postMessage('ucinewgame');
    engine.postMessage(`position fen ${fen}`);
    engine.postMessage(`go depth ${DEPTH}`);
  }

  engine.postMessage('uci');

  // ── Poll ────────────────────────────────────────────────────────────────────

  let prevFen = null;

  setInterval(() => {
    const fen = readFen();
    if (fen && fen !== prevFen) { prevFen = fen; analyze(fen); }
  }, POLL_MS);
})();
