"""Chess advisor tool — fetches the pre-analyzed position from the laptop agent and returns Stockfish's recommendation."""

import asyncio
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any, Dict

from reachy_mini_conversation_app_vlad.tools.core_tools import Tool, ToolDependencies

logger = logging.getLogger(__name__)

_DEFAULT_URL = "http://localhost:8766/analysis"


def _fetch_analysis(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        return {"error": f"Cannot reach chess agent at {url} — is laptop_agent.py running? ({e})"}
    except Exception as e:
        return {"error": f"Failed to fetch analysis: {e}"}


class ChessAdvisor(Tool):
    name = "chess_advisor"
    description = (
        "Get Stockfish's best move and suggested line for the current chess position on the laptop. "
        "Use this when the user asks for the best move, wants chess advice, asks what Stockfish recommends, "
        "or asks you to analyze the position. "
        "Requires chess_agent/laptop_agent.py to be running on the laptop "
        "and CHESS_AGENT_URL to be set in the environment."
    )
    parameters_schema = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        url = os.getenv("CHESS_AGENT_URL", _DEFAULT_URL)
        logger.info("chess_advisor: fetching analysis from %s", url)

        # Retry a few times in case the laptop agent is mid-analysis
        result: dict = {}
        for attempt in range(4):
            result = await asyncio.to_thread(_fetch_analysis, url)
            if "error" not in result or "Cannot reach" in result.get("error", ""):
                break
            logger.info("chess_advisor: not ready yet (attempt %d/4), retrying…", attempt + 1)
            await asyncio.sleep(1.5)

        if "error" in result:
            return result

        if "best_move" not in result:
            return {"error": "Laptop agent has not yet analyzed a position — open a game on chess.com"}

        return {
            "best_move": result["best_move"],
            "best_line": result.get("best_line", ""),
            "evaluation": result.get("evaluation", ""),
            "side_to_move": result.get("side_to_move", ""),
            "move_number": result.get("move_number", ""),
        }
