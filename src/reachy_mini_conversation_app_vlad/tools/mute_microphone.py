import os
import shutil
import asyncio
import subprocess
from typing import Any, Dict

from reachy_mini_conversation_app_vlad.tools.core_tools import Tool, ToolDependencies

# Launcher services run with a stripped PATH — extend it to cover common locations.
_SYSTEM_PATH = "/usr/bin:/usr/local/bin:/usr/sbin:/bin:/sbin:" + os.environ.get("PATH", "")


def _find(cmd: str) -> str:
    """Return the full path of cmd, searching system locations regardless of $PATH."""
    return shutil.which(cmd, path=_SYSTEM_PATH) or cmd


def _pulse_env() -> dict:
    """Add XDG_RUNTIME_DIR so pactl/wpctl find the PulseAudio/PipeWire socket."""
    env = os.environ.copy()
    env["PATH"] = _SYSTEM_PATH
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
        commands = [
            # PipeWire (Raspberry Pi OS Bookworm default)
            ([_find("wpctl"), "set-volume", "@DEFAULT_AUDIO_SOURCE@", "0%"], env),
            # PulseAudio / PipeWire compat layer
            ([_find("pactl"), "set-source-volume", "@DEFAULT_SOURCE@", "0%"], env),
            # ALSA fallbacks
            ([_find("amixer"), "sset", "Capture", "0%"], None),
            ([_find("amixer"), "set", "Capture", "0%"], None),
        ]
        for cmd, cmd_env in commands:
            try:
                result = await asyncio.to_thread(
                    subprocess.run, cmd, capture_output=True, text=True, env=cmd_env,
                )
                if result.returncode == 0:
                    return {"ok": True, "method": cmd[0]}
            except FileNotFoundError:
                continue
        return {"error": "Could not set microphone volume — wpctl, pactl, and amixer not found"}
