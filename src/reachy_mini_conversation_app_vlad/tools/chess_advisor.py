"""Chess advisor tool — returns Stockfish's best move for the current chess position.

Analysis is pushed by the Reachy Chess Advisor browser extension (primary) or
fetched from a running laptop_agent.py (fallback).
"""

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict

from reachy_mini_conversation_app_vlad import chess_state
from reachy_mini_conversation_app_vlad.tools.core_tools import Tool, ToolDependencies

logger = logging.getLogger(__name__)

_LAPTOP_AGENT_URL = "http://localhost:8766/analysis"


def _fetch_from_laptop(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach laptop agent at {url} ({e})"}
    except Exception as e:
        return {"error": f"Laptop agent fetch failed: {e}"}


class ChessAdvisor(Tool):
    name = "chess_advisor"
    description = (
        "Get Stockfish's best move and suggested line for the current chess position. "
        "Use this when the user asks for the best move, wants chess advice, or asks what "
        "Stockfish recommends. Never use conversation history or camera to answer chess "
        "move questions — always call this tool. "
        "Requires the Reachy Chess Advisor browser extension to be open on chess.com, "
        "or laptop_agent.py to be running. Moves are in UCI notation (e.g. e2e4, g1f3)."
    )
    parameters_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        # Primary: analysis pushed by the browser extension
        state = chess_state.get()
        if state.get("best_move"):
            logger.info("chess_advisor: serving analysis from extension (move %s)", state.get("best_move"))
            return {
                "best_move":    state["best_move"],
                "best_line":    state.get("best_line", ""),
                "evaluation":   state.get("evaluation", ""),
                "side_to_move": state.get("side_to_move", ""),
                "move_number":  state.get("move_number", ""),
            }

        # Fallback: laptop agent HTTP server
        url = os.getenv("CHESS_AGENT_URL", _LAPTOP_AGENT_URL)
        logger.info("chess_advisor: no extension data, fetching from %s", url)

        result: dict = {}
        for attempt in range(4):
            result = await asyncio.to_thread(_fetch_from_laptop, url)
            if "error" not in result or "Cannot reach" in result.get("error", ""):
                break
            logger.info("chess_advisor: not ready (attempt %d/4), retrying…", attempt + 1)
            await asyncio.sleep(1.5)

        if "error" in result:
            return result

        if "best_move" not in result:
            return {
                "error": (
                    "No chess analysis available. "
                    "Open chess.com with the Reachy Chess Advisor extension installed, "
                    "or run chess_agent/laptop_agent.py."
                )
            }

        return {
            "best_move":    result["best_move"],
            "best_line":    result.get("best_line", ""),
            "evaluation":   result.get("evaluation", ""),
            "side_to_move": result.get("side_to_move", ""),
            "move_number":  result.get("move_number", ""),
        }
