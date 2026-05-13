"""
Agent Session Logic
===================

Core agent interaction functions for running autonomous coding sessions
via the OpenCode server (opencode-ai Python SDK).
"""

import asyncio
import traceback
from pathlib import Path
from typing import Optional

from client import OpencodeClient, SYSTEM_PROMPT, create_client
from progress import print_session_header, print_progress_summary, has_features
from prompts import (
    get_initializer_prompt,
    get_coding_prompt,
    copy_spec_to_project,
    has_project_prompts,
)


# Configuration
AUTO_CONTINUE_DELAY_SECONDS = 3


async def run_agent_session(
    client: OpencodeClient,
    message: str,
    project_dir: Path,
    model: str,
) -> tuple[str, str]:
    """
    Run a single agent session using the OpenCode server.

    Creates a fresh session for each call (clean context), sends the prompt,
    and waits for the full response including all tool-use rounds.

    Returns:
        (status, response_text) where status is "continue" or "error"
    """
    print("Sending prompt to OpenCode server...\n")

    try:
        session_id = await client.create_session()
        parts = await client.chat(session_id, message, model)

        response_text = ""
        for part in parts:
            part_type = part.get("type")

            if part_type == "text":
                text = part.get("text", "")
                response_text += text
                print(text, end="", flush=True)

            elif part_type in ("tool-invocation", "tool-call", "tool_use"):
                tool_name = part.get("toolName") or part.get("name", "unknown")
                print(f"\n[Tool: {tool_name}]", flush=True)
                tool_input = part.get("input") or part.get("args")
                if tool_input:
                    input_str = str(tool_input)
                    print(f"   Input: {input_str[:200]}{'...' if len(input_str) > 200 else ''}", flush=True)
                print("   [Done]", flush=True)

        print("\n" + "-" * 70 + "\n")
        return "continue", response_text

    except Exception as e:
        print(f"Error during agent session: {type(e).__name__}: {e}")
        print(traceback.format_exc())
        return "error", repr(e)


async def run_autonomous_agent(
    project_dir: Path,
    model: str,
    max_iterations: Optional[int] = None,
) -> None:
    """
    Run the autonomous agent loop.

    Args:
        project_dir: Directory for the project
        model: Model identifier to use
        max_iterations: Maximum number of iterations (None for unlimited)
    """
    print("\n" + "=" * 70)
    print("  AUTONOMOUS CODING AGENT")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print(f"Model: {model}")
    if max_iterations:
        print(f"Max iterations: {max_iterations}")
    else:
        print("Max iterations: Unlimited (will run until completion)")
    print()

    # Create project directory
    project_dir.mkdir(parents=True, exist_ok=True)

    # Check if this is a fresh start or continuation
    is_first_run = not has_features(project_dir)

    if is_first_run:
        print("Fresh start - will use initializer agent")
        print()
        print("=" * 70)
        print("  NOTE: First session takes 10-20+ minutes!")
        print("  The agent is generating 200 detailed test cases.")
        print("  This may appear to hang - it's working. Watch for [Tool: ...] output.")
        print("=" * 70)
        print()
        copy_spec_to_project(project_dir)
    else:
        print("Continuing existing project")
        print_progress_summary(project_dir)

    # Create the HTTP client once; reuse across all iterations
    client = create_client(project_dir, model)

    # Main loop
    iteration = 0

    while True:
        iteration += 1

        if max_iterations and iteration > max_iterations:
            print(f"\nReached max iterations ({max_iterations})")
            print("To continue, run the script again without --max-iterations")
            break

        print_session_header(iteration, is_first_run)

        if is_first_run:
            prompt = get_initializer_prompt(project_dir)
        else:
            prompt = get_coding_prompt(project_dir)

        status, response = await run_agent_session(client, prompt, project_dir, model)

        if status == "continue":
            is_first_run = False  # only advance past initializer on success
            print(f"\nAgent will auto-continue in {AUTO_CONTINUE_DELAY_SECONDS}s...")
            print_progress_summary(project_dir)
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        elif status == "error":
            print("\nSession encountered an error. Will retry...")
            await asyncio.sleep(AUTO_CONTINUE_DELAY_SECONDS)

        if max_iterations is None or iteration < max_iterations:
            print("\nPreparing next session...\n")
            await asyncio.sleep(1)

    # Final summary
    print("\n" + "=" * 70)
    print("  SESSION COMPLETE")
    print("=" * 70)
    print(f"\nProject directory: {project_dir}")
    print_progress_summary(project_dir)

    print("\n" + "-" * 70)
    print("  TO RUN THE GENERATED APPLICATION:")
    print("-" * 70)
    print(f"\n  cd {project_dir.resolve()}")
    print("  ./init.sh           # Run the setup script")
    print("  # Or manually:")
    print("  npm install && npm run dev")
    print("\n  Then open http://localhost:3000 (or check init.sh for the URL)")
    print("-" * 70)

    print("\nDone!")
