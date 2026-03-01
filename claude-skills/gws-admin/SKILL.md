---
name: gws-admin
description: Google Workspace Admin CLI (GAM7 wrapper). Manage users, groups, org units, aliases, devices, and licenses with safety guardrails, JSON output, and raw GAM passthrough. Requires GAM7 and super admin access.
---

# GWS Admin

Manage Google Workspace via GAM7. Provides organized subcommands for users, groups, org units, aliases, devices, and licenses with safety guardrails on destructive operations. All list/info commands support `--json` output. Includes a setup wizard and raw GAM passthrough.

## Usage

```bash
GWS="uv run ~/.claude/skills/gws-admin/gws-admin.py"
```

## Commands

### Setup & Status

```bash
$GWS setup                    # First-time GAM install + OAuth + service account
$GWS status                   # Check GAM install, config files, connectivity
```

### Users

```bash
$GWS users list [--json]
$GWS users info alice@example.com
$GWS users create bob@example.com --firstname Bob --lastname Smith --password 'TempPass123!' [--org /Engineering]
$GWS users update bob@example.com [--suspended on|off] [--org /Sales] [--password 'NewPass!']
$GWS users delete bob@example.com --dry-run    # Preview
$GWS users delete bob@example.com --confirm    # Execute
```

### Groups

```bash
$GWS groups list [--json]
$GWS groups info engineering@example.com
$GWS groups create devops@example.com --name "DevOps Team" [--description "DevOps engineers"]
$GWS groups add-member devops@example.com alice@example.com [--role manager|member|owner]
$GWS groups remove-member devops@example.com bob@example.com
```

### Organizational Units

```bash
$GWS orgs list [--json]
$GWS orgs create /Engineering/Frontend [--description "Frontend team"]
$GWS orgs info /Engineering
```

### Email Aliases

```bash
$GWS aliases list [alice@example.com]
$GWS aliases create support@example.com --target alice@example.com
$GWS aliases delete support@example.com --confirm
```

### Devices

```bash
$GWS devices list [--json]
$GWS devices wipe DEVICE_RESOURCE_ID --dry-run     # Preview
$GWS devices wipe DEVICE_RESOURCE_ID --confirm     # Execute
```

### Licenses

```bash
$GWS licenses list [--json]
```

### Raw GAM Passthrough

```bash
$GWS raw info domain
$GWS raw print cros
$GWS raw create resource calendar "Room A" capacity 10
```

## Global Flags

- `--json` — Output in JSON format (works with any list/info command)
- `--dry-run` — Show the GAM command that would run without executing it

## Safety Guardrails

Destructive operations (`users delete`, `aliases delete`, `devices wipe`) require `--confirm` to execute. Without it, they print a warning and exit.

## Data Storage

GAM configuration and credentials are stored at `~/.claude/skills/gws-admin/gam-config/`.

## Prerequisites

- **Python 3.10+**
- **Google Workspace** account with **super admin** access
- **Browser access** for initial OAuth flow (GAM opens a browser for auth)
- GAM7 is installed automatically by the `setup` command

## Tips

- Use `--dry-run` on any command to preview the GAM invocation
- Passwords can be passed via `--password`, stdin (`--password -`), or `GWS_USER_PASSWORD` env var
- The `raw` passthrough prints the exact GAM command being executed
- All destructive operations are logged in the Google Admin Console audit log
