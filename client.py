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


OPENCODE_BASE_URL = "http://127.0.0.1:4097"

SYSTEM_PROMPT = (
    "You are an expert full-stack developer building a production-quality web application."
)


class OpencodeClient:
    """Minimal async client for the OpenCode server API."""

    def __init__(self, base_url: str = OPENCODE_BASE_URL, project_dir: Path | None = None):
        headers = {}
        token = os.environ.get("OPENCODE_AUTH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        # No read timeout — agent sessions can take many minutes with tool calls
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=httpx.Timeout(connect=10, read=None, write=60, pool=10),
        )
        self._project_dir = str(project_dir.resolve()) if project_dir else None

    async def create_session(self, verbose: bool = True) -> str:
        """Create a new session scoped to the project directory and return its ID."""
        body = {}
        if self._project_dir:
            body["directory"] = self._project_dir
        r = await self._http.post("/session", json=body)
        r.raise_for_status()
        data = r.json()
        if verbose:
            session_dir = data.get("directory", "unknown")
            print(f"   Session directory: {session_dir}")
        return data["id"]

    def _system_prompt(self) -> str:
        base = SYSTEM_PROMPT
        if self._project_dir:
            base += f"\n\nYour working directory for this project is: {self._project_dir}\nAll files must be created inside this directory."
        return base

    async def chat(
        self,
        session_id: str,
        message: str,
        model: str,
        system: str | None = None,
    ) -> list[dict]:
        """
        Send a message to a session and return the response parts.

        Args:
            session_id: ID of an existing session
            message: User prompt text
            model: "providerID/modelID" e.g. "opencode-go/deepseek-v4-pro"
            system: System prompt

        Returns:
            List of part dicts from the assistant response
        """
        provider_id, model_id = model.split("/", 1)
        payload = {
            "parts": [{"type": "text", "text": message}],
            "model": {"modelID": model_id, "providerID": provider_id},
            "system": system if system is not None else self._system_prompt(),
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

    return OpencodeClient(project_dir=project_dir)
