"""Persistent key-value memory store for facts across sessions."""
from __future__ import annotations
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MEMORY_FILENAME = "memory.json"
_INSTANCE_DIR = Path.home() / ".local" / "share" / "reachy_mini_conversation_app"


def _memory_path() -> Path:
    return _INSTANCE_DIR / MEMORY_FILENAME


def read_memory() -> dict[str, str]:
    path = _memory_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception as e:
        logger.warning("Failed to read memory: %s", e)
    return {}


def write_memory(facts: dict[str, str]) -> None:
    path = _memory_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(facts, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("Failed to write memory: %s", e)


def upsert_fact(key: str, fact: str) -> None:
    facts = read_memory()
    facts[key] = fact
    write_memory(facts)


def format_for_prompt() -> str:
    facts = read_memory()
    if not facts:
        return ""
    lines = ["\n\n## WHAT I REMEMBER"]
    for k, v in sorted(facts.items()):
        lines.append(f"- {k}: {v}")
    return "\n".join(lines)
