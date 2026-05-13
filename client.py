"""
OpenCode Client Configuration
==============================

Factory for creating the opencode-ai async client.
The OpenCode server must be running before any calls are made
(start it with: opencode serve).

Authentication uses OPENCODE_AUTH_TOKEN from the environment (.env file).
MCP servers (playwright, features) are configured in opencode.jsonc.
"""

import os
from pathlib import Path

from opencode_ai import AsyncOpencode


SYSTEM_PROMPT = (
    "You are an expert full-stack developer building a production-quality web application."
)


def create_client(project_dir: Path, model: str) -> AsyncOpencode:
    """
    Create an AsyncOpencode client connected to the local OpenCode server.

    The OpenCode server must already be running on port 4096.
    Start it with: opencode serve

    PROJECT_DIR is set in the environment so the features MCP server
    (spawned by OpenCode) knows which project database to use.
    """
    os.environ["PROJECT_DIR"] = str(project_dir.resolve())

    print(f"Connecting to OpenCode server at http://127.0.0.1:4096")
    print(f"   Project directory: {project_dir.resolve()}")
    print(f"   Model: {model}")
    print(f"   MCP servers: playwright (browser), features (database)")
    print()

    return AsyncOpencode(base_url="http://127.0.0.1:4096")
