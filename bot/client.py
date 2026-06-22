"""Thin async HTTP client the Telegram bot uses to call the FastAPI backend."""
from __future__ import annotations

import httpx

from app.config import settings


class AgentAPIClient:
    """Calls the FastAPI `/chat` endpoint."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.api_base_url).rstrip("/")

    async def chat(
        self, *, session_id: str, user_message: str, user_id: str | None = None
    ) -> dict:
        """Send a message to the agent and return the JSON response."""
        payload = {
            "session_id": session_id,
            "user_message": user_message,
            "user_id": user_id,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(f"{self.base_url}/chat", json=payload)
            resp.raise_for_status()
            return resp.json()
