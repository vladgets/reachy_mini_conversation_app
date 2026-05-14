import re
import os
import sys
import json
import logging
import threading
import urllib.request
from datetime import datetime
from pathlib import Path

from reachy_mini_conversation_app_vlad.config import DEFAULT_PROFILES_DIRECTORY, config, get_default_voice_for_backend


logger = logging.getLogger(__name__)

_location_cache: str | None = None
_location_fetch_done = False
_location_lock = threading.Lock()


def _fetch_location_from_ip() -> str:
    """Auto-detect location via IP geolocation. Returns formatted string or empty on failure."""
    try:
        url = "http://ip-api.com/json/?fields=city,regionName,country,lat,lon"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read())
        city = data.get("city", "")
        region = data.get("regionName", "")
        country = data.get("country", "")
        lat = data.get("lat")
        lon = data.get("lon")
        name_parts = [p for p in [city, region, country] if p]
        loc_str = ", ".join(name_parts)
        if lat is not None and lon is not None:
            return f"{loc_str} (lat={lat:.4f}, lon={lon:.4f})"
        return loc_str
    except Exception:
        return ""


def _get_location() -> str:
    """Return location string from env var override or cached IP detection."""
    manual = os.getenv("REACHY_MINI_LOCATION", "").strip()
    if manual:
        return manual
    global _location_cache, _location_fetch_done
    with _location_lock:
        if not _location_fetch_done:
            _location_cache = _fetch_location_from_ip()
            _location_fetch_done = True
        return _location_cache or ""


def _build_context_suffix() -> str:
    """Build a context block with current date, time, and location for the system prompt."""
    now = datetime.now()
    date_str = now.strftime("%A, %B %d, %Y")
    time_str = now.strftime("%I:%M %p")
    location = _get_location()
    lines = ["\n\n## CURRENT CONTEXT", f"Date: {date_str}", f"Time: {time_str}"]
    if location:
        lines.append(f"Location: {location}")
    return "\n".join(lines)


PROMPTS_LIBRARY_DIRECTORY = Path(__file__).parent / "prompts"
INSTRUCTIONS_FILENAME = "instructions.txt"
VOICE_FILENAME = "voice.txt"


def _expand_prompt_includes(content: str) -> str:
    """Expand [<name>] placeholders with content from prompts library files.

    Args:
        content: The template content with [<name>] placeholders

    Returns:
        Expanded content with placeholders replaced by file contents

    """
    # Pattern to match [<name>] where name is a valid file stem (alphanumeric, underscores, hyphens)
    # pattern = re.compile(r'^\[([a-zA-Z0-9_-]+)\]$')
    # Allow slashes for subdirectories
    pattern = re.compile(r"^\[([a-zA-Z0-9/_-]+)\]$")

    lines = content.split("\n")
    expanded_lines = []

    for line in lines:
        stripped = line.strip()
        match = pattern.match(stripped)

        if match:
            # Extract the name from [<name>]
            template_name = match.group(1)
            template_file = PROMPTS_LIBRARY_DIRECTORY / f"{template_name}.txt"

            try:
                if template_file.exists():
                    template_content = template_file.read_text(encoding="utf-8").rstrip()
                    expanded_lines.append(template_content)
                    logger.debug("Expanded template: [%s]", template_name)
                else:
                    logger.warning("Template file not found: %s, keeping placeholder", template_file)
                    expanded_lines.append(line)
            except Exception as e:
                logger.warning("Failed to read template '%s': %s, keeping placeholder", template_name, e)
                expanded_lines.append(line)
        else:
            expanded_lines.append(line)

    return "\n".join(expanded_lines)


def get_session_instructions() -> str:
    """Get session instructions, loading from REACHY_MINI_CUSTOM_PROFILE if set."""
    profile = config.REACHY_MINI_CUSTOM_PROFILE
    if not profile:
        logger.info(f"Loading default prompt from {PROMPTS_LIBRARY_DIRECTORY / 'default_prompt.txt'}")
        instructions_file = PROMPTS_LIBRARY_DIRECTORY / "default_prompt.txt"
    else:
        if config.PROFILES_DIRECTORY != DEFAULT_PROFILES_DIRECTORY:
            logger.info(
                "Loading prompt from external profile '%s' (root=%s)",
                profile,
                config.PROFILES_DIRECTORY,
            )
        else:
            logger.info(f"Loading prompt from profile '{profile}'")
        instructions_file = config.PROFILES_DIRECTORY / profile / INSTRUCTIONS_FILENAME

    try:
        if instructions_file.exists():
            instructions = instructions_file.read_text(encoding="utf-8").strip()
            if instructions:
                # Expand [<name>] placeholders with content from prompts library
                expanded_instructions = _expand_prompt_includes(instructions)
                return expanded_instructions + _build_context_suffix()
            logger.error(f"Profile '{profile}' has empty {INSTRUCTIONS_FILENAME}")
            sys.exit(1)
        logger.error(f"Profile {profile} has no {INSTRUCTIONS_FILENAME}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to load instructions from profile '{profile}': {e}")
        sys.exit(1)


def get_session_voice(default: str | None = None) -> str:
    """Resolve the voice to use for the session.

    If a custom profile is selected and contains a voice.txt, return its
    trimmed content; otherwise return the provided default or the active
    backend default voice.
    """
    fallback = get_default_voice_for_backend() if default is None else default
    profile = config.REACHY_MINI_CUSTOM_PROFILE
    if not profile:
        return fallback
    try:
        voice_file = config.PROFILES_DIRECTORY / profile / VOICE_FILENAME
        if voice_file.exists():
            voice = voice_file.read_text(encoding="utf-8").strip()
            return voice or fallback
    except Exception:
        pass
    return fallback
