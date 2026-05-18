import atexit
import os
import signal
import logging
import subprocess
from typing import Any, Dict

from reachy_mini_conversation_app_vlad.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)

# Launcher services run with a stripped PATH — extend it to cover common locations.
_SYSTEM_PATH = "/usr/bin:/usr/local/bin:/usr/sbin:/bin:/sbin:" + os.environ.get("PATH", "")

# dmix device configured in ~/.asoundrc for shared ALSA access alongside the app.
_ALSA_DEVICE = "reachymini_audio_sink"

# Music is attenuated so Reachy's voice always cuts through clearly.
_MUSIC_VOLUME = 0.50

_music_process: subprocess.Popen | None = None

atexit.register(lambda: _stop_music_process())


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

        env = os.environ.copy()
        env["PATH"] = _SYSTEM_PATH

        # Resample to 16000 Hz and attenuate so Reachy's voice always cuts through.
        cmd = (
            f'yt-dlp "ytsearch1:{query}" -f bestaudio -o - -q 2>/dev/null'
            f" | ffmpeg -i pipe:0 -af volume={_MUSIC_VOLUME} -ar 16000 -ac 2 -f s16le - 2>/dev/null"
            f" | aplay -D {_ALSA_DEVICE} -f S16_LE -r 16000 -c 2 -q"
        )
        logger.info("play_music: %s", cmd)

        try:
            _music_process = subprocess.Popen(cmd, shell=True, preexec_fn=os.setsid, env=env)
            return {"status": "playing", "query": query}
        except Exception as e:
            logger.exception("play_music: failed to start")
            return {"error": str(e)}
