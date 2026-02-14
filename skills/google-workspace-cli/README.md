# google-workspace-cli

Google Workspace CLI with multi-profile support for Gmail, Calendar, and Drive. Designed for both human use and LLM agent integration.

## Why This Exists

This CLI was built specifically to give LLM agents (like Claude Code) access to Google Workspace.

**Why CLI instead of MCP?** CLIs are more context-efficient. MCP servers require tool schemas to be loaded into the agent's context window on every request. A CLI skill only needs a concise command reference, and the agent invokes it via standard shell execution. Same capabilities, fewer tokens.

The JSON output mode provides structured data that agents can parse and act on.

**Use cases:**
- Let Claude Code read and respond to your emails
- Have an AI agent manage your calendar
- Search and retrieve Google Drive files programmatically

## Features

- **Multi-account support** - Named profiles like AWS CLI (e.g., `personal`, `work`)
- **Gmail** - List, search, read, archive, draft, send, reply
- **Calendar** - List calendars, view events, create/update/delete events
- **Drive** - List, search, download files, export Google Docs/Sheets/Slides
- **Flexible output** - JSON (for agents), table, or text format

## Installation

```bash
git clone https://github.com/ianpatrickhines/google-workspace-cli.git
cd google-workspace-cli
npm install
npm run build
npm link
```

## Setup

### 1. Create Google Cloud OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable APIs:
   - Gmail API
   - Google Calendar API
   - Google Drive API
4. Go to **APIs & Services > Credentials**
5. Click **Create Credentials > OAuth client ID**
6. Select **Desktop app** as application type
7. Download the JSON file

### 2. Add a Profile

```bash
gwcli profiles add personal --client ~/Downloads/client_secret_*.json
```

This opens a browser for Google authentication. After authorizing, the tokens are stored locally.

### 3. Set Default Profile (optional)

```bash
gwcli profiles set-default personal
```

## Usage

### Profile Selection

```bash
gwcli --profile work gmail list     # Use specific profile
GWCLI_PROFILE=work gwcli gmail list # Via environment variable
gwcli gmail list                    # Uses default profile
```

### Gmail

```bash
# List recent emails
gwcli gmail list
gwcli gmail list --unread --limit 20

# Search emails
gwcli gmail search "from:boss@example.com"
gwcli gmail search "subject:invoice is:unread"

# Read email
gwcli gmail read <message-id>
gwcli gmail thread <thread-id>

# Compose and send
gwcli gmail draft --to user@example.com --subject "Hello" --body "Message"
gwcli gmail send <draft-id>
gwcli gmail send --to user@example.com --subject "Hello" --body "Message"

# Reply to a message
gwcli gmail reply <message-id> --body "Thanks for your email"

# Archive or trash
gwcli gmail archive <message-id>
gwcli gmail trash <message-id>
```

### Calendar

```bash
# List calendars
gwcli calendar list

# View upcoming events
gwcli calendar events
gwcli calendar events --days 14 --limit 20

# Search events
gwcli calendar search "meeting"

# Create event
gwcli calendar create "Team Meeting" --start "2025-01-15 10:00" --end "2025-01-15 11:00"
gwcli calendar create "Lunch" --start "tomorrow 12:00"

# Update event
gwcli calendar update <event-id> --title "New Title" --start "2025-01-15 14:00"

# Delete event
gwcli calendar delete <event-id>
```

### Drive

```bash
# List files
gwcli drive list
gwcli drive list --folder <folder-id> --limit 50

# Search files
gwcli drive search "name contains 'report'"
gwcli drive search "mimeType = 'application/pdf'"

# Download file
gwcli drive download <file-id>
gwcli drive download <file-id> --output ~/Downloads/report.pdf

# Export Google Docs/Sheets/Slides
gwcli drive export <doc-id> --format pdf
gwcli drive export <sheet-id> --format xlsx
gwcli drive export <slide-id> --format pptx
```

### Output Formats

```bash
gwcli gmail list --format json    # JSON (for scripting/Claude Code)
gwcli gmail list --format table   # Formatted table (default)
gwcli gmail list --format text    # Plain text
```

## Profile Management

```bash
gwcli profiles list               # List all profiles
gwcli profiles add <name> --client <path>  # Add new profile
gwcli profiles remove <name>      # Delete profile
gwcli profiles set-default <name> # Set default profile
```

## Configuration

Config files are stored in `~/.config/gwcli/`:

```
~/.config/gwcli/
├── config.json                   # Global settings, default profile
└── profiles/
    ├── personal/
    │   ├── credentials.json      # OAuth tokens
    │   └── config.json           # Profile metadata
    └── work/
        └── credentials.json
```

## LLM Agent Integration

### Claude Code

To use with Claude Code, create a skill file that teaches it how to use the CLI.

**Example skill** (`~/.claude/skills/gwcli/SKILL.md`):

```yaml
---
name: gwcli
description: "Google Workspace CLI for Gmail, Calendar, and Drive. Use when reading/sending emails, managing calendar events, or accessing Drive files."
---
```

Then add command reference and examples in the skill body. The key is using `--format json` so Claude can parse the output:

```bash
# Claude can parse this structured output
gwcli gmail list --format json
gwcli calendar events --format json
```

### Other LLM Agents

Any agent that can execute shell commands can use this CLI. The JSON output mode provides structured data:

```bash
# Returns JSON array of emails
gwcli gmail list --format json

# Returns JSON array of calendar events
gwcli calendar events --days 7 --format json

# Returns JSON array of files
gwcli drive list --format json
```

### Pre-Approving Commands

For Claude Code, you can pre-approve gwcli commands in your settings so the agent can run them without confirmation:

```json
{
  "permissions": {
    "allow": [
      "Bash(gwcli:*)"
    ]
  }
}
```

## License

MIT
