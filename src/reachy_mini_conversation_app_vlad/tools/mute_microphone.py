import os
import asyncio
import subprocess
from typing import Any, Dict

from reachy_mini_conversation_app_vlad.tools.core_tools import Tool, ToolDependencies


def _pulse_env() -> dict:
    """Build subprocess env with XDG_RUNTIME_DIR so pactl finds the PulseAudio/PipeWire socket."""
    env = os.environ.copy()
    if "XDG_RUNTIME_DIR" not in env:
        env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
    return env


class MuteMicrophone(Tool):
    name = "mute_microphone"
    description = (
        "Set the system microphone input volume to 0, so the robot stops listening. "
        "The user can restore the volume manually via the app panel slider."
    )
    parameters_schema = {"type": "object", "properties": {}, "required": []}

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        env = _pulse_env()
        # (command, needs_pulse_env)
        commands = [
            (["pactl", "set-source-volume", "@DEFAULT_SOURCE@", "0%"], env),
            (["amixer", "sset", "Capture", "0%"], None),
            (["amixer", "set", "Capture", "0%"], None),
        ]
        for cmd, cmd_env in commands:
            try:
                result = await asyncio.to_thread(
                    subprocess.run, cmd, capture_output=True, text=True,
                    env=cmd_env,
                )
                if result.returncode == 0:
                    return {"ok": True}
            except FileNotFoundError:
                continue
        return {"error": "Could not set microphone volume — pactl and amixer unavailable"}
