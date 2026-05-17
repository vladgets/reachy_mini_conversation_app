"""
Chess.com board monitor — reads piece positions from the DOM, analyzes with
local Stockfish, and serves the result over HTTP for Reachy's chess_advisor tool.

An SSH reverse tunnel is opened automatically so Reachy's localhost:8766 points
back to this machine — no manual configuration needed on the robot.

Usage
-----
Install deps (once):
    pip install playwright chess paramiko
    playwright install chromium
    brew install stockfish

Run:
    python chess_agent/laptop_agent.py

A browser will open automatically — log in to chess.com and start a game.

Environment overrides:
    CHESS_AGENT_PORT    HTTP port to serve on (default: 8766)
    CHESS_AGENT_DEPTH   Stockfish depth (default: 20)
    REACHY_HOST         Robot hostname (default: reachy-mini.local)
    REACHY_USER         SSH user (default: pollen)
    REACHY_PASSWORD     SSH password (default: root)
"""

import asyncio
import json
import logging
import os
import select
import shutil
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

from playwright.async_api import Page, async_playwright

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

PORT = int(os.getenv("CHESS_AGENT_PORT", "8766"))
ANALYSIS_DEPTH = int(os.getenv("CHESS_AGENT_DEPTH", "20"))
PV_MOVES = 8  # half-moves to include in the best line

REACHY_HOST = os.getenv("REACHY_HOST", "reachy-mini.local")
REACHY_USER = os.getenv("REACHY_USER", "pollen")
REACHY_PASSWORD = os.getenv("REACHY_PASSWORD", "root")

PIECE_MAP = {
    "wp": "P", "wr": "R", "wn": "N", "wb": "B", "wq": "Q", "wk": "K",
    "bp": "p", "br": "r", "bn": "n", "bb": "b", "bq": "q", "bk": "k",
}

_state: dict = {"error": "No board detected yet"}
_state_lock = threading.Lock()


# ── HTTP server ──────────────────────────────────────────────────────────────

class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/analysis", "/fen"):
            with _state_lock:
                body = json.dumps(_state).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        pass


def _start_http_server():
    HTTPServer(("0.0.0.0", PORT), _Handler).serve_forever()


# ── SSH reverse tunnel ───────────────────────────────────────────────────────

def _tunnel_handler(chan, local_port: int):
    """Forward data between an SSH channel and a local TCP connection."""
    try:
        sock = socket.create_connection(("127.0.0.1", local_port), timeout=5)
    except Exception as e:
        logger.debug("Tunnel: local connect failed: %s", e)
        chan.close()
        return
    try:
        while True:
            r, _, _ = select.select([chan, sock], [], [], 2.0)
            if chan in r:
                data = chan.recv(4096)
                if not data:
                    break
                sock.sendall(data)
            if sock in r:
                data = sock.recv(4096)
                if not data:
                    break
                chan.sendall(data)
    except Exception:
        pass
    finally:
        chan.close()
        sock.close()


def _reverse_tunnel_loop():
    """
    Maintain a persistent SSH reverse tunnel to Reachy.
    Reachy's localhost:PORT will forward to this machine's PORT.
    Reconnects automatically on failure.
    """
    try:
        import paramiko
    except ImportError:
        print("⚠  paramiko not installed — Reachy not auto-configured.")
        print(f"   Either run:  pip install paramiko")
        print(f"   Or manually add to Reachy's .env:")
        print(f"   CHESS_AGENT_URL=http://<your-laptop-ip>:{PORT}/analysis")
        return

    while True:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                REACHY_HOST,
                username=REACHY_USER,
                password=REACHY_PASSWORD,
                timeout=10,
                banner_timeout=10,
            )
            transport = client.get_transport()
            transport.set_keepalive(30)
            transport.request_port_forward("127.0.0.1", PORT)
            print(f"✓ Reachy auto-configured — tunnel active ({REACHY_HOST}:localhost:{PORT} → here)")

            while transport.is_active():
                chan = transport.accept(timeout=1)
                if chan is None:
                    continue
                threading.Thread(
                    target=_tunnel_handler,
                    args=(chan, PORT),
                    daemon=True,
                ).start()

            print("  Tunnel closed, reconnecting…")
        except Exception as e:
            print(f"  SSH tunnel error ({e}), retrying in 15s…")
        finally:
            try:
                client.close()
            except Exception:
                pass
        time.sleep(15)


# ── Board reading ────────────────────────────────────────────────────────────

def _placement_from_grid(board: list) -> str:
    rows = []
    for rank in range(7, -1, -1):
        empty = 0
        row = ""
        for file in range(8):
            p = board[rank][file]
            if p:
                if empty:
                    row += str(empty)
                    empty = 0
                row += p
            else:
                empty += 1
        if empty:
            row += str(empty)
        rows.append(row)
    return "/".join(rows)


async def _read_board(page: Page) -> dict:
    """Extract board state from chess.com DOM."""
    pieces = await page.query_selector_all(".piece")
    board: list = [[None] * 8 for _ in range(8)]
    found = 0

    for el in pieces:
        classes = (await el.get_attribute("class") or "").split()
        piece_char = next((PIECE_MAP[c] for c in classes if c in PIECE_MAP), None)
        # chess.com: square-XY where X=file(1-8), Y=rank(1-8), total class length = 9
        sq = next((c for c in classes if c.startswith("square-") and len(c) == 9), None)
        if not piece_char or not sq:
            continue
        f, r = int(sq[7]) - 1, int(sq[8]) - 1
        if 0 <= f <= 7 and 0 <= r <= 7:
            board[r][f] = piece_char
            found += 1

    if found < 2:
        return {"error": "No chess board found — open a game on chess.com"}

    # Active color from data-ply (1 = white's 1st move, 2 = black's, …)
    nodes = await page.query_selector_all("[data-ply]")
    if nodes:
        last_str = await nodes[-1].get_attribute("data-ply")
        ply = int(last_str) if last_str and last_str.isdigit() else 0
    else:
        ply = 0

    active = "b" if ply % 2 == 1 else "w"
    fullmove = (ply // 2) + 1

    castling = ""
    if board[0][4] == "K":
        if board[0][7] == "R":
            castling += "K"
        if board[0][0] == "R":
            castling += "Q"
    if board[7][4] == "k":
        if board[7][7] == "r":
            castling += "k"
        if board[7][0] == "r":
            castling += "q"

    fen = f"{_placement_from_grid(board)} {active} {castling or '-'} - 0 {fullmove}"
    return {"fen": fen, "active": active, "fullmove": fullmove}


# ── Stockfish analysis ───────────────────────────────────────────────────────

def _format_pv(san_moves: list, start_fullmove: int, white_to_move: bool) -> str:
    """Format SAN move list as '12. Nf3 Nc6 13. Bb5 a6'."""
    out: list[str] = []
    fullmove = start_fullmove
    white_turn = white_to_move
    for san in san_moves:
        if white_turn:
            out.append(f"{fullmove}. {san}")
        else:
            if out:
                out[-1] += f" {san}"
            else:
                out.append(f"{fullmove}… {san}")
            fullmove += 1
        white_turn = not white_turn
    return " ".join(out)


def _analyze(fen: str) -> dict:
    try:
        import chess
        import chess.engine
    except ImportError:
        return {"error": "python-chess not installed — run: pip install chess"}

    sf = shutil.which("stockfish")
    if not sf:
        for candidate in ["/opt/homebrew/bin/stockfish", "/usr/local/bin/stockfish"]:
            if os.path.isfile(candidate):
                sf = candidate
                break
    if not sf:
        return {"error": "Stockfish not found — run: brew install stockfish"}

    try:
        board = chess.Board(fen)
    except ValueError as e:
        return {"error": f"Invalid FEN: {e}"}

    if board.is_game_over():
        return {"error": f"Game is already over ({board.result()})"}

    try:
        with chess.engine.SimpleEngine.popen_uci(sf) as engine:
            info = engine.analyse(board, chess.engine.Limit(depth=ANALYSIS_DEPTH))

        pv = info.get("pv") or []
        if not pv:
            return {"error": "Stockfish returned no move"}

        best_move_san = board.san(pv[0])

        line_board = board.copy()
        san_line: list[str] = []
        for move in pv[:PV_MOVES]:
            if move not in line_board.legal_moves:
                break
            san_line.append(line_board.san(move))
            line_board.push(move)

        best_line_str = _format_pv(
            san_line,
            start_fullmove=board.fullmove_number,
            white_to_move=(board.turn == chess.WHITE),
        )

        score_str = ""
        score = info.get("score")
        if score:
            pov = score.white() if board.turn == chess.WHITE else score.black()
            if pov.is_mate():
                n = pov.mate()
                score_str = f"mate in {abs(n)}" if n and n > 0 else f"being mated in {abs(n)}"
            else:
                cp = pov.score()
                if cp is not None:
                    score_str = f"{'+' if cp >= 0 else ''}{cp / 100:.2f}"

        return {
            "best_move": best_move_san,
            "best_line": best_line_str,
            "san_moves": san_line,
            "evaluation": score_str,
            "side_to_move": "white" if board.turn == chess.WHITE else "black",
            "move_number": board.fullmove_number,
            "depth": info.get("depth", ANALYSIS_DEPTH),
        }
    except Exception as e:
        logger.exception("Stockfish analysis failed")
        return {"error": f"Stockfish analysis failed: {e}"}


# ── Main monitor loop ────────────────────────────────────────────────────────

async def _monitor():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto("https://www.chess.com/play/online")
        print("Browser opened — log in to chess.com and start a game.")

        print(f"Analysis server: http://localhost:{PORT}/analysis  (depth {ANALYSIS_DEPTH})\n")

        prev_fen = None
        while True:
            try:
                board_data = await _read_board(page)
            except Exception as e:
                board_data = {"error": str(e)}

            fen = board_data.get("fen")
            if fen and fen != prev_fen:
                prev_fen = fen
                side = "white" if board_data.get("active") == "w" else "black"
                move_n = board_data.get("fullmove", "?")
                print(f"[move {move_n}, {side} to move] analyzing…", end=" ", flush=True)

                analysis = await asyncio.to_thread(_analyze, fen)
                board_data.update(analysis)

                if "best_move" in analysis:
                    print(f"{analysis['best_move']}  ({analysis.get('evaluation', '?')})")
                    print(f"  line: {analysis.get('best_line', '')}")
                else:
                    print(analysis.get("error", "unknown error"))

                with _state_lock:
                    _state.clear()
                    _state.update(board_data)
            elif "error" in board_data:
                with _state_lock:
                    _state.clear()
                    _state.update(board_data)
            # position unchanged: keep existing state so best_move remains available

            await asyncio.sleep(1.5)


def main():
    threading.Thread(target=_start_http_server, daemon=True).start()
    threading.Thread(target=_reverse_tunnel_loop, daemon=True).start()

    try:
        asyncio.run(_monitor())
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
