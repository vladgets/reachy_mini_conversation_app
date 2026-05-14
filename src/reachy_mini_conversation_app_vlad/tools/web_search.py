"""Web search tool using OpenAI Responses API with built-in web search."""

import logging
import os
from typing import Any, Dict

from openai import AsyncOpenAI

from reachy_mini_conversation_app_vlad.tools.core_tools import Tool, ToolDependencies


logger = logging.getLogger(__name__)

WEB_SEARCH_MODEL = "gpt-5.4-mini"


class WebSearch(Tool):
    """Search the web and return a concise spoken-friendly answer."""

    name = "web_search"
    description = (
        "Search the web for current information and return a concise answer. "
        "Use this when the user asks about recent events, news, weather, facts, "
        "or anything that requires up-to-date information."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to look up on the web.",
            }
        },
        "required": ["query"],
    }

    async def __call__(self, deps: ToolDependencies, query: str = "", **kwargs: Any) -> Dict[str, Any]:
        """Search the web via OpenAI's built-in web search and return a summary."""
        logger.info("Tool call: web_search query=%r", query)

        if not query:
            return {"error": "No query provided"}

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return {"error": "OPENAI_API_KEY is not set — web search is unavailable"}

        try:
            client = AsyncOpenAI(api_key=api_key)
            response = await client.responses.create(
                model=WEB_SEARCH_MODEL,
                tools=[{"type": "web_search_preview"}],
                input=query,
            )
            answer = response.output_text
            if not answer:
                return {"error": "No results returned from web search"}
            logger.info("web_search result: %d chars", len(answer))
            return {"answer": answer}
        except Exception as e:
            logger.error("web_search failed: %s", e)
            return {"error": f"Web search failed: {e}"}
