import asyncio
import subprocess
from typing import Any, Dict

from reachy_mini_conversation_app_vlad.tools.core_tools import Tool, ToolDependencies


class MuteMicrophone(Tool):
    name = "mute_microphone"
    description = (
        "Set the system microphone input volume to 0, so the robot stops listening. "
        "The user can restore the volume manually via the app panel slider."
    )
    parameters_schema = {"type": "object", "properties": {}, "required": []}

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        # Try PulseAudio first (Raspberry Pi default), then ALSA
        commands = [
            ["pactl", "set-source-volume", "@DEFAULT_SOURCE@", "0%"],
            ["amixer", "set", "Capture", "0%"],
        ]
        for cmd in commands:
            try:
                result = await asyncio.to_thread(
                    subprocess.run, cmd, capture_output=True, text=True
                )
                if result.returncode == 0:
                    return {"ok": True}
            except FileNotFoundError:
                continue
        return {"error": "Could not set microphone volume — pactl and amixer unavailable"}
