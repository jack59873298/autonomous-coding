"""
OpenCode HTTP Client
====================

Thin httpx wrapper around the OpenCode server REST API.
The OpenCode server must be running before any calls are made:
    opencode serve --port 4096

Authentication / credentials are managed by OpenCode itself
(run `opencode providers login` to set up your Go subscription).
MCP servers (playwright, features) are configured in opencode.jsonc.
"""

import os
from pathlib import Path

import httpx


OPENCODE_BASE_URL = "http://127.0.0.1:4096"

SYSTEM_PROMPT = (
    "You are an expert full-stack developer building a production-quality web application."
)


class OpencodeClient:
    """Minimal async client for the OpenCode server API."""

    def __init__(self, base_url: str = OPENCODE_BASE_URL, timeout: float = 600):
        self._http = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def create_session(self) -> str:
        """Create a new session and return its ID."""
        r = await self._http.post("/session", json={})
        r.raise_for_status()
        return r.json()["id"]

    async def chat(
        self,
        session_id: str,
        message: str,
        model: str,
        system: str = SYSTEM_PROMPT,
    ) -> list[dict]:
        """
        Send a message to a session and return the response parts.

        Args:
            session_id: ID of an existing session
            message: User prompt text
            model: "providerID/modelID" e.g. "opencode/deepseek-v4-flash-free"
            system: System prompt

        Returns:
            List of part dicts from the assistant response
        """
        provider_id, model_id = model.split("/", 1)
        payload = {
            "parts": [{"type": "text", "text": message}],
            "model": {"modelID": model_id, "providerID": provider_id},
            "system": system,
        }
        r = await self._http.post(f"/session/{session_id}/message", json=payload)
        r.raise_for_status()
        return r.json().get("parts", [])

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.aclose()


def create_client(project_dir: Path, model: str) -> OpencodeClient:
    """
    Create an OpenCode client connected to the local server.

    PROJECT_DIR is set in the environment so the features MCP server
    (spawned by OpenCode) knows which project database to use.
    """
    os.environ["PROJECT_DIR"] = str(project_dir.resolve())

    print(f"Connecting to OpenCode server at {OPENCODE_BASE_URL}")
    print(f"   Project directory: {project_dir.resolve()}")
    print(f"   Model: {model}")
    print(f"   MCP servers: playwright (browser), features (database)")
    print()

    return OpencodeClient()
