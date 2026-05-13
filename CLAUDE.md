# CLAUDE.md — Autonomous Coding Agent

## What this project is

A long-running autonomous coding agent that builds complete web applications over multiple sessions. Ported from the Anthropic `claude-agent-sdk` to [OpenCode](https://opencode.ai) with Go subscription support.

## Architecture

**Two-agent pattern:**
1. **Initializer** — reads `prompts/app_spec.txt`, creates `feature_list.json` with ~200 test cases, scaffolds the project
2. **Coding agent** — implements features one at a time, marks them passing via the `features` MCP server

**Session persistence:** Each Python iteration creates a fresh OpenCode session (clean context). Progress survives restarts via SQLite (`feature_list.json`) and git commits.

## Key files

| File | Role |
|---|---|
| `start.py` | Main menu — project creation, model selection, server health check |
| `autonomous_agent_demo.py` | CLI entry point, parses `--project-dir` / `--model` args |
| `agent.py` | Session loop — creates OpenCode session, sends prompt, parses parts |
| `client.py` | `OpencodeClient` — thin httpx wrapper around OpenCode REST API |
| `progress.py` | SQLite-backed feature progress tracking |
| `prompts.py` | Loads initializer/coding prompts from `generations/<project>/prompts/` |
| `security.py` | Bash allowlist (reference only — not enforced via hooks in OpenCode) |
| `opencode.jsonc` | OpenCode server config: model + MCP servers |
| `mcp_server/feature_mcp.py` | MCP server exposing feature DB tools to the agent |

## Running locally

**Prerequisite:** OpenCode server must be running in a separate terminal:
```powershell
opencode serve --port 4097
```
> Port 4096 is reserved by the Kilo Code VS Code extension. Use 4097.

**Start the agent:**
```powershell
python start.py
```

## OpenCode client API

The `OpencodeClient` in `client.py` wraps two endpoints:

```
POST /session          body: {directory?}         → {id, ...}
POST /session/:id/message  body: {parts, model: {modelID, providerID}, system?}  → {parts}
```

**Important:** The `model` field must be a nested object `{modelID, providerID}` — NOT a plain string. The `opencode-ai` Python SDK has a schema mismatch so we use httpx directly.

## Model format

Models use `"providerID/modelID"` strings:
- Paid Go subscription: `opencode-go/deepseek-v4-pro`, `opencode-go/deepseek-v4-flash`, `opencode-go/kimi-k2.6`
- Free tier: `opencode/deepseek-v4-flash-free`, `opencode/big-pickle`

Provider split happens in `client.py`: `provider_id, model_id = model.split("/", 1)`

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `OPENCODE_AUTH_TOKEN` | Yes | OpenCode Go subscription token |
| `PROJECT_DIR` | Set at runtime | Tells the features MCP server which SQLite DB to use |
| `PROGRESS_N8N_WEBHOOK_URL` | No | Optional N8N webhook for progress notifications |

## Spec creation flow

`start.py` offers two paths when creating a new project:
1. **AI-assisted** — interactive chat in the terminal; uses a fresh OpenCode session per turn (passing full conversation history in the prompt). Multi-turn reuse of a single session causes a silent deadlock where the server never forwards the second message to the LLM.
2. **Manual** — opens `app_spec.txt` in VS Code automatically, waits for Enter.

The AI path hardcodes `opencode-go/deepseek-v4-pro` for the interview; model selection for the actual coding agent happens separately.

## Known gotchas

- **Port conflict with Kilo Code:** The Kilo Code VS Code extension (`kilo.exe`) occupies port 4096. Use port 4097 for `opencode serve`. `check_opencode_server()` now detects this via `www-authenticate: Basic` on the 401 response and prints a clear error.
- **Multi-turn session deadlock:** Sending a second REST message to the same OpenCode session while the first is still being processed server-side causes a silent hang (no LLM call is made). Use a fresh session per turn with conversation history in the prompt instead.
- **Session directory:** OpenCode server ignores the `directory` field in session creation — the project path is injected via the system prompt instead
- **opencode-ai SDK:** The alpha SDK sends `modelID`/`providerID` as flat fields; server wants them in `model: {modelID, providerID}`. We bypass the SDK and use httpx directly
- **No read timeout:** Agent sessions can take many minutes with tool calls — `httpx.Timeout(connect=10, read=None, write=60, pool=10)` is intentional
- **`load_dotenv()` in start.py:** Must be called before any OpenCode API calls so `OPENCODE_AUTH_TOKEN` is in the environment (needed by `client.py` to add the Bearer header)
