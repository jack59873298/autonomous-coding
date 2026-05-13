#!/usr/bin/env python3
"""
Simple CLI launcher for the Autonomous Coding Agent.
Provides an interactive menu to create new projects or continue existing ones.

Supports two paths for new projects:
1. Claude path: Use /create-spec to generate spec interactively
2. Manual path: Edit template files directly, then continue
"""

import asyncio
import os
import sys
import subprocess
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

from prompts import (
    scaffold_project_prompts,
    has_project_prompts,
    get_project_prompts_dir,
)


# Directory containing generated projects
GENERATIONS_DIR = Path(__file__).parent / "generations"

OPENCODE_SERVER_URL = "http://127.0.0.1:4097"


def check_opencode_server() -> bool:
    """Return True if an OpenCode server is reachable on the configured port."""
    try:
        r = httpx.get(f"{OPENCODE_SERVER_URL}/global/health", timeout=3)
        if r.status_code == 200:
            return True
        # Got a response but not from OpenCode (e.g. another app owns the port)
        print(f"\nError: Port {OPENCODE_SERVER_URL.split(':')[-1]} returned HTTP {r.status_code}.")
        if r.status_code == 401 and "Basic" in r.headers.get("www-authenticate", ""):
            print("Another application (e.g. the Kilo Code VS Code extension) is using that port.")
            print("Stop it first, or start OpenCode on a different port:")
            print(f"  opencode serve --port 4097")
            print("  # and update OPENCODE_SERVER_URL in start.py / client.py to match")
        else:
            print("Make sure OpenCode is running: opencode serve --port 4096")
        return False
    except Exception:
        print("\nError: OpenCode server is not running.")
        print("Start it in a separate terminal with:")
        print("  opencode serve --port 4096")
        print("\nMake sure OPENCODE_AUTH_TOKEN is set in your .env file.")
        print("Get your token from: https://opencode.ai/go")
        return False


def check_spec_exists(project_dir: Path) -> bool:
    """
    Check if valid spec files exist for a project.

    Checks in order:
    1. Project prompts directory: {project_dir}/prompts/app_spec.txt
    2. Project root (legacy): {project_dir}/app_spec.txt
    """
    # Check project prompts directory first
    project_prompts = get_project_prompts_dir(project_dir)
    spec_file = project_prompts / "app_spec.txt"
    if spec_file.exists():
        try:
            content = spec_file.read_text(encoding="utf-8")
            return "<project_specification>" in content
        except (OSError, PermissionError):
            return False

    # Check legacy location in project root
    legacy_spec = project_dir / "app_spec.txt"
    if legacy_spec.exists():
        try:
            content = legacy_spec.read_text(encoding="utf-8")
            return "<project_specification>" in content
        except (OSError, PermissionError):
            return False

    return False


def get_existing_projects() -> list[str]:
    """Get list of existing projects from generations folder."""
    if not GENERATIONS_DIR.exists():
        return []

    projects = []
    for item in GENERATIONS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            projects.append(item.name)

    return sorted(projects)


def display_menu(projects: list[str]) -> None:
    """Display the main menu."""
    print("\n" + "=" * 50)
    print("  Autonomous Coding Agent Launcher")
    print("=" * 50)
    print("\n[1] Create new project")

    if projects:
        print("[2] Continue existing project")

    print("[q] Quit")
    print()


def display_projects(projects: list[str]) -> None:
    """Display list of existing projects."""
    print("\n" + "-" * 40)
    print("  Existing Projects")
    print("-" * 40)

    for i, project in enumerate(projects, 1):
        print(f"  [{i}] {project}")

    print("\n  [b] Back to main menu")
    print()


def get_project_choice(projects: list[str]) -> str | None:
    """Get user's project selection."""
    while True:
        choice = input("Select project number: ").strip().lower()

        if choice == 'b':
            return None

        try:
            idx = int(choice) - 1
            if 0 <= idx < len(projects):
                return projects[idx]
            print(f"Please enter a number between 1 and {len(projects)}")
        except ValueError:
            print("Invalid input. Enter a number or 'b' to go back.")


def get_new_project_name() -> str | None:
    """Get name for new project."""
    print("\n" + "-" * 40)
    print("  Create New Project")
    print("-" * 40)
    print("\nEnter project name (e.g., my-awesome-app)")
    print("Leave empty to cancel.\n")

    name = input("Project name: ").strip()

    if not name:
        return None

    # Basic validation - OS-aware invalid characters
    # Windows has more restrictions than Unix
    if sys.platform == "win32":
        invalid_chars = '<>:"/\\|?*'
    else:
        # Unix only restricts / and null
        invalid_chars = '/'

    for char in invalid_chars:
        if char in name:
            print(f"Invalid character '{char}' in project name")
            return None

    return name


def ensure_project_scaffolded(project_name: str) -> Path:
    """
    Ensure project directory exists with prompt templates.

    Creates the project directory and copies template files if needed.

    Returns:
        The project directory path
    """
    project_dir = GENERATIONS_DIR / project_name

    # Create project directory if it doesn't exist
    project_dir.mkdir(parents=True, exist_ok=True)

    # Scaffold prompts (copies templates if they don't exist)
    print(f"\nSetting up project: {project_name}")
    scaffold_project_prompts(project_dir)

    return project_dir


_AI_SPEC_SYSTEM = """\
You are a software project requirements expert helping a user define a complete app specification.

Start by asking what kind of app they want to build. Gather details through conversation:
- Core features and functionality
- Target users
- Tech stack preferences (default: React frontend + Node/Python backend)
- Any specific requirements or constraints

After 3-5 exchanges, or when the user says "done" or "generate", output the complete specification.
Wrap it exactly like this (no text after the closing tag):

<project_specification>
[detailed spec here]
</project_specification>"""


async def _ai_spec_turn(conversation: list[tuple[str, str]], model: str) -> str:
    """Send one conversation turn in a fresh session and return the AI's response text."""
    from client import OpencodeClient

    if not conversation:
        prompt = "Begin the project specification interview."
    else:
        history = "\n\n".join(
            f"{'User' if role == 'user' else 'Assistant'}: {text}"
            for role, text in conversation
        )
        prompt = (
            f"Here is the conversation so far:\n\n{history}\n\n"
            "Continue as the interviewer. Respond to the user's last message."
        )

    async with OpencodeClient() as client:
        session_id = await client.create_session(verbose=False)
        parts = await asyncio.wait_for(
            client.chat(session_id, prompt, model, system=_AI_SPEC_SYSTEM),
            timeout=90.0,
        )

    return "".join(p["text"] for p in parts if p.get("type") == "text")


async def _ai_spec_conversation(project_dir: Path) -> bool:
    """Run interactive AI spec generation using one fresh session per turn."""
    spec_file = get_project_prompts_dir(project_dir) / "app_spec.txt"
    conversation: list[tuple[str, str]] = []
    model = "opencode-go/deepseek-v4-pro"

    print("\n" + "-" * 50)
    print("  AI Spec Generator")
    print("-" * 50)
    print('Describe your app and answer follow-up questions.')
    print('Type "done" or "generate" at any point to produce the spec.')
    print('Type "quit" to cancel.\n')

    while True:
        print("Thinking...", flush=True)
        try:
            response_text = await _ai_spec_turn(conversation, model)
        except asyncio.TimeoutError:
            print("\nNo response after 90s. The OpenCode server may be busy.")
            retry = input("Retry this turn? [Y/n]: ").strip().lower()
            if retry == 'n':
                return False
            continue
        except Exception as e:
            print(f"\nError calling OpenCode: {e}")
            return False

        if not response_text:
            print("(no response received — check the OpenCode server logs)")

        print(f"\nAI: {response_text}\n")
        conversation.append(("assistant", response_text))

        if "<project_specification>" in response_text:
            save = input("Save this specification? [Y/n]: ").strip().lower()
            if save != 'n':
                start = response_text.find("<project_specification>")
                end = response_text.find("</project_specification>") + len("</project_specification>")
                spec_text = response_text[start:end] if start >= 0 and end > start else response_text
                spec_file.write_text(spec_text, encoding="utf-8")
                print(f"\nSpec saved to: {spec_file}")
                return True

        try:
            user_input = input("You: ").strip()
        except KeyboardInterrupt:
            print("\n\nCancelled.")
            return False

        if user_input.lower() in ('quit', 'exit'):
            return False
        if user_input.lower() in ('done', 'generate'):
            user_input = "Please generate the final project specification now."

        conversation.append(("user", user_input))


def run_ai_spec_flow(project_dir: Path) -> bool:
    """Run AI-assisted spec generation (sync wrapper)."""
    if not check_opencode_server():
        return False
    try:
        return asyncio.run(_ai_spec_conversation(project_dir))
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        return False


def _open_in_editor(path: Path) -> None:
    """Try to open a file in VS Code, fall back to the OS default."""
    try:
        subprocess.Popen(["code", str(path)])
        print(f"  Opened in VS Code: {path.name}")
    except FileNotFoundError:
        try:
            os.startfile(str(path))
        except Exception:
            pass  # editor open is best-effort


def run_manual_spec_flow(project_dir: Path) -> bool:
    """Guide user through manual spec editing, auto-opening the file."""
    prompts_dir = get_project_prompts_dir(project_dir)
    spec_file = prompts_dir / "app_spec.txt"

    print("\n" + "-" * 50)
    print("  Manual Specification Setup")
    print("-" * 50)
    print("\nTemplate files have been created. Edit these files in your editor:")
    print(f"\n  Required:")
    print(f"    {spec_file}")
    print(f"\n  Optional (customize agent behavior):")
    print(f"    {prompts_dir / 'initializer_prompt.md'}")
    print(f"    {prompts_dir / 'coding_prompt.md'}")
    print("\n" + "-" * 50)
    print("\nThe app_spec.txt file contains a template with placeholders.")
    print("Replace the placeholders with your actual project specification.")

    _open_in_editor(spec_file)

    print("\nWhen you're done editing, press Enter to continue...")

    try:
        input()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        return False

    if check_spec_exists(project_dir):
        print("\nSpec file validated successfully!")
        return True
    else:
        print("\nWarning: The app_spec.txt file still contains the template placeholder.")
        print("The agent may not work correctly without a proper specification.")
        confirm = input("Continue anyway? [y/N]: ").strip().lower()
        return confirm == 'y'


def ask_spec_creation_choice() -> str | None:
    """Ask user how to create the project spec."""
    print("\n" + "-" * 40)
    print("  Specification Setup")
    print("-" * 40)
    print("\nHow would you like to define your project?")
    print("\n[1] Generate spec with AI (interactive)")
    print("    Chat with the AI to define your project, spec is written automatically")
    print("\n[2] Edit templates manually")
    print("    Edit the template files directly in your editor")
    print("\n[b] Back to main menu")
    print()

    while True:
        choice = input("Select [1/2/b]: ").strip().lower()
        if choice in ('1', '2', 'b'):
            return choice
        print("Invalid choice. Please enter 1, 2, or b.")


def create_new_project_flow() -> str | None:
    """
    Complete flow for creating a new project.

    1. Get project name
    2. Create project directory and scaffold prompts
    3. Ask: Claude or Manual?
    4. If Claude: Run /create-spec with project path
    5. If Manual: Show paths, wait for Enter
    6. Return project name if successful
    """
    project_name = get_new_project_name()
    if not project_name:
        return None

    # Create project directory and scaffold prompts FIRST
    project_dir = ensure_project_scaffolded(project_name)

    # Ask user how they want to handle spec creation
    choice = ask_spec_creation_choice()

    if choice == 'b':
        return None
    elif choice == '1':
        success = run_ai_spec_flow(project_dir)
        if not success:
            print("\nAI spec generation failed or was cancelled.")
            retry = input("Start agent anyway? [y/N]: ").strip().lower()
            if retry != 'y':
                return None
    elif choice == '2':
        success = run_manual_spec_flow(project_dir)
        if not success:
            return None

    return project_name


def fetch_opencode_models() -> list[str]:
    """Fetch Go subscription models (paid + free) from the running OpenCode server."""
    try:
        r = httpx.get(f"{OPENCODE_SERVER_URL}/provider", timeout=3)
        paid, free = [], []
        for p in r.json().get("all", []):
            pid = p.get("id")
            if pid == "opencode-go":
                paid = sorted(f"opencode-go/{mid}" for mid in p["models"])
            elif pid == "opencode":
                free = sorted(f"opencode/{mid}" for mid in p["models"])
        models = paid + free
        return models if models else _fallback_models()
    except Exception:
        return _fallback_models()


def _fallback_models() -> list[str]:
    return [
        "opencode-go/deepseek-v4-pro",
        "opencode-go/deepseek-v4-flash",
        "opencode-go/kimi-k2.6",
        "opencode-go/qwen3.6-plus",
        "opencode/deepseek-v4-flash-free",
        "opencode/big-pickle",
    ]


def select_model(default: str = "opencode-go/deepseek-v4-pro") -> str:
    """Prompt the user to pick a model from the available list."""
    models = fetch_opencode_models()

    print("\n" + "-" * 50)
    print("  Select Model")
    print("-" * 50)
    prev_provider = None
    for i, m in enumerate(models, 1):
        provider = m.split("/")[0]
        if provider != prev_provider:
            label = "Go subscription (paid)" if provider == "opencode-go" else "Free tier"
            print(f"\n  -- {label} --")
            prev_provider = provider
        marker = " (default)" if m == default else ""
        print(f"  [{i}] {m}{marker}")
    print(f"\n  [Enter] Use default ({default})")
    print()

    while True:
        choice = input("Model number or Enter for default: ").strip()
        if choice == "":
            return default
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
            print(f"Please enter a number between 1 and {len(models)}")
        except ValueError:
            print("Invalid input.")


def run_agent(project_name: str) -> None:
    """Run the autonomous agent with the given project."""
    project_dir = GENERATIONS_DIR / project_name

    # Verify OpenCode server is reachable before launching the agent
    if not check_opencode_server():
        return

    # Final validation before running
    if not has_project_prompts(project_dir):
        print(f"\nWarning: No valid spec found for project '{project_name}'")
        print("The agent may not work correctly.")
        confirm = input("Continue anyway? [y/N]: ").strip().lower()
        if confirm != 'y':
            return

    # Let user choose the model
    model = select_model()

    print(f"\nStarting agent for project: {project_name}")
    print(f"Model: {model}")
    print("-" * 50)

    # Build the command
    cmd = [sys.executable, "autonomous_agent_demo.py", "--project-dir", project_name, "--model", model]

    # Run the agent
    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        print("\n\nAgent interrupted. Run again to resume.")


def main() -> None:
    """Main entry point."""
    # Ensure we're in the right directory
    script_dir = Path(__file__).parent.absolute()
    os.chdir(script_dir)

    while True:
        projects = get_existing_projects()
        display_menu(projects)

        choice = input("Select option: ").strip().lower()

        if choice == 'q':
            print("\nGoodbye!")
            break

        elif choice == '1':
            project_name = create_new_project_flow()
            if project_name:
                run_agent(project_name)

        elif choice == '2' and projects:
            display_projects(projects)
            selected = get_project_choice(projects)
            if selected:
                run_agent(selected)

        else:
            print("Invalid option. Please try again.")


if __name__ == "__main__":
    main()
