# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Redis CLI wrapper with connection profiles and JSON output.

Usage:
    uv run redis-cli.py <command> [options]

Requires redis-cli binary to be installed on the system.
"""

import argparse
import json
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def stderr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def out_json(data):
    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Data / profile management
# ---------------------------------------------------------------------------

def get_data_dir() -> Path:
    d = Path.home() / ".claude" / "skills" / "redis-cli" / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_profiles() -> dict:
    path = get_data_dir() / "connections.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            stderr("Warning: connections.json is corrupted, starting fresh.")
            return {}
    return {}


def save_profiles(profiles: dict):
    path = get_data_dir() / "connections.json"
    path.write_text(json.dumps(profiles, indent=2) + "\n")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def get_profile(alias: str) -> dict:
    profiles = load_profiles()
    if alias not in profiles:
        stderr(f"Profile '{alias}' not found. Use 'profile list' to see registered profiles.")
        sys.exit(1)
    return profiles[alias]


# ---------------------------------------------------------------------------
# Core subprocess wrapper
# ---------------------------------------------------------------------------

def run_redis(alias: str, redis_args: list[str], timeout: int = 30) -> str:
    """Run a redis-cli command and return raw stdout."""
    profile = get_profile(alias)

    cmd = ["redis-cli", "-h", profile["host"], "-p", str(profile["port"]),
           "-n", str(profile.get("db", 0))]
    if profile.get("password"):
        cmd.extend(["-a", profile["password"]])
    cmd.extend(redis_args)

    # Echo command with password redacted
    display = []
    skip_next = False
    for i, tok in enumerate(cmd):
        if skip_next:
            display.append("****")
            skip_next = False
        elif tok == "-a":
            display.append(tok)
            skip_next = True
        else:
            display.append(tok)
    stderr(f"$ {' '.join(display)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        stderr("Error: 'redis-cli' command not found. Ensure Redis CLI is installed.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        stderr(f"Error: Command timed out after {timeout} seconds.")
        sys.exit(1)

    if result.returncode != 0:
        stderr(f"Redis error (exit {result.returncode}):")
        if result.stderr:
            stderr(result.stderr.strip())
        if result.stdout:
            stderr(result.stdout.strip())
        sys.exit(result.returncode)

    # redis-cli prints auth warnings to stderr even on success
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Profile commands
# ---------------------------------------------------------------------------

def cmd_profile_add(args):
    profiles = load_profiles()
    if args.alias in profiles:
        stderr(f"Profile '{args.alias}' already exists. Remove it first.")
        sys.exit(1)
    profiles[args.alias] = {
        "name": args.name or args.alias,
        "host": args.host,
        "port": args.port,
        "db": args.db,
        **({"password": args.password} if args.password else {}),
        "added": datetime.now(timezone.utc).isoformat(),
    }
    save_profiles(profiles)
    stderr(f"Added profile '{args.alias}' ({args.host}:{args.port}/{args.db})")


def cmd_profile_remove(args):
    profiles = load_profiles()
    if args.alias not in profiles:
        stderr(f"Profile '{args.alias}' not found.")
        sys.exit(1)
    name = profiles[args.alias].get("name", args.alias)
    del profiles[args.alias]
    save_profiles(profiles)
    stderr(f"Removed profile '{args.alias}' ({name})")


def cmd_profile_list(args):
    profiles = load_profiles()
    result = []
    for alias, info in profiles.items():
        result.append({
            "alias": alias,
            "name": info.get("name", alias),
            "host": info["host"],
            "port": info["port"],
            "db": info.get("db", 0),
            "password": "****" if info.get("password") else None,
            "added": info.get("added"),
        })
    out_json(result)


# ---------------------------------------------------------------------------
# Server commands
# ---------------------------------------------------------------------------

def cmd_server(args):
    action = args.server_action

    if action == "ping":
        output = run_redis(args.alias, ["PING"])
        out_json({"status": "ok" if output == "PONG" else output})

    elif action == "info":
        section_args = ["INFO"]
        if args.section:
            section_args.append(args.section)
        output = run_redis(args.alias, section_args)
        # Parse INFO output into dict
        info = {}
        current_section = "default"
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("# "):
                current_section = line[2:].lower()
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                info[f"{current_section}.{key}"] = val
        out_json(info)

    elif action == "dbsize":
        output = run_redis(args.alias, ["DBSIZE"])
        # Output is like "(integer) 42"
        count = output.split()[-1] if output else "0"
        out_json({"keys": int(count)})


# ---------------------------------------------------------------------------
# Keys commands
# ---------------------------------------------------------------------------

def cmd_keys(args):
    action = args.keys_action

    if action == "list":
        pattern = args.pattern or "*"
        output = run_redis(args.alias, ["KEYS", pattern])
        keys = output.splitlines() if output else []
        out_json(keys)

    elif action == "type":
        output = run_redis(args.alias, ["TYPE", args.key])
        out_json({"key": args.key, "type": output})

    elif action == "ttl":
        output = run_redis(args.alias, ["TTL", args.key])
        out_json({"key": args.key, "ttl": int(output)})

    elif action == "del":
        if not args.confirm:
            stderr("Error: --confirm flag required for destructive operations.")
            sys.exit(1)
        output = run_redis(args.alias, ["DEL", args.key])
        out_json({"key": args.key, "deleted": int(output)})
        stderr(f"Deleted key '{args.key}'")

    elif action == "exists":
        output = run_redis(args.alias, ["EXISTS", args.key])
        out_json({"key": args.key, "exists": int(output) > 0})

    elif action == "expire":
        output = run_redis(args.alias, ["EXPIRE", args.key, str(args.seconds)])
        out_json({"key": args.key, "seconds": args.seconds, "set": int(output) == 1})
        stderr(f"Set TTL {args.seconds}s on '{args.key}'")

    elif action == "rename":
        output = run_redis(args.alias, ["RENAME", args.key, args.newkey])
        out_json({"old": args.key, "new": args.newkey, "ok": output == "OK"})
        stderr(f"Renamed '{args.key}' -> '{args.newkey}'")


# ---------------------------------------------------------------------------
# String commands
# ---------------------------------------------------------------------------

def cmd_string(args):
    action = args.string_action

    if action == "get":
        output = run_redis(args.alias, ["GET", args.key])
        if output == "(nil)":
            out_json({"key": args.key, "value": None})
        else:
            out_json({"key": args.key, "value": output})

    elif action == "set":
        redis_args = ["SET", args.key, args.value]
        if args.ex:
            redis_args.extend(["EX", str(args.ex)])
        if args.nx:
            redis_args.append("NX")
        output = run_redis(args.alias, redis_args)
        out_json({"key": args.key, "ok": output == "OK"})
        stderr(f"Set key '{args.key}'")

    elif action == "del":
        if not args.confirm:
            stderr("Error: --confirm flag required for destructive operations.")
            sys.exit(1)
        output = run_redis(args.alias, ["DEL", args.key])
        out_json({"key": args.key, "deleted": int(output)})
        stderr(f"Deleted key '{args.key}'")


# ---------------------------------------------------------------------------
# List commands
# ---------------------------------------------------------------------------

def cmd_list(args):
    action = args.list_action

    if action == "range":
        output = run_redis(args.alias, [
            "LRANGE", args.key, str(args.start), str(args.stop),
        ])
        items = output.splitlines() if output else []
        out_json({"key": args.key, "items": items})

    elif action == "push":
        cmd_name = "RPUSH" if args.right else "LPUSH"
        output = run_redis(args.alias, [cmd_name, args.key, args.value])
        out_json({"key": args.key, "length": int(output)})
        stderr(f"Pushed to '{args.key}' ({cmd_name})")

    elif action == "pop":
        cmd_name = "RPOP" if args.right else "LPOP"
        output = run_redis(args.alias, [cmd_name, args.key])
        if output == "(nil)":
            out_json({"key": args.key, "value": None})
        else:
            out_json({"key": args.key, "value": output})

    elif action == "len":
        output = run_redis(args.alias, ["LLEN", args.key])
        out_json({"key": args.key, "length": int(output)})

    elif action == "trim":
        if not args.confirm:
            stderr("Error: --confirm flag required for destructive operations.")
            sys.exit(1)
        output = run_redis(args.alias, [
            "LTRIM", args.key, str(args.start), str(args.stop),
        ])
        out_json({"key": args.key, "ok": output == "OK"})
        stderr(f"Trimmed list '{args.key}' to [{args.start}:{args.stop}]")


# ---------------------------------------------------------------------------
# Hash commands
# ---------------------------------------------------------------------------

def cmd_hash(args):
    action = args.hash_action

    if action == "get":
        output = run_redis(args.alias, ["HGET", args.key, args.field])
        if output == "(nil)":
            out_json({"key": args.key, "field": args.field, "value": None})
        else:
            out_json({"key": args.key, "field": args.field, "value": output})

    elif action == "getall":
        output = run_redis(args.alias, ["HGETALL", args.key])
        lines = output.splitlines() if output else []
        pairs = {}
        for i in range(0, len(lines) - 1, 2):
            pairs[lines[i]] = lines[i + 1]
        out_json({"key": args.key, "fields": pairs})

    elif action == "set":
        output = run_redis(args.alias, ["HSET", args.key, args.field, args.value])
        out_json({"key": args.key, "field": args.field, "new_fields": int(output)})
        stderr(f"Set field '{args.field}' on '{args.key}'")

    elif action == "del":
        if not args.confirm:
            stderr("Error: --confirm flag required for destructive operations.")
            sys.exit(1)
        output = run_redis(args.alias, ["HDEL", args.key, args.field])
        out_json({"key": args.key, "field": args.field, "deleted": int(output)})
        stderr(f"Deleted field '{args.field}' from '{args.key}'")

    elif action == "keys":
        output = run_redis(args.alias, ["HKEYS", args.key])
        fields = output.splitlines() if output else []
        out_json({"key": args.key, "fields": fields})


# ---------------------------------------------------------------------------
# Flush command
# ---------------------------------------------------------------------------

def cmd_flush(args):
    if not args.confirm:
        stderr("Error: --confirm flag required. This will delete ALL keys in the current database.")
        sys.exit(1)
    profile = get_profile(args.alias)
    db = profile.get("db", 0)
    output = run_redis(args.alias, ["FLUSHDB"])
    out_json({"flushed": True, "db": db, "ok": output == "OK"})
    stderr(f"Flushed database {db}")


# ---------------------------------------------------------------------------
# Raw run command
# ---------------------------------------------------------------------------

def cmd_run(args):
    raw_args = args.extra_args
    if raw_args and raw_args[0] == "--":
        raw_args = raw_args[1:]
    if not raw_args:
        stderr("Error: No Redis command provided. Usage: run <alias> -- <command> [args...]")
        sys.exit(1)
    output = run_redis(args.alias, raw_args)
    # Try JSON parse, fall back to raw
    try:
        out_json(json.loads(output))
    except (json.JSONDecodeError, ValueError):
        if output:
            print(output)
        else:
            out_json({"ok": True})


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Redis CLI wrapper with profiles and JSON output")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- profile ---
    profile_parser = sub.add_parser("profile", help="Manage connection profiles")
    profile_sub = profile_parser.add_subparsers(dest="profile_action", required=True)

    p = profile_sub.add_parser("add", help="Register a connection profile")
    p.add_argument("alias", help="Short alias (e.g. 'local', 'prod')")
    p.add_argument("--host", default="127.0.0.1", help="Redis host (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=6379, help="Redis port (default: 6379)")
    p.add_argument("--db", type=int, default=0, help="Database number (default: 0)")
    p.add_argument("--password", help="Redis password (optional)")
    p.add_argument("--name", help="Human-readable label")

    p = profile_sub.add_parser("remove", help="Remove a registered profile")
    p.add_argument("alias", help="Profile alias")

    profile_sub.add_parser("list", help="List registered profiles")

    # --- server ---
    server_parser = sub.add_parser("server", help="Server health and stats")
    server_parser.add_argument("alias", help="Profile alias")
    server_sub = server_parser.add_subparsers(dest="server_action", required=True)

    server_sub.add_parser("ping", help="Ping the Redis server")

    p = server_sub.add_parser("info", help="Get server info")
    p.add_argument("--section", help="Info section (e.g. memory, clients, stats)")

    server_sub.add_parser("dbsize", help="Get number of keys in current DB")

    # --- keys ---
    keys_parser = sub.add_parser("keys", help="Key inspection and management")
    keys_parser.add_argument("alias", help="Profile alias")
    keys_sub = keys_parser.add_subparsers(dest="keys_action", required=True)

    p = keys_sub.add_parser("list", help="List keys matching a pattern")
    p.add_argument("--pattern", default="*", help="Glob pattern (default: *)")

    p = keys_sub.add_parser("type", help="Get the type of a key")
    p.add_argument("key", help="Key name")

    p = keys_sub.add_parser("ttl", help="Get TTL of a key in seconds")
    p.add_argument("key", help="Key name")

    p = keys_sub.add_parser("del", help="Delete a key")
    p.add_argument("key", help="Key name")
    p.add_argument("--confirm", action="store_true", help="Required for destructive ops")

    p = keys_sub.add_parser("exists", help="Check if a key exists")
    p.add_argument("key", help="Key name")

    p = keys_sub.add_parser("expire", help="Set TTL on a key")
    p.add_argument("key", help="Key name")
    p.add_argument("seconds", type=int, help="TTL in seconds")
    p.add_argument("--confirm", action="store_true")

    p = keys_sub.add_parser("rename", help="Rename a key")
    p.add_argument("key", help="Current key name")
    p.add_argument("newkey", help="New key name")

    # --- string ---
    string_parser = sub.add_parser("string", help="String value operations")
    string_parser.add_argument("alias", help="Profile alias")
    string_sub = string_parser.add_subparsers(dest="string_action", required=True)

    p = string_sub.add_parser("get", help="Get a string value")
    p.add_argument("key", help="Key name")

    p = string_sub.add_parser("set", help="Set a string value")
    p.add_argument("key", help="Key name")
    p.add_argument("value", help="Value to set")
    p.add_argument("--ex", type=int, help="Expire after N seconds")
    p.add_argument("--nx", action="store_true", help="Only set if key does not exist")

    p = string_sub.add_parser("del", help="Delete a string key")
    p.add_argument("key", help="Key name")
    p.add_argument("--confirm", action="store_true", help="Required for destructive ops")

    # --- list ---
    list_parser = sub.add_parser("list", help="List value operations")
    list_parser.add_argument("alias", help="Profile alias")
    list_sub = list_parser.add_subparsers(dest="list_action", required=True)

    p = list_sub.add_parser("range", help="Get a range of list elements")
    p.add_argument("key", help="Key name")
    p.add_argument("--start", type=int, default=0, help="Start index (default: 0)")
    p.add_argument("--stop", type=int, default=-1, help="Stop index (default: -1)")

    p = list_sub.add_parser("push", help="Push a value to a list")
    p.add_argument("key", help="Key name")
    p.add_argument("value", help="Value to push")
    p.add_argument("--right", action="store_true", help="Push to right/tail (RPUSH, default is LPUSH)")

    p = list_sub.add_parser("pop", help="Pop a value from a list")
    p.add_argument("key", help="Key name")
    p.add_argument("--right", action="store_true", help="Pop from right/tail (RPOP, default is LPOP)")

    p = list_sub.add_parser("len", help="Get list length")
    p.add_argument("key", help="Key name")

    p = list_sub.add_parser("trim", help="Trim a list to a range")
    p.add_argument("key", help="Key name")
    p.add_argument("--start", type=int, required=True, help="Start index")
    p.add_argument("--stop", type=int, required=True, help="Stop index")
    p.add_argument("--confirm", action="store_true", help="Required for destructive ops")

    # --- hash ---
    hash_parser = sub.add_parser("hash", help="Hash value operations")
    hash_parser.add_argument("alias", help="Profile alias")
    hash_sub = hash_parser.add_subparsers(dest="hash_action", required=True)

    p = hash_sub.add_parser("get", help="Get a hash field value")
    p.add_argument("key", help="Key name")
    p.add_argument("field", help="Field name")

    p = hash_sub.add_parser("getall", help="Get all fields and values")
    p.add_argument("key", help="Key name")

    p = hash_sub.add_parser("set", help="Set a hash field value")
    p.add_argument("key", help="Key name")
    p.add_argument("field", help="Field name")
    p.add_argument("value", help="Value to set")

    p = hash_sub.add_parser("del", help="Delete a hash field")
    p.add_argument("key", help="Key name")
    p.add_argument("field", help="Field name")
    p.add_argument("--confirm", action="store_true", help="Required for destructive ops")

    p = hash_sub.add_parser("keys", help="List all fields in a hash")
    p.add_argument("key", help="Key name")

    # --- flush ---
    flush_parser = sub.add_parser("flush", help="Flush current database (destructive)")
    flush_parser.add_argument("alias", help="Profile alias")
    flush_parser.add_argument("--confirm", action="store_true",
                              help="Required — confirms you want to delete all keys")

    # --- run ---
    run_parser = sub.add_parser("run", help="Run any raw redis-cli command")
    run_parser.add_argument("alias", help="Profile alias")
    run_parser.add_argument("extra_args", nargs=argparse.REMAINDER,
                            help="Redis command and arguments (after --)")

    return parser


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()
    cmd = args.command

    if cmd == "profile":
        if args.profile_action == "add":
            cmd_profile_add(args)
        elif args.profile_action == "remove":
            cmd_profile_remove(args)
        elif args.profile_action == "list":
            cmd_profile_list(args)
    elif cmd == "server":
        cmd_server(args)
    elif cmd == "keys":
        cmd_keys(args)
    elif cmd == "string":
        cmd_string(args)
    elif cmd == "list":
        cmd_list(args)
    elif cmd == "hash":
        cmd_hash(args)
    elif cmd == "flush":
        cmd_flush(args)
    elif cmd == "run":
        cmd_run(args)


if __name__ == "__main__":
    main()
