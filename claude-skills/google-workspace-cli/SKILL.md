---
name: google-workspace-cli
description: Google Workspace CLI for Gmail, Calendar, and Drive. Multi-profile support, JSON output for agent consumption. Read/send emails, manage calendar events, search and download Drive files.
---

# Google Workspace CLI

Access Gmail, Calendar, and Drive from the command line. Multi-account support with named profiles (like AWS CLI). JSON output mode for agent consumption.

## Usage

```bash
GWCLI="gwcli"
```

Requires `npm install && npm run build && npm link` from the skill directory first.

## Commands

### Profile Management

```bash
$GWCLI profiles add personal --client ~/Downloads/client_secret_*.json
$GWCLI profiles set-default personal
$GWCLI profiles list
$GWCLI profiles remove <name>
```

### Gmail

```bash
$GWCLI gmail list [--unread] [--limit 20] --format json
$GWCLI gmail search "from:boss@example.com" --format json
$GWCLI gmail read <message-id>
$GWCLI gmail thread <thread-id>
$GWCLI gmail draft --to user@example.com --subject "Hello" --body "Message"
$GWCLI gmail send <draft-id>
$GWCLI gmail send --to user@example.com --subject "Hello" --body "Message"
$GWCLI gmail reply <message-id> --body "Thanks for your email"
$GWCLI gmail archive <message-id>
$GWCLI gmail trash <message-id>
```

### Calendar

```bash
$GWCLI calendar list --format json
$GWCLI calendar events [--days 14] [--limit 20] --format json
$GWCLI calendar search "meeting" --format json
$GWCLI calendar create "Team Meeting" --start "2025-01-15 10:00" --end "2025-01-15 11:00"
$GWCLI calendar create "Lunch" --start "tomorrow 12:00"
$GWCLI calendar update <event-id> --title "New Title" --start "2025-01-15 14:00"
$GWCLI calendar delete <event-id>
```

### Drive

```bash
$GWCLI drive list [--folder <folder-id>] [--limit 50] --format json
$GWCLI drive search "name contains 'report'" --format json
$GWCLI drive download <file-id> [--output ~/Downloads/report.pdf]
$GWCLI drive export <doc-id> --format pdf
$GWCLI drive export <sheet-id> --format xlsx
$GWCLI drive export <slide-id> --format pptx
```

### Output Formats

- `--format json` — JSON (for agent consumption)
- `--format table` — Formatted table (default)
- `--format text` — Plain text

### Profile Selection

```bash
$GWCLI --profile work gmail list    # Use specific profile
GWCLI_PROFILE=work gwcli gmail list # Via environment variable
$GWCLI gmail list                   # Uses default profile
```

## Data Storage

Config and credentials at `~/.config/gwcli/`:

- `config.json` — Global settings, default profile
- `profiles/<name>/credentials.json` — OAuth tokens per profile
- `profiles/<name>/config.json` — Profile metadata

## Prerequisites

- Node.js 18+
- Google Cloud project with Gmail API, Calendar API, and Drive API enabled
- OAuth Desktop App credentials (client_secret JSON)

## Setup

1. Create OAuth credentials in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Gmail, Calendar, and Drive APIs
3. `cd` into skill directory: `npm install && npm run build && npm link`
4. `gwcli profiles add <name> --client <path-to-client-secret.json>`

## Tips

- Always use `--format json` when invoking from Claude Code for structured output
- Profile tokens auto-refresh; re-auth only needed if revoked
- Google Workspace admin access not required — works with regular Google accounts too
