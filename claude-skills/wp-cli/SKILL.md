---
name: wp-cli
description: WP-CLI remote wrapper for agents. Run any WP-CLI command on remote WordPress sites via SSH with convenience wrappers for plugins, cache, maintenance, and backups.
---

# WP-CLI

Run WP-CLI commands on remote WordPress sites via SSH. Provides a passthrough for any WP-CLI command plus convenience wrappers for common operations (status, plugins, cache, maintenance, backups) and plugin-specific commands (Elementor, WP Rocket, Imagify, SEOPress, Gravity Forms, Redirection). Most output is JSON to stdout; `run` passthrough and `backup-db` (stdout mode) may emit plain text. Status/errors to stderr.

## Usage

```bash
WPCLI="uv run ~/.claude/skills/wp-cli/scripts/wp-cli.py"
```

## Commands

### Register a site

```bash
$WPCLI site add prod --ssh deploy@web1.example.com --path /var/www/html [--name "Production"] [--wp-user admin]
```

### Remove / list sites

```bash
$WPCLI site remove prod
$WPCLI site list
```

### Run any WP-CLI command (passthrough)

```bash
$WPCLI run prod -- core version
$WPCLI run prod -- user list
$WPCLI run prod -- option get siteurl
$WPCLI run prod -- search-replace "old.com" "new.com" --dry-run
```

Prepends `wp --ssh=user@host:/path`, appends `--format=json` if not specified.

### Status overview

```bash
$WPCLI status prod
```

Returns core version, plugins needing updates, and maintenance mode status.

### Plugins

```bash
$WPCLI plugins prod                       # List all with update info
$WPCLI update-plugins prod                # Update all plugins
$WPCLI update-plugins prod --plugin acf   # Update specific plugin
```

### Cache management

```bash
$WPCLI flush-cache prod     # wp cache flush + rocket clean + rocket preload
```

### Maintenance mode

```bash
$WPCLI maintenance prod on
$WPCLI maintenance prod off
$WPCLI maintenance prod status
```

### Database backup

```bash
$WPCLI backup-db prod --output /tmp/backup.sql   # Path is on the REMOTE server
$WPCLI backup-db prod                             # Dumps to stdout (plain SQL, not JSON)
```

### Elementor

```bash
$WPCLI elementor prod flush-css
$WPCLI elementor prod replace-urls https://old.com https://new.com
```

### WP Rocket

```bash
$WPCLI rocket prod clean
$WPCLI rocket prod preload
```

### Imagify

```bash
$WPCLI imagify prod optimize [--lossless]
```

### SEOPress

```bash
$WPCLI seopress prod export settings.json
$WPCLI seopress prod import settings.json
```

### Gravity Forms

```bash
$WPCLI gf prod forms
$WPCLI gf prod entries 1 [--limit 50]
```

### Redirection

```bash
$WPCLI redirection prod export redirects.json
$WPCLI redirection prod import redirects.json
```

## Data Storage

Site data is stored at `~/.claude/skills/wp-cli/data/sites.json`.

State files:

- `sites.json` — registered sites with alias, SSH string, WP path, optional WP user

## Prerequisites

- **Local:** WP-CLI installed (`wp` command available)
- **Remote:** SSH key access to the server, WordPress installed at the specified path
- WP-CLI's `--ssh` flag uses SSH under the hood, so your SSH config/keys must be set up

## Tips

- The `run` passthrough accepts any WP-CLI command after `--`
- JSON format is auto-appended unless you specify `--format=` yourself
- `flush-cache` gracefully skips WP Rocket commands if the plugin isn't installed
- `status` gives a quick health overview: version, pending updates, maintenance state
- All commands propagate WP-CLI's exit codes for scripting
- Use `--wp-user` at site registration to run commands as a specific WordPress user
