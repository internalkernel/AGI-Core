---
name: redis-cli
description: Redis CLI wrapper with connection profiles, key/string/list/hash operations, server health checks, and raw command passthrough. All output is JSON to stdout; status/errors to stderr.
---

# Redis CLI

Manage Redis instances through connection profiles. Supports key inspection, string/list/hash operations, server health checks, database flushing, and raw command passthrough. All structured data is JSON to stdout; status messages and errors go to stderr.

## Usage

```bash
REDIS="uv run ~/.claude/skills/redis-cli/scripts/redis-cli.py"
```

## Commands

### Profile Management

```bash
$REDIS profile add local --host 127.0.0.1              # register with defaults (port 6379, db 0)
$REDIS profile add prod --host 10.0.1.5 --port 6380 --password s3cret --db 2
$REDIS profile remove prod                              # remove a profile
$REDIS profile list                                     # list all profiles (passwords redacted)
```

### Server Health

```bash
$REDIS server local ping                                # PONG check
$REDIS server local info                                # full server info as JSON
$REDIS server local info --section memory               # specific info section
$REDIS server local dbsize                              # number of keys in current DB
```

### Key Inspection

```bash
$REDIS keys local list                                  # all keys (use with caution in production)
$REDIS keys local list --pattern "login_lock:*"         # keys matching glob pattern
$REDIS keys local type mykey                            # get key type
$REDIS keys local ttl mykey                             # get TTL in seconds
$REDIS keys local exists mykey                          # check if key exists
$REDIS keys local expire mykey 3600                     # set TTL to 1 hour
$REDIS keys local rename oldkey newkey                  # rename a key
$REDIS keys local del mykey --confirm                   # delete a key (requires --confirm)
```

### String Operations

```bash
$REDIS string local get session:abc123                  # get a string value
$REDIS string local set counter 42                      # set a string value
$REDIS string local set token xyz --ex 900              # set with 15-min expiry
$REDIS string local set lock:user1 1 --nx               # set only if not exists
$REDIS string local del session:abc123 --confirm        # delete (requires --confirm)
```

### List Operations

```bash
$REDIS list local range activity:recent --start 0 --stop 4    # get first 5 items
$REDIS list local push queue:jobs "task-payload"               # LPUSH (left/head)
$REDIS list local push queue:jobs "task-payload" --right       # RPUSH (right/tail)
$REDIS list local pop queue:jobs                               # LPOP
$REDIS list local pop queue:jobs --right                       # RPOP
$REDIS list local len queue:jobs                               # list length
$REDIS list local trim queue:jobs --start 0 --stop 99 --confirm   # keep first 100 items
```

### Hash Operations

```bash
$REDIS hash local get user:1001 email                   # get a single field
$REDIS hash local getall user:1001                      # get all fields and values
$REDIS hash local set user:1001 status active           # set a field
$REDIS hash local del user:1001 temp_flag --confirm     # delete a field (requires --confirm)
$REDIS hash local keys user:1001                        # list all field names
```

### Flush Database

```bash
$REDIS flush local --confirm                            # delete ALL keys in current DB
```

### Raw Command Passthrough

```bash
$REDIS run local -- GET "login_lock:test"               # run any redis-cli command
$REDIS run local -- CLIENT LIST                         # list connected clients
$REDIS run local -- CONFIG GET maxmemory                # query config values
```

## Data Storage

Connection profiles are stored in `~/.claude/skills/redis-cli/data/connections.json` (chmod 600).

State files:
- `connections.json` — named connection profiles with host, port, db, optional password

## Prerequisites

- **redis-cli** binary must be installed and available in `$PATH`

## Tips

- Use `keys list --pattern` instead of bare `keys list` in production to avoid scanning all keys
- The `run` passthrough command accepts any valid redis-cli arguments after `--`
- Passwords are stored in the profile but **always redacted** in stderr command echo and `profile list` output
- Destructive operations (`keys del`, `string del`, `hash del`, `list trim`, `flush`) require `--confirm`
- The default timeout is 30 seconds per command; use `run` for long-running operations
- Use `server info --section memory` to quickly check memory usage without full info dump
