---
name: pm2
description: PM2 process manager wrapper for agents. List, start, stop, restart, describe, and tail logs for PM2-managed processes. All output is JSON to stdout; status/errors to stderr.
---

# PM2 Manager

Manage PM2 processes. Provides commands to list, inspect, control, and tail logs for any PM2-managed process. Designed for the OpenClaw multi-agent environment but works with any PM2 setup.

## Usage

```bash
PM2="uv run ~/.openclaw/skills/pm2/scripts/pm2-manager.py"
```

## Commands

### List all processes

```bash
$PM2 list                            # All processes (table summary)
$PM2 list --json                     # Full JSON output
$PM2 list --filter running           # Filter by status: online, stopped, errored
```

### Describe a process

```bash
$PM2 describe openclaw-dashboard     # Detailed info by name
$PM2 describe 8                      # Detailed info by PM2 id
```

### Start / Stop / Restart

```bash
$PM2 start openclaw-dashboard
$PM2 stop openclaw-dashboard
$PM2 restart openclaw-dashboard
$PM2 restart all                     # Restart everything
```

### Reload (zero-downtime for cluster mode)

```bash
$PM2 reload openclaw-dashboard
```

### Delete a process from PM2

```bash
$PM2 delete openclaw-dashboard
```

### Tail logs

```bash
$PM2 logs openclaw-dashboard              # Last 20 lines + follow
$PM2 logs openclaw-dashboard --lines 50   # Last 50 lines
$PM2 logs openclaw-dashboard --err        # Only stderr
$PM2 logs openclaw-dashboard --nostream   # Print and exit (no follow)
```

### Flush logs

```bash
$PM2 flush                           # Clear all log files
$PM2 flush openclaw-dashboard        # Clear logs for one process
```

### Start from ecosystem file

```bash
$PM2 start-ecosystem /root/.openclaw/ecosystem.config.js
$PM2 start-ecosystem /root/.openclaw/ecosystem.config.js --only devops
```

### Save / Resurrect

```bash
$PM2 save                            # Save current process list
$PM2 resurrect                       # Restore saved processes
```

### Environment info

```bash
$PM2 env openclaw-dashboard          # Show environment variables for a process
```

## Output Format

All commands emit JSON to stdout. Status messages and errors go to stderr. Exit codes mirror PM2 exit codes.

## Prerequisites

- **PM2** installed globally (`npm install -g pm2`)
- Processes managed via PM2

## Tips

- Use `list --filter` to quickly check which agents are online
- `describe` gives memory/CPU stats, restart count, uptime, and log file paths
- `logs --nostream` is useful for grabbing recent output without blocking
- `start-ecosystem --only` lets you restart a single agent from the ecosystem config
