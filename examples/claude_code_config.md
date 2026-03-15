# Using agent-trace with Claude Code

## How it works

Claude Code has a [hooks system](https://code.claude.com/docs/en/hooks) that fires
events before and after every tool call. agent-trace registers hooks for these events
to capture the full session: every Bash command, file edit, file read, web fetch,
subagent spawn, and MCP tool call.

```
Claude Code agentic loop
  ├── PreToolUse   → agent-strace hook pre-tool         (logs tool_call)
  ├── PostToolUse  → agent-strace hook post-tool         (logs tool_result)
  ├── PostToolUseFailure → agent-strace hook post-tool-failure (logs error)
  ├── SessionStart → agent-strace hook session-start     (starts trace)
  └── SessionEnd   → agent-strace hook session-end       (closes trace)
                          ↓
                    .agent-traces/
```

This captures all tool calls, not just MCP. Claude Code's built-in tools (Bash, Edit,
Write, Read, Agent, Grep, Glob, WebFetch, WebSearch) are all traced.

## Setup

### 1. Install agent-trace

```bash
# With uv (recommended)
uv tool install agent-strace

# Or with pip
pip install agent-strace
```

### 2. Generate the hooks config

```bash
# For this project only
agent-strace setup

# For all projects (global)
agent-strace setup --global

# With secret redaction
agent-strace setup --redact
```

This prints the JSON you need to add to your settings file.

### 3. Add to Claude Code settings

**Per-project** (`.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "agent-strace hook pre-tool" }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "agent-strace hook post-tool" }
        ]
      }
    ],
    "PostToolUseFailure": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": "agent-strace hook post-tool-failure" }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "agent-strace hook session-start" }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          { "type": "command", "command": "agent-strace hook session-end" }
        ]
      }
    ]
  }
}
```

**Global** (`~/.claude/settings.json`): same structure, traces every project.

### 4. Use Claude Code normally

Every tool call is now traced. Claude Code does not know the hooks exist.

### 5. Replay the session

```bash
# List all sessions
agent-strace list

# Replay the latest
agent-strace replay

# Show stats
agent-strace stats
```

## What gets captured

| Claude Code tool | Trace event type | Example data |
|---|---|---|
| `Bash` | tool_call / tool_result | command, output |
| `Edit` | tool_call / tool_result | file path, old/new text |
| `Write` | tool_call / tool_result | file path, content |
| `Read` | tool_call / tool_result | file path |
| `Agent` | tool_call / tool_result | subagent task |
| `Grep` | tool_call / tool_result | pattern, matches |
| `Glob` | tool_call / tool_result | pattern, files found |
| `WebFetch` | tool_call / tool_result | URL, response |
| `WebSearch` | tool_call / tool_result | query, results |
| `mcp__*` | tool_call / tool_result | any MCP server tool |

Failed tool calls are logged as `error` events with the failure message.

## Secret redaction

To redact API keys, tokens, and credentials from traces:

```bash
# Option 1: set the environment variable
export AGENT_TRACE_REDACT=1

# Option 2: generate config with redaction baked in
agent-strace setup --redact
```

With redaction enabled, the hook commands are prefixed with `AGENT_TRACE_REDACT=1`.

## Trace storage

Traces are stored in `.agent-traces/` in the current directory. Each session gets
a directory with `meta.json` and `events.ndjson`. Add `.agent-traces/` to your
`.gitignore`.

## Comparison with MCP proxy mode

| | Hooks mode | MCP proxy mode |
|---|---|---|
| What it captures | All Claude Code tool calls | Only MCP server messages |
| Setup | Add hooks to settings.json | Wrap MCP server command |
| Works with | Claude Code only | Any MCP client |
| Overhead | One process spawn per tool call | Persistent proxy process |

Use hooks mode when you want the full picture of a Claude Code session.
Use MCP proxy mode when you want to trace a specific MCP server across any client.
