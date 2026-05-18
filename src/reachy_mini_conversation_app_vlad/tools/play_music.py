import os
import sys
import signal
import logging
import subprocess
from typing import Any, Dict

from reachy_mini_conversation_app_vlad.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)

_music_process: subprocess.Popen | None = None


def _stop_music_process() -> bool:
    global _music_process
    if _music_process is None:
        return False
    try:
        os.killpg(os.getpgid(_music_process.pid), signal.SIGTERM)
    except Exception:
        pass
    _music_process = None
    return True


class PlayMusic(Tool):
    name = "play_music"
    description = (
        "Search and play music through the robot's speaker. "
        "Accepts any song name, artist, genre, or mood description."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Song, artist, or mood to search for (e.g. 'Bohemian Rhapsody', 'chill lo-fi beats').",
            }
        },
        "required": ["query"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        global _music_process
        query = kwargs.get("query", "").strip()
        if not query:
            return {"error": "query is required"}

        _stop_music_process()

        cmd = (
            f'yt-dlp "ytsearch1:{query}" -f bestaudio -o - -q 2>/dev/null'
            f" | ffplay -nodisp -autoexit -i - 2>/dev/null"
        )
        logger.info("play_music: %s", cmd)

        try:
            _music_process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid)
            return {"status": "playing", "query": query}
        except Exception as e:
            logger.exception("play_music: failed to start")
            return {"error": str(e)}
