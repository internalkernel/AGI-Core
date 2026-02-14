---
name: slack
description: Control Slack — react to messages, pin/unpin, send/edit/delete messages, read channels, search, and fetch member info. All output is JSON for agent consumption.
---

# Slack Actions

CLI for Slack operations. All output is JSON. Requires `SLACK_BOT_TOKEN` env var.

## Usage

```bash
uv run ~/.openclaw/skills/slack/scripts/slack.py <action> [options]
```

## Actions

### Messages

```bash
# Read recent messages from a channel
uv run ~/.openclaw/skills/slack/scripts/slack.py read --channel C123 [--limit 20]

# Read thread replies
uv run ~/.openclaw/skills/slack/scripts/slack.py read --channel C123 --thread 1712023032.1234

# Send a message
uv run ~/.openclaw/skills/slack/scripts/slack.py send --to C123 --text "Hello"

# Reply in a thread
uv run ~/.openclaw/skills/slack/scripts/slack.py send --to C123 --text "Reply" --thread 1712023032.1234

# Edit a message (bot's own messages only)
uv run ~/.openclaw/skills/slack/scripts/slack.py edit --channel C123 --message 1712023032.1234 --text "Updated"

# Delete a message (bot's own messages only)
uv run ~/.openclaw/skills/slack/scripts/slack.py delete --channel C123 --message 1712023032.1234

# Search messages
uv run ~/.openclaw/skills/slack/scripts/slack.py search --query "keyword" [--limit 20]
```

### Reactions

```bash
# React to a message
uv run ~/.openclaw/skills/slack/scripts/slack.py react --channel C123 --message 1712023032.1234 --emoji white_check_mark

# List reactions on a message
uv run ~/.openclaw/skills/slack/scripts/slack.py reactions --channel C123 --message 1712023032.1234
```

### Pins

```bash
# Pin a message
uv run ~/.openclaw/skills/slack/scripts/slack.py pin --channel C123 --message 1712023032.1234

# Unpin a message
uv run ~/.openclaw/skills/slack/scripts/slack.py unpin --channel C123 --message 1712023032.1234

# List pinned items
uv run ~/.openclaw/skills/slack/scripts/slack.py pins --channel C123
```

### Info

```bash
# Get user info
uv run ~/.openclaw/skills/slack/scripts/slack.py member-info --user U123

# List channels
uv run ~/.openclaw/skills/slack/scripts/slack.py channels [--limit 100]

# List custom emoji
uv run ~/.openclaw/skills/slack/scripts/slack.py emoji-list
```

## Setup

Requires `SLACK_BOT_TOKEN` env var (xoxb-...) from a Slack app with these scopes:
- `channels:history`, `groups:history` — read messages
- `chat:write` — send/edit/delete messages
- `reactions:read`, `reactions:write` — reactions
- `pins:read`, `pins:write` — pins
- `users:read`, `users:read.email` — member info
- `channels:read`, `groups:read` — list channels
- `emoji:read` — custom emoji list
- `search:read` — search (requires user token)

## Tips

- Message IDs are Slack timestamps (e.g. `1712023032.1234`)
- Message context lines include `slack message id` and `channel` fields you can reuse
- React with checkmarks to acknowledge tasks, pin key decisions
- All responses include `"ok": true/false` for easy error checking
