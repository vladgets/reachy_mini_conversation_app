import logging
from typing import Any, Dict

from reachy_mini_conversation_app_vlad.tools import play_music as play_music_mod
from reachy_mini_conversation_app_vlad.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)


class StopMusic(Tool):
    name = "stop_music"
    description = "Stop the currently playing music."
    parameters_schema = {"type": "object", "properties": {}, "required": []}

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        logger.info("Tool call: stop_music")
        stopped = play_music_mod._stop_music_process()
        return {"status": "stopped" if stopped else "nothing_playing"}
