import logging
import subprocess
from typing import Any, Dict

from reachy_mini_conversation_app_vlad.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)

_ROBOT_HOST = "pollen@reachy-mini.local"
_ROBOT_PASS = "root"

_music_process: subprocess.Popen | None = None


def _ssh(remote_cmd: str, wait: bool = True) -> subprocess.Popen:
    cmd = [
        "sshpass", "-p", _ROBOT_PASS,
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "LogLevel=ERROR",
        _ROBOT_HOST, remote_cmd,
    ]
    if wait:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    else:
        return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _stop_music_process() -> bool:
    global _music_process
    was_playing = _music_process is not None
    if _music_process is not None:
        _music_process.terminate()
        _music_process = None
    try:
        _ssh("pkill -f ffplay; pkill -f yt-dlp; true")
    except Exception:
        pass
    return was_playing


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

        remote_cmd = (
            f'yt-dlp "ytsearch1:{query}" -f bestaudio -o - -q 2>/dev/null'
            f" | ffplay -nodisp -autoexit -i - 2>/dev/null"
        )
        logger.info("play_music: ssh -> %s", remote_cmd)

        try:
            _music_process = _ssh(remote_cmd, wait=False)
            return {"status": "playing", "query": query}
        except Exception as e:
            logger.exception("play_music: failed to start")
            return {"error": str(e)}
