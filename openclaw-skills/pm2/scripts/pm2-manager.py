# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""PM2 process manager wrapper for agents.

Usage:
    uv run pm2-manager.py <command> [options]

Requires PM2 installed globally (npm install -g pm2).
"""

import argparse
import json
import subprocess
import sys


def stderr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def out_json(data):
    print(json.dumps(data, indent=2, default=str))


def run_pm2(*args, capture=True):
    cmd = ["pm2"] + list(args)
    stderr(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=capture, text=True)
    if result.returncode != 0 and capture:
        stderr(result.stderr.strip() if result.stderr else f"pm2 exited with code {result.returncode}")
    return result


def run_pm2_json(*args):
    result = run_pm2(*args)
    if result.returncode != 0:
        sys.exit(result.returncode)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        stderr("Failed to parse PM2 JSON output")
        stderr(result.stdout[:500] if result.stdout else "(empty)")
        sys.exit(1)


# ── Commands ──────────────────────────────────────────────────────────

def cmd_list(args):
    data = run_pm2_json("jlist")
    if args.filter:
        status = args.filter.lower()
        data = [p for p in data if p.get("pm2_env", {}).get("status", "").lower() == status]
    if args.json:
        out_json(data)
    else:
        rows = []
        for p in data:
            env = p.get("pm2_env", {})
            monit = p.get("monit", {})
            rows.append({
                "id": p.get("pm_id"),
                "name": p.get("name"),
                "status": env.get("status"),
                "cpu": monit.get("cpu", 0),
                "memory_mb": round(monit.get("memory", 0) / 1024 / 1024, 1),
                "restarts": env.get("restart_time", 0),
                "uptime": env.get("pm_uptime"),
            })
        out_json(rows)


def find_process(name_or_id):
    data = run_pm2_json("jlist")
    for p in data:
        if str(p.get("pm_id")) == str(name_or_id) or p.get("name") == name_or_id:
            return p
    return None


def cmd_describe(args):
    p = find_process(args.name_or_id)
    if not p:
        stderr(f"Process '{args.name_or_id}' not found")
        sys.exit(1)
    env = p.get("pm2_env", {})
    monit = p.get("monit", {})
    out_json({
        "id": p.get("pm_id"),
        "name": p.get("name"),
        "status": env.get("status"),
        "pid": p.get("pid"),
        "cpu": monit.get("cpu", 0),
        "memory_mb": round(monit.get("memory", 0) / 1024 / 1024, 1),
        "restarts": env.get("restart_time", 0),
        "uptime": env.get("pm_uptime"),
        "script": env.get("pm_exec_path"),
        "cwd": env.get("pm_cwd"),
        "exec_mode": env.get("exec_mode"),
        "node_version": env.get("node_version"),
        "log_out": env.get("pm_out_log_path"),
        "log_err": env.get("pm_err_log_path"),
        "created_at": env.get("created_at"),
    })


def cmd_start(args):
    result = run_pm2("start", args.name_or_id)
    sys.exit(result.returncode)


def cmd_stop(args):
    result = run_pm2("stop", args.name_or_id)
    sys.exit(result.returncode)


def cmd_restart(args):
    result = run_pm2("restart", args.name_or_id)
    sys.exit(result.returncode)


def cmd_reload(args):
    result = run_pm2("reload", args.name_or_id)
    sys.exit(result.returncode)


def cmd_delete(args):
    result = run_pm2("delete", args.name_or_id)
    sys.exit(result.returncode)


def cmd_logs(args):
    pm2_args = ["logs", args.name_or_id, "--lines", str(args.lines)]
    if args.err:
        pm2_args.append("--err")
    if args.nostream:
        pm2_args.append("--nostream")
    result = run_pm2(*pm2_args, capture=False)
    sys.exit(result.returncode)


def cmd_flush(args):
    pm2_args = ["flush"]
    if args.name:
        pm2_args.append(args.name)
    result = run_pm2(*pm2_args)
    sys.exit(result.returncode)


def cmd_start_ecosystem(args):
    pm2_args = ["start", args.file]
    if args.only:
        pm2_args.extend(["--only", args.only])
    result = run_pm2(*pm2_args)
    sys.exit(result.returncode)


def cmd_save(args):
    result = run_pm2("save")
    sys.exit(result.returncode)


def cmd_resurrect(args):
    result = run_pm2("resurrect")
    sys.exit(result.returncode)


_SENSITIVE_PATTERNS = (
    "KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH",
    "DATABASE_URL", "REDIS_URL", "MONGO", "DSN", "CONNECTION_STRING",
    "COOKIE", "SESSION", "PRIVATE", "SIGNING", "ENCRYPTION", "PASSPHRASE",
    "API_KEY", "ACCESS_KEY", "APP_SECRET",
)

import re as _re

_CREDENTIAL_VALUE_RE = _re.compile(
    r"(://[^:]+:[^@]+@)"  # URI with embedded credentials
    r"|([A-Za-z0-9+/=_-]{40,})"  # High-entropy base64/hex strings (40+ chars)
)


def _redact_env(env: dict) -> dict:
    """Redact values of environment variables with sensitive-sounding names or credential-like values."""
    redacted = {}
    for k, v in env.items():
        upper_k = k.upper()
        if any(pat in upper_k for pat in _SENSITIVE_PATTERNS):
            redacted[k] = "****"
        elif isinstance(v, str) and _CREDENTIAL_VALUE_RE.search(v):
            redacted[k] = "****"
        else:
            redacted[k] = v
    return redacted


def cmd_env(args):
    p = find_process(args.name_or_id)
    if not p:
        stderr(f"Process '{args.name_or_id}' not found")
        sys.exit(1)
    env = p.get("pm2_env", {}).get("env", {})
    out_json(_redact_env(env))


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="PM2 process manager wrapper")
    sub = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = sub.add_parser("list", help="List all processes")
    p_list.add_argument("--json", action="store_true", help="Full JSON output")
    p_list.add_argument("--filter", type=str, help="Filter by status: online, stopped, errored")
    p_list.set_defaults(func=cmd_list)

    # describe
    p_desc = sub.add_parser("describe", help="Describe a process")
    p_desc.add_argument("name_or_id", help="Process name or PM2 id")
    p_desc.set_defaults(func=cmd_describe)

    # start
    p_start = sub.add_parser("start", help="Start a process")
    p_start.add_argument("name_or_id", help="Process name or PM2 id")
    p_start.set_defaults(func=cmd_start)

    # stop
    p_stop = sub.add_parser("stop", help="Stop a process")
    p_stop.add_argument("name_or_id", help="Process name or PM2 id")
    p_stop.set_defaults(func=cmd_stop)

    # restart
    p_restart = sub.add_parser("restart", help="Restart a process")
    p_restart.add_argument("name_or_id", help="Process name or PM2 id")
    p_restart.set_defaults(func=cmd_restart)

    # reload
    p_reload = sub.add_parser("reload", help="Reload a process (zero-downtime)")
    p_reload.add_argument("name_or_id", help="Process name or PM2 id")
    p_reload.set_defaults(func=cmd_reload)

    # delete
    p_del = sub.add_parser("delete", help="Delete a process from PM2")
    p_del.add_argument("name_or_id", help="Process name or PM2 id")
    p_del.set_defaults(func=cmd_delete)

    # logs
    p_logs = sub.add_parser("logs", help="Tail process logs")
    p_logs.add_argument("name_or_id", help="Process name or PM2 id")
    p_logs.add_argument("--lines", type=int, default=20, help="Number of lines (default: 20)")
    p_logs.add_argument("--err", action="store_true", help="Only stderr logs")
    p_logs.add_argument("--nostream", action="store_true", help="Print and exit (no follow)")
    p_logs.set_defaults(func=cmd_logs)

    # flush
    p_flush = sub.add_parser("flush", help="Clear log files")
    p_flush.add_argument("name", nargs="?", help="Process name (omit for all)")
    p_flush.set_defaults(func=cmd_flush)

    # start-ecosystem
    p_eco = sub.add_parser("start-ecosystem", help="Start from ecosystem file")
    p_eco.add_argument("file", help="Path to ecosystem config file")
    p_eco.add_argument("--only", help="Only start this process name")
    p_eco.set_defaults(func=cmd_start_ecosystem)

    # save
    p_save = sub.add_parser("save", help="Save current process list")
    p_save.set_defaults(func=cmd_save)

    # resurrect
    p_res = sub.add_parser("resurrect", help="Restore saved processes")
    p_res.set_defaults(func=cmd_resurrect)

    # env
    p_env = sub.add_parser("env", help="Show environment variables for a process")
    p_env.add_argument("name_or_id", help="Process name or PM2 id")
    p_env.set_defaults(func=cmd_env)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
