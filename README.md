# Autonomous Coding Agent

A long-running autonomous coding agent powered by [OpenCode](https://opencode.ai). Builds complete applications over multiple sessions using a two-agent pattern (initializer + coding agent).

> Originally based on [leonvanzyl/autonomous-coding](https://github.com/leonvanzyl/autonomous-coding), ported from the Anthropic Claude Agent SDK to OpenCode with Go subscription support.

---

## Prerequisites

### 1. OpenCode CLI

Install the OpenCode CLI:

```powershell
npm install -g opencode-ai
```

### 2. OpenCode Go Subscription

Sign up at [opencode.ai/go](https://opencode.ai/go) ($5 first month, $10/month).

Log in to configure your credentials:

```powershell
opencode providers login
```

### 3. Python 3.8+

Required Python packages are listed in `requirements.txt`.

---

## Quick Start

### 1. Install Python dependencies

```powershell
pip install -r requirements.txt
```

### 2. Configure your token

Copy `.env.example` to `.env` and set your OpenCode auth token:

```
OPENCODE_AUTH_TOKEN=your_token_here
```

Get your token from [opencode.ai/go](https://opencode.ai/go).

### 3. Start the OpenCode server

In a **separate terminal**, run:

```powershell
opencode serve --port 4096
```

Keep this terminal open while the agent runs.

### 4. Run the agent

```powershell
python start.py
```

You'll see a menu to create a new project or continue an existing one.

---

## How It Works

### Two-Agent Pattern

1. **Initializer Agent (First Session):** Reads your app specification, creates a `feature_list.json` with test cases, and sets up the project structure.

2. **Coding Agent (Subsequent Sessions):** Picks up where the previous session left off, implements features one by one, and marks them as passing in `feature_list.json`.

### Session Management

- Each session creates a fresh OpenCode session (clean context window)
- Progress is persisted via `feature_list.json` and git commits
- The agent auto-continues between sessions (3 second delay)
- Press `Ctrl+C` to pause; run `python start.py` again to resume

---

## Model Selection

When you start a project, the app fetches available models live from the OpenCode server and lets you pick:

```
  -- Go subscription (paid) --
  [1] opencode-go/deepseek-v4-flash
  [2] opencode-go/deepseek-v4-pro  (default)
  [3] opencode-go/kimi-k2.6
  ...

  -- Free tier --
  [13] opencode/deepseek-v4-flash-free
  ...
```

Recommended for coding: **deepseek-v4-pro** (default) or **deepseek-v4-flash** for faster/cheaper runs.

---

## Timing Expectations

- **First session (initialization):** Generates feature test cases. Takes several minutes and may appear to hang — this is normal. Watch for `[Tool: ...]` output.
- **Subsequent sessions:** Each coding iteration takes **5–15 minutes** depending on complexity.
- **Full app:** Building all features typically requires **many hours** across multiple sessions.

For faster demos, target fewer features in your app spec (20–50 instead of 200).

---

## Project Structure

```
autocoder/
├── start.py                  # Main menu and project management
├── autonomous_agent_demo.py  # Agent entry point and CLI
├── agent.py                  # Agent session loop logic
├── client.py                 # OpenCode HTTP client wrapper
├── progress.py               # Feature progress tracking (SQLite)
├── prompts.py                # Prompt loading utilities
├── security.py               # Bash command allowlist (reference)
├── opencode.jsonc            # OpenCode server config (model + MCP)
├── mcp_server/
│   └── feature_mcp.py       # MCP server for feature tracking tools
├── .claude/
│   └── commands/
│       └── create-spec.md   # Spec creation prompt template
├── generations/              # Generated projects land here
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variable template
└── .env                      # Your credentials (not committed)
```

---

## Generated Project Structure

```
generations/my_project/
├── feature_list.json         # Test cases (source of truth for progress)
├── prompts/
│   ├── app_spec.txt          # Your app specification
│   ├── initializer_prompt.md # First session prompt
│   └── coding_prompt.md      # Continuation session prompt
├── init.sh                   # Environment setup script (created by agent)
└── [application files]       # Generated application code
```

---

## Running the Generated Application

```bash
cd generations/my_project
./init.sh          # Run setup script created by the agent
# Or manually:
npm install && npm run dev
```

The app will typically be available at `http://localhost:3000`.

---

## Configuration

### opencode.jsonc

Controls which model and MCP servers the OpenCode server uses:

```jsonc
{
  "model": "opencode-go/deepseek-v4-pro",
  "mcp": {
    "playwright": { "type": "local", "command": ["npx", "-y", "@playwright/mcp@latest"] },
    "features":   { "type": "local", "command": ["python", "-m", "mcp_server.feature_mcp"] }
  }
}
```

### N8N Webhook (optional)

Add to `.env` to receive progress notifications:

```
PROGRESS_N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/your-id
```

---

## Troubleshooting

**"OpenCode server is not running"**
Start it in a separate terminal: `opencode serve --port 4096`

**"Failed to start server on port 4096"**
Port is already in use. Kill the process:
```powershell
Get-NetTCPConnection -LocalPort 4096 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```
Then run `opencode serve --port 4096` again.

**"Error during agent session" (repeated)**
Check the full traceback printed below the error. Common causes:
- Model rate limit hit — wait a minute and retry
- Session timeout — the default has no read timeout so this should be rare
- Network issue to OpenCode server

**"Appears to hang on first run"**
Normal — the initializer is generating test cases. Watch for `[Tool: ...]` output to confirm it's working.
