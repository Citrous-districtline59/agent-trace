# Using agent-trace with Claude Code

## How it works

Claude Code launches MCP servers as subprocesses over stdio. agent-trace sits
between Claude Code and the MCP server, capturing every tool call.

```
Claude Code ←→ agent-trace record ←→ MCP Server
                     ↓
              .agent-traces/
```

## Setup

### 1. Install agent-trace

```bash
# With uv (recommended)
uv tool install agent-trace

# Or with pip
pip install agent-trace
```

### 2. Add a traced MCP server

Use `claude mcp add` with agent-trace wrapping the server command:

```bash
# Instead of:
claude mcp add filesystem -- npx -y @modelcontextprotocol/server-filesystem /tmp

# Use:
claude mcp add filesystem -- agent-trace record --name filesystem -- npx -y @modelcontextprotocol/server-filesystem /tmp
```

The `--name` flag tags the session so you can identify which server it came from.

### 3. Or edit .claude/mcp.json directly

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "agent-trace",
      "args": [
        "record",
        "--name", "filesystem",
        "--",
        "npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp"
      ]
    }
  }
}
```

### 4. Use Claude Code normally

Every tool call Claude Code makes through the MCP server is now traced.

### 5. Replay the session

```bash
# List all sessions
agent-trace list

# Replay the latest
agent-trace replay

# Show stats
agent-trace stats
```
