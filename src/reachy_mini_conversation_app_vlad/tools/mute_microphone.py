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
    """Build env so pactl/wpctl can reach the PulseAudio/PipeWire session socket.

    When the app runs as a launcher service, XDG_RUNTIME_DIR and
    DBUS_SESSION_BUS_ADDRESS are often stripped from the environment.
    wpctl needs both to reach WirePlumber; pactl needs XDG_RUNTIME_DIR.
    """
    env = os.environ.copy()
    env["PATH"] = _SYSTEM_PATH
    uid = os.getuid()
    xdg_runtime = env.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}"
    env["XDG_RUNTIME_DIR"] = xdg_runtime
    if "DBUS_SESSION_BUS_ADDRESS" not in env:
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={xdg_runtime}/bus"
    return env


class MuteMicrophone(Tool):
    name = "mute_microphone"
    description = (
        "Set the system microphone input volume to 0, so the robot stops listening. "
        "The user can restore the volume manually via the app panel slider."
    )
    parameters_schema = {"type": "object", "properties": {}, "required": []}

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        import logging
        logger = logging.getLogger(__name__)

        env = _pulse_env()
        candidates = {
            "wpctl": _find("wpctl"),
            "pactl": _find("pactl"),
            "amixer": _find("amixer"),
        }
        logger.info("mute_microphone: resolved paths %s", candidates)

        commands = [
            # wpctl (WirePlumber/PipeWire) — volume is 0..1 float, not "0%"
            ([candidates["wpctl"], "set-volume", "@DEFAULT_AUDIO_SOURCE@", "0"], env),
            ([candidates["wpctl"], "set-mute", "@DEFAULT_AUDIO_SOURCE@", "1"], env),
            # pactl (PulseAudio compat) — uses "0%"
            ([candidates["pactl"], "set-source-volume", "@DEFAULT_SOURCE@", "0%"], env),
            # amixer via PipeWire PulseAudio bridge (-D pulse)
            ([candidates["amixer"], "-D", "pulse", "sset", "Capture", "0%"], env),
            # ALSA direct fallback
            ([candidates["amixer"], "sset", "Capture", "0%"], None),
            ([candidates["amixer"], "set", "Capture", "0%"], None),
        ]
        attempts = []
        for cmd, cmd_env in commands:
            try:
                result = await asyncio.to_thread(
                    subprocess.run, cmd, capture_output=True, text=True, env=cmd_env,
                )
                logger.info("mute_microphone: %s rc=%d stderr=%r", cmd, result.returncode, result.stderr[:200])
                if result.returncode == 0:
                    return {"ok": True, "method": cmd[0]}
                attempts.append(f"{cmd[0]}(rc={result.returncode})")
            except FileNotFoundError:
                attempts.append(f"{cmd[0]}(not found)")
        return {"error": f"Could not mute microphone. Tried: {', '.join(attempts)}"}
