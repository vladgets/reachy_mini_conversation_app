import os
import re
import shutil
import asyncio
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from reachy_mini_conversation_app_vlad.tools.core_tools import Tool, ToolDependencies

# Launcher services run with a stripped PATH — extend it to cover common locations.
_SYSTEM_PATH = "/usr/bin:/usr/local/bin:/usr/sbin:/bin:/sbin:" + os.environ.get("PATH", "")

# Reachy Mini daemon API (same host, controls the UI slider too)
_DAEMON_MICROPHONE_URL = "http://127.0.0.1:8000/api/volume/microphone/set"


def _find(cmd: str) -> str:
    """Return the full path of cmd, searching system locations regardless of $PATH."""
    return shutil.which(cmd, path=_SYSTEM_PATH) or cmd


def _pulse_env() -> dict:
    """Build env so pactl/wpctl can reach the PulseAudio/PipeWire session socket."""
    env = os.environ.copy()
    env["PATH"] = _SYSTEM_PATH
    uid = os.getuid()
    xdg_runtime = env.get("XDG_RUNTIME_DIR") or f"/run/user/{uid}"
    env["XDG_RUNTIME_DIR"] = xdg_runtime
    if "DBUS_SESSION_BUS_ADDRESS" not in env:
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={xdg_runtime}/bus"
    if "PIPEWIRE_RUNTIME_DIR" not in env:
        env["PIPEWIRE_RUNTIME_DIR"] = xdg_runtime
    return env


def _usb_card_numbers() -> List[int]:
    """Return ALSA card numbers that correspond to USB audio devices, card 1 first."""
    try:
        text = Path("/proc/asound/cards").read_text(encoding="utf-8", errors="replace")
        usb_cards = []
        lines = text.splitlines()
        for i, line in enumerate(lines):
            m = re.match(r"^\s*(\d+)\s+\[", line)
            if m:
                card_no = int(m.group(1))
                context = lines[i + 1] if i + 1 < len(lines) else ""
                if "usb" in line.lower() or "usb" in context.lower():
                    usb_cards.append(card_no)
        return usb_cards if usb_cards else [1, 0]
    except Exception:
        return [1, 0]


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

        # Try the daemon API first — it uses the correct ALSA command AND updates the UI slider
        try:
            import httpx
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(_DAEMON_MICROPHONE_URL, json={"volume": 0})
                if resp.status_code == 200:
                    logger.info("mute_microphone: daemon API succeeded, volume=0")
                    return {"ok": True, "method": "daemon_api"}
                logger.warning("mute_microphone: daemon API returned %d", resp.status_code)
        except Exception as e:
            logger.warning("mute_microphone: daemon API failed: %s", e)

        # Fallback: direct ALSA/PipeWire commands
        env = _pulse_env()
        wpctl = _find("wpctl")
        pactl = _find("pactl")
        amixer = _find("amixer")
        usb_cards = _usb_card_numbers()
        logger.info("mute_microphone: fallback — wpctl=%s amixer=%s usb_cards=%s", wpctl, amixer, usb_cards)

        control_names = ["Capture", "Mic", "PCM", "Master"]
        commands: List[tuple] = [
            ([wpctl, "set-volume", "@DEFAULT_AUDIO_SOURCE@", "0"], env),
            ([wpctl, "set-mute", "@DEFAULT_AUDIO_SOURCE@", "1"], env),
            ([pactl, "set-source-volume", "@DEFAULT_SOURCE@", "0%"], env),
            ([pactl, "set-source-mute", "@DEFAULT_SOURCE@", "1"], env),
            *[([amixer, "-D", "pulse", "sset", ctrl, "0%"], env) for ctrl in control_names],
        ]
        for card_no in usb_cards + [c for c in [0, 1, 2] if c not in usb_cards]:
            for ctrl in control_names:
                commands.append(([amixer, "-c", str(card_no), "sset", ctrl, "0%"], None))

        attempts = []
        for cmd, cmd_env in commands:
            try:
                result = await asyncio.to_thread(
                    subprocess.run, cmd, capture_output=True, text=True, env=cmd_env,
                )
                logger.info(
                    "mute_microphone: %s rc=%d stderr=%r",
                    " ".join(cmd[:4]), result.returncode, result.stderr[:200],
                )
                if result.returncode == 0:
                    return {"ok": True, "method": " ".join(cmd[:4])}
                attempts.append(f"{cmd[0]}({'|'.join(str(x) for x in cmd[1:4])})(rc={result.returncode})")
            except FileNotFoundError:
                attempts.append(f"{cmd[0]}(not found)")
        return {"error": f"Could not mute microphone. Tried: {', '.join(attempts)}"}
