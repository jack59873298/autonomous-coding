#!/usr/bin/env python3
"""
Autonomous Coding Agent Demo
============================

A minimal harness demonstrating long-running autonomous coding via OpenCode.
This script implements the two-agent pattern (initializer + coding agent).

Requires the OpenCode server to be running before starting:
    opencode serve

Example Usage:
    python autonomous_agent_demo.py --project-dir ./my_demo
    python autonomous_agent_demo.py --project-dir ./my_demo --max-iterations 5
    python autonomous_agent_demo.py --project-dir ./my_demo --model opencode/deepseek/deepseek-chat-v3-0324
"""

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file (if it exists)
# IMPORTANT: Must be called BEFORE importing other modules that read env vars at load time
load_dotenv()

from agent import run_autonomous_agent


# Configuration — format is "providerID/modelID"
# Go paid: opencode-go/deepseek-v4-pro, opencode-go/deepseek-v4-flash, opencode-go/kimi-k2.6
# Go free: opencode/deepseek-v4-flash-free, opencode/big-pickle
DEFAULT_MODEL = "opencode-go/deepseek-v4-pro"


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Autonomous Coding Agent Demo - Long-running agent harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start fresh project
  python autonomous_agent_demo.py --project-dir ./my_project

  # Use a different model
  python autonomous_agent_demo.py --project-dir ./my_project --model opencode/deepseek/deepseek-chat-v3-0324

  # Limit iterations for testing
  python autonomous_agent_demo.py --project-dir ./my_project --max-iterations 5

  # Continue existing project
  python autonomous_agent_demo.py --project-dir ./my_project

Authentication:
  Set OPENCODE_AUTH_TOKEN in your .env file (from https://opencode.ai/go dashboard).
  The OpenCode server must be running: opencode serve
        """,
    )

    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path("./autonomous_demo_project"),
        help="Directory for the project (default: generations/autonomous_demo_project). Relative paths automatically placed in generations/ directory.",
    )

    parser.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Maximum number of agent iterations (default: unlimited)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"OpenCode model to use (default: {DEFAULT_MODEL})",
    )

    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    args = parse_args()

    # Authentication: OPENCODE_AUTH_TOKEN read from .env file by load_dotenv() above.
    # The OpenCode server must already be running (opencode serve).

    # Automatically place projects in generations/ directory unless already specified
    project_dir = args.project_dir
    if not str(project_dir).startswith("generations/"):
        # Convert relative paths to be under generations/
        if project_dir.is_absolute():
            # If absolute path, use as-is
            pass
        else:
            # Prepend generations/ to relative paths
            project_dir = Path("generations") / project_dir

    try:
        # Run the agent (MCP server handles feature database)
        asyncio.run(
            run_autonomous_agent(
                project_dir=project_dir,
                model=args.model,
                max_iterations=args.max_iterations,
            )
        )
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        print("To resume, run the same command again")
    except Exception as e:
        print(f"\nFatal error: {e}")
        raise


if __name__ == "__main__":
    main()
