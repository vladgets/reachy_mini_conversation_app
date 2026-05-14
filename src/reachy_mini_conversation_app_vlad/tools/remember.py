from typing import Any, Dict

from reachy_mini_conversation_app_vlad.tools.core_tools import Tool, ToolDependencies
from reachy_mini_conversation_app_vlad.memory import upsert_fact


class Remember(Tool):
    name = "remember"
    description = (
        "Save or update a fact about the user or context for future sessions. "
        "Use a short snake_case key (e.g. 'user_name', 'preferred_language') and a concise value. "
        "If the key already exists it is updated in place."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Short snake_case identifier (e.g. 'user_name', 'prefers_short_answers')",
            },
            "fact": {
                "type": "string",
                "description": "The fact to remember",
            },
        },
        "required": ["key", "fact"],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        key = (kwargs.get("key") or "").strip().lower().replace(" ", "_")
        fact = (kwargs.get("fact") or "").strip()
        if not key or not fact:
            return {"error": "key and fact must be non-empty"}
        upsert_fact(key, fact)
        return {"ok": True, "remembered": f"{key}: {fact}"}
