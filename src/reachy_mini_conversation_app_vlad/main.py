"""Entry point for Vlad's Reachy Mini Conversation App fork.

This thin wrapper exists so the Robot desktop app can discover the
settings panel URL from site_packages/reachy_mini_conversation_app_vlad/main.py,
matching the entry point name used to register this app.
"""
from reachy_mini_conversation_app.main import ReachyMiniConversationApp


class ReachyMiniConversationAppVlad(ReachyMiniConversationApp):
    """Reachy Mini conversation app — Vlad's fork."""

    custom_app_url = "http://0.0.0.0:7860/"
