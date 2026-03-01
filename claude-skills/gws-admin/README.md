# Google Workspace Admin Skill (GAM7 Wrapper)

An OpenClaw skill for managing Google Workspace from the CLI. Wraps [GAM7](https://github.com/GAM-team/GAM) with organized subcommands, safety guardrails, JSON output for agent consumption, and a guided setup wizard.

## Prerequisites

- **Python 3.10+** and **pip**
- **Google Workspace** account with **super admin** access
- **Browser access** for the initial OAuth flow (GAM opens a browser for Google auth)

## Quick Start

```bash
# 1. Run the setup wizard (installs GAM, creates GCP project, authorizes OAuth)
uv run gws-admin.py setup

# 2. Verify everything works
uv run gws-admin.py status

# 3. Start managing your workspace
uv run gws-admin.py users list
```

## First-Time Setup Walkthrough

The `setup` command automates most steps, but here's what happens under the hood:

### Step 1: Install GAM7

The setup wizard installs GAM via pip:
```bash
pip install advanced-gam-for-google-workspace
```

### Step 2: Create a GCP Project

GAM needs a Google Cloud Platform project with the appropriate APIs enabled. The `gam create project` command:
1. Opens a browser for Google sign-in (use your super admin account)
2. Creates a new GCP project named "GAM Project"
3. Enables the required Google Workspace APIs:
   - Admin SDK API
   - Gmail API
   - Google Calendar API
   - Google Drive API
   - Groups Settings API
   - Contacts API
   - Google Sheets API
   - License Manager API
   - People API

### Step 3: OAuth Authorization

`gam oauth create` authorizes GAM to act on behalf of your admin account:
1. Opens a browser showing the OAuth consent screen
2. Select the scopes GAM needs (the default selection covers all standard operations)
3. Approve access

### Step 4: Service Account & Domain-Wide Delegation

`gam update serviceaccount` and `gam check serviceaccount` configure a service account for automated access:

1. GAM creates/updates a service account in your GCP project
2. You need to authorize domain-wide delegation in the **Google Admin console**:
   - Go to **Admin Console** → **Security** → **API Controls** → **Domain-wide Delegation**
   - Click **Add new**
   - Enter the **Client ID** shown by GAM during setup
   - Add the required **OAuth scopes** (GAM will list them)
   - Click **Authorize**

### Step 5: Verify

```bash
uv run gws-admin.py status
```

This checks that GAM is installed, all config files are present, and runs `gam info domain` to verify connectivity.

## Configuration

All GAM configuration and credentials are stored in:

```
~/.claude/skills/gws-admin/gam-config/
├── gam.cfg                 # Main config
├── client_secrets.json     # OAuth client credentials
├── oauth2.txt              # Authorized OAuth tokens
├── oauth2service.json      # Service account key
└── gamcache/               # API response cache
```

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `GAMCFGDIR` | GAM config directory | `~/.claude/skills/gws-admin/gam-config/` |
| `GAM_ADMIN_EMAIL` | Admin email for domain-wide ops | Read from `gam.cfg` |

## Command Reference

### Setup & Status

```bash
gws-admin.py setup     # First-time install and configuration wizard
gws-admin.py status    # Check GAM install, config files, and connectivity
```

### Users

```bash
# List all users
gws-admin.py users list
gws-admin.py users list --json

# Get user details
gws-admin.py users info alice@example.com

# Create a user
gws-admin.py users create bob@example.com \
  --firstname Bob --lastname Smith --password 'TempPass123!' \
  --org /Engineering

# Update user attributes
gws-admin.py users update bob@example.com --suspended on
gws-admin.py users update bob@example.com --org /Sales
gws-admin.py users update bob@example.com --password 'NewPass456!'

# Delete a user (requires --confirm)
gws-admin.py users delete bob@example.com --dry-run    # Preview
gws-admin.py users delete bob@example.com --confirm    # Execute
```

### Groups

```bash
# List all groups
gws-admin.py groups list
gws-admin.py groups list --json

# Get group details and members
gws-admin.py groups info engineering@example.com

# Create a group
gws-admin.py groups create devops@example.com \
  --name "DevOps Team" --description "DevOps engineers"

# Add/remove members
gws-admin.py groups add-member devops@example.com alice@example.com --role manager
gws-admin.py groups remove-member devops@example.com bob@example.com
```

### Organizational Units

```bash
# List all org units
gws-admin.py orgs list
gws-admin.py orgs list --json

# Create an org unit
gws-admin.py orgs create /Engineering/Frontend --description "Frontend team"

# Get org unit details
gws-admin.py orgs info /Engineering
```

### Email Aliases

```bash
# List all aliases (or for a specific user)
gws-admin.py aliases list
gws-admin.py aliases list alice@example.com

# Create an alias
gws-admin.py aliases create support@example.com --target alice@example.com

# Delete an alias (requires --confirm)
gws-admin.py aliases delete support@example.com --confirm
```

### Devices

```bash
# List mobile devices
gws-admin.py devices list
gws-admin.py devices list --json

# Remote wipe a device (requires --confirm)
gws-admin.py devices wipe DEVICE_RESOURCE_ID --dry-run    # Preview
gws-admin.py devices wipe DEVICE_RESOURCE_ID --confirm    # Execute
```

### Licenses

```bash
# List license assignments
gws-admin.py licenses list
gws-admin.py licenses list --json
```

### Raw GAM Passthrough

For any GAM command not covered by the wrapper:

```bash
# Run any GAM command directly
gws-admin.py raw info domain
gws-admin.py raw print cros
gws-admin.py raw create resource calendar "Room A" capacity 10
```

## Safety Guardrails

### Destructive Operation Protection

Commands that delete data or affect device state require the `--confirm` flag:

- `users delete` — deletes a user account
- `aliases delete` — removes an email alias
- `devices wipe` — remotely wipes a mobile device

Without `--confirm`, these commands print what would happen and exit without taking action.

### Dry Run Mode

All commands support `--dry-run`, which shows the GAM command that would be executed without running it:

```bash
gws-admin.py users delete alice@example.com --dry-run
# Output: [DRY RUN] Would execute:
#   gam delete user alice@example.com
```

### Raw Command Transparency

The `raw` passthrough always prints the exact GAM command being executed:

```bash
gws-admin.py raw update user alice@example.com suspended on
# Output: [RAW] Executing: gam update user alice@example.com suspended on
```

## DevOps Agent Integration

### OpenClaw Invocation

From an OpenClaw agent, invoke the skill via:

```bash
uv run ~/.claude/skills/gws-admin/gws-admin.py users list --json
```

### JSON Output

Use `--json` on any list or info command to get structured output for programmatic consumption:

```bash
uv run gws-admin.py users list --json | python3 -m json.tool
```

### Example Agent Workflow

```
User: "Onboard new hire Jane Doe to the Engineering team"

Agent actions:
1. gws-admin.py users create jane.doe@company.com \
     --firstname Jane --lastname Doe --password 'Welcome123!'  --org /Engineering
2. gws-admin.py groups add-member engineering@company.com jane.doe@company.com
3. gws-admin.py aliases create jdoe@company.com --target jane.doe@company.com
4. gws-admin.py users info jane.doe@company.com --json
```

## Troubleshooting

### "GAM is not installed"

Run the setup wizard:
```bash
uv run gws-admin.py setup
```

Or install manually:
```bash
pip install advanced-gam-for-google-workspace
```

### "oauth2.txt not found" / Authentication Errors

Re-run OAuth authorization:
```bash
GAMCFGDIR=~/.openclaw/gam-config gam oauth create
```

### "Service account not authorized"

You need to configure domain-wide delegation in the Google Admin console:
1. Go to **Admin Console** → **Security** → **API Controls** → **Domain-wide Delegation**
2. Add the service account Client ID
3. Add the required OAuth scopes

To see the Client ID and required scopes:
```bash
GAMCFGDIR=~/.openclaw/gam-config gam check serviceaccount
```

### API Quota Errors

Google Workspace APIs have rate limits. If you hit quota errors:
- Wait a few minutes and retry
- For bulk operations, GAM handles rate limiting automatically
- Check quotas in the GCP Console under **APIs & Services** → **Dashboard**

### "Permission denied" Errors

Ensure the account used during setup has **super admin** privileges in Google Workspace.

## Security Notes

- **Credential files** (`oauth2.txt`, `oauth2service.json`, `client_secrets.json`) contain sensitive tokens. They are stored in `~/.claude/skills/gws-admin/gam-config/` with default file permissions.
- **Do not commit** the `gam-config/` directory to version control.
- **Service account keys** grant domain-wide access. Rotate them periodically via the GCP Console.
- **The `--confirm` flag** on destructive operations is a safety mechanism for agent use. It prevents accidental deletions when an agent misinterprets a request.
- **Audit logging**: All Google Workspace Admin actions are logged in the Admin Console under **Reports** → **Admin** audit log, regardless of whether they're performed via GAM or the web UI.
