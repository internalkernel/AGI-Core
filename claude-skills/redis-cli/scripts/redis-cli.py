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
import fcntl
import json
import os
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

MAX_OUTPUT_BYTES = 10 * 1024 * 1024  # 10 MB guard on subprocess output
MAX_PROFILE_BYTES = 1 * 1024 * 1024  # 1 MB guard on connections.json
MAX_KEYS_HARD_CAP = 100_000  # absolute cap on keys list to bound memory
VERBOSE = False  # set via --verbose flag; controls command echo to stderr
_REDIS_CLI: str | None = None  # resolved absolute path to redis-cli binary
_TRUSTED_PATH_DIRS = ("/usr/bin", "/usr/local/bin", "/bin", "/usr/sbin", "/sbin", "/snap/bin")
# Minimal env vars to pass to redis-cli subprocesses (avoid leaking unrelated secrets)
_ENV_ALLOWLIST = ("HOME", "PATH", "LANG", "LC_ALL", "LC_CTYPE", "TERM", "USER", "LOGNAME")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def stderr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def out_json(data, compact=False):
    if compact:
        print(json.dumps(data, default=str))
    else:
        print(json.dumps(data, indent=2, default=str))


def _minimal_env() -> dict:
    """Build a minimal subprocess environment from allowlisted vars."""
    return {k: os.environ[k] for k in _ENV_ALLOWLIST if k in os.environ}


# ---------------------------------------------------------------------------
# Data / profile management
# ---------------------------------------------------------------------------

def get_data_dir() -> Path:
    d = Path.home() / ".claude" / "skills" / "redis-cli" / "data"
    d.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Ensure permissions even if dir pre-existed with wider umask
    os.chmod(str(d), 0o700)
    return d


def _lock_path() -> Path:
    return get_data_dir() / ".lock"


def load_profiles() -> dict:
    path = get_data_dir() / "connections.json"
    if not path.exists():
        return {}
    # Open with O_NOFOLLOW to reject symlinks atomically; all checks use the fd
    try:
        fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as e:
        stderr(f"Error: Cannot open connections.json: {e}")
        sys.exit(1)
    try:
        os.fchmod(fd, 0o600)
        size = os.fstat(fd).st_size
        if size > MAX_PROFILE_BYTES:
            stderr(f"Error: connections.json exceeds {MAX_PROFILE_BYTES // 1024} KB limit ({size} bytes). "
                   "File may be corrupted.")
            sys.exit(1)
        chunks = []
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        os.close(fd)
    try:
        return json.loads(b"".join(chunks).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        stderr("Warning: connections.json is corrupted, starting fresh.")
        return {}


def _write_profiles(profiles: dict):
    """Write profiles atomically (caller must hold lock)."""
    data_dir = get_data_dir()
    path = data_dir / "connections.json"
    data = (json.dumps(profiles, indent=2) + "\n").encode()
    if len(data) > MAX_PROFILE_BYTES:
        stderr(f"Error: Profile data exceeds {MAX_PROFILE_BYTES // 1024} KB limit. "
               "Remove unused profiles to free space.")
        sys.exit(1)
    fd, tmp = tempfile.mkstemp(dir=data_dir, suffix=".tmp")
    closed = False
    try:
        os.fchmod(fd, 0o600)
        written = 0
        while written < len(data):
            written += os.write(fd, data[written:])
        os.fsync(fd)
        os.close(fd)
        closed = True
        os.replace(tmp, path)
    except BaseException:
        if not closed:
            os.close(fd)
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def update_profiles(fn):
    """Locked read-modify-write: fn(profiles) -> profiles must return updated dict."""
    lock = _lock_path()
    # Atomic create+open with O_NOFOLLOW (no TOCTOU from separate touch)
    try:
        fd = os.open(str(lock), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    except OSError as e:
        stderr(f"Error: Cannot open lock file: {e}")
        sys.exit(1)
    lf = os.fdopen(fd, "r")
    try:
        os.fchmod(fd, 0o600)
        fcntl.flock(lf, fcntl.LOCK_EX)
        profiles = load_profiles()
        profiles = fn(profiles)
        _write_profiles(profiles)
    finally:
        lf.close()


def get_profile(alias: str) -> dict:
    profiles = load_profiles()
    if alias not in profiles:
        stderr(f"Profile '{alias}' not found. Use 'profile list' to see registered profiles.")
        sys.exit(1)
    return profiles[alias]


# ---------------------------------------------------------------------------
# Core subprocess wrapper
# ---------------------------------------------------------------------------

def _get_redis_cli() -> str:
    """Resolve redis-cli to an absolute path from trusted directories (cached)."""
    global _REDIS_CLI
    if _REDIS_CLI is None:
        # Search only trusted dirs — fail closed to prevent PATH hijacking
        trusted_path = os.pathsep.join(_TRUSTED_PATH_DIRS)
        path = shutil.which("redis-cli", path=trusted_path)
        if path is None:
            stderr("Error: 'redis-cli' not found in trusted directories "
                   f"({', '.join(_TRUSTED_PATH_DIRS)}). "
                   "Ensure Redis CLI is installed in a standard location.")
            sys.exit(1)
        _REDIS_CLI = path
    return _REDIS_CLI


def _resolve_profile_password(profile: dict) -> str | None:
    """Resolve password from profile at runtime (supports env/file/direct)."""
    if profile.get("password_env"):
        val = os.environ.get(profile["password_env"])
        if val is None:
            stderr(f"Error: Env var '{profile['password_env']}' is not set.")
            sys.exit(1)
        return val
    if profile.get("password_file"):
        p = Path(profile["password_file"]).expanduser()
        # Open with O_NOFOLLOW to reject symlinks atomically; validate via fstat
        try:
            fd = os.open(str(p), os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            stderr(f"Error: Password file '{p}' not found.")
            sys.exit(1)
        except OSError as e:
            stderr(f"Error: Cannot open password file '{p}': {e}")
            sys.exit(1)
        try:
            st = os.fstat(fd)
            if st.st_uid != os.getuid():
                stderr(f"Error: Password file '{p}' is not owned by current user.")
                sys.exit(1)
            if st.st_mode & 0o077:
                stderr(f"Error: Password file '{p}' is accessible by group/others "
                       f"(mode {oct(st.st_mode & 0o777)}). Run: chmod 600 {p}")
                sys.exit(1)
            data = os.read(fd, 4096)
        finally:
            os.close(fd)
        return data.decode("utf-8", errors="replace").rstrip("\r\n")
    if profile.get("password"):
        stderr("Warning: Profile uses plaintext password. "
               "Migrate to --password-env or --password-file for security.")
        return profile["password"]
    return None


def run_redis(alias: str, redis_args: list[str], timeout: int = 30) -> str:
    """Run a redis-cli command and return raw stdout."""
    profile = get_profile(alias)
    redis_bin = _get_redis_cli()

    cmd = [redis_bin, "-h", profile["host"], "-p", str(profile["port"]),
           "-n", str(profile.get("db", 0))]
    cmd.extend(redis_args)

    # Always control REDISCLI_AUTH: set from profile or clear ambient value
    env = _minimal_env()
    password = _resolve_profile_password(profile)
    if password:
        env["REDISCLI_AUTH"] = password
    else:
        env.pop("REDISCLI_AUTH", None)

    if VERBOSE:
        # Deny-by-default redaction: show connection params + command verb + first key only
        # Read-only commands where args are safe to show (keys/patterns, no values)
        _SAFE_CMDS = {"GET", "MGET", "EXISTS", "TYPE", "TTL", "PTTL", "KEYS", "SCAN",
                      "HGET", "HGETALL", "HKEYS", "HLEN", "HEXISTS",
                      "LRANGE", "LLEN", "LINDEX",
                      "SCARD", "SMEMBERS", "SISMEMBER",
                      "ZCARD", "ZRANGE", "ZRANGEBYSCORE", "ZSCORE",
                      "DBSIZE", "INFO", "PING", "ECHO", "TIME",
                      "DEL", "UNLINK", "EXPIRE", "PEXPIRE", "PERSIST", "RENAME",
                      "LPOP", "RPOP", "LLEN", "DUMP"}
        conn_len = len(cmd) - len(redis_args)
        display = list(cmd[:conn_len])
        if redis_args:
            top_cmd = redis_args[0].upper()
            if top_cmd in _SAFE_CMDS:
                display.extend(redis_args)
            else:
                # Show command verb only, redact all args
                display.append(redis_args[0])
                if len(redis_args) > 1:
                    display += ["****"] * (len(redis_args) - 1)
        stderr(f"$ {' '.join(display)}")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env=env)

    # Stream-read stdout+stderr with combined byte cap and wall-clock deadline
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    total_bytes = 0
    deadline = time.monotonic() + timeout
    sel = selectors.DefaultSelector()
    sel.register(proc.stdout, selectors.EVENT_READ, stdout_chunks)
    sel.register(proc.stderr, selectors.EVENT_READ, stderr_chunks)
    try:
        open_streams = 2
        while open_streams > 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                proc.kill()
                proc.wait()
                stderr(f"Error: Command timed out after {timeout} seconds.")
                sys.exit(1)
            events = sel.select(timeout=remaining)
            if not events:
                # select returned empty (timeout expired)
                proc.kill()
                proc.wait()
                stderr(f"Error: Command timed out after {timeout} seconds.")
                sys.exit(1)
            for key, _ in events:
                chunk = key.fileobj.read(65536)
                if not chunk:
                    sel.unregister(key.fileobj)
                    open_streams -= 1
                    continue
                total_bytes += len(chunk)
                if total_bytes > MAX_OUTPUT_BYTES:
                    proc.kill()
                    proc.wait()
                    stderr(f"Error: Output exceeds {MAX_OUTPUT_BYTES // (1024 * 1024)} MB limit.")
                    sys.exit(1)
                key.data.append(chunk)
    except (OSError, ValueError) as e:
        proc.kill()
        proc.wait(timeout=5)
        stderr(f"Error: I/O failure reading subprocess output: {e}")
        sys.exit(1)
    finally:
        sel.close()

    try:
        proc.wait(timeout=max(0, deadline - time.monotonic()) + 1)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        stderr(f"Error: Command timed out after {timeout} seconds.")
        sys.exit(1)

    stdout_text = b"".join(stdout_chunks).decode("utf-8", errors="replace")
    stderr_text = b"".join(stderr_chunks).decode("utf-8", errors="replace")

    if proc.returncode != 0:
        stderr(f"Redis error (exit {proc.returncode}):")
        if stderr_text.strip():
            stderr(stderr_text.strip())
        if stdout_text.strip():
            stderr(stdout_text.strip())
        sys.exit(proc.returncode)

    # redis-cli prints auth warnings to stderr even on success
    return stdout_text.strip()


# ---------------------------------------------------------------------------
# Profile commands
# ---------------------------------------------------------------------------

def _password_fields(args) -> dict:
    """Return profile fields for password storage (reference, not resolved value).

    Stores env var name or file path when possible so the actual secret
    never touches disk.  Falls back to storing the raw password only when
    --password is used directly.
    """
    if getattr(args, "password_env", None):
        # Validate the env var exists now, but store only the name
        if os.environ.get(args.password_env) is None:
            stderr(f"Error: Env var '{args.password_env}' is not set.")
            sys.exit(1)
        return {"password_env": args.password_env}
    if getattr(args, "password_file", None):
        p = Path(args.password_file).expanduser().resolve()
        if not p.is_file():
            stderr(f"Error: Password file '{p}' not found.")
            sys.exit(1)
        mode = p.stat().st_mode
        if mode & 0o077:
            stderr(f"Warning: Password file '{p}' is accessible by group/others (mode {oct(mode)}). "
                   "Consider: chmod 600")
        return {"password_file": str(p)}
    return {}


_MAX_FIELD_LEN = 256  # max length for alias, host, name, env var, file path


def cmd_profile_add(args):
    # Validate field lengths to prevent oversized profile writes
    for label, val in [("alias", args.alias), ("host", args.host),
                       ("name", args.name or args.alias)]:
        if len(val) > _MAX_FIELD_LEN:
            stderr(f"Error: {label} exceeds {_MAX_FIELD_LEN} character limit.")
            sys.exit(1)
    pw_fields = _password_fields(args)
    for key in ("password_env", "password_file"):
        if key in pw_fields and len(pw_fields[key]) > _MAX_FIELD_LEN:
            stderr(f"Error: {key} value exceeds {_MAX_FIELD_LEN} character limit.")
            sys.exit(1)

    def _add(profiles):
        if args.alias in profiles:
            stderr(f"Profile '{args.alias}' already exists. Remove it first.")
            sys.exit(1)
        profiles[args.alias] = {
            "name": args.name or args.alias,
            "host": args.host,
            "port": args.port,
            "db": args.db,
            **pw_fields,
            "added": datetime.now(timezone.utc).isoformat(),
        }
        return profiles

    update_profiles(_add)
    stderr(f"Added profile '{args.alias}' ({args.host}:{args.port}/{args.db})")


def cmd_profile_remove(args):
    removed_name = [None]

    def _remove(profiles):
        if args.alias not in profiles:
            stderr(f"Profile '{args.alias}' not found.")
            sys.exit(1)
        removed_name[0] = profiles[args.alias].get("name", args.alias)
        del profiles[args.alias]
        return profiles

    update_profiles(_remove)
    stderr(f"Removed profile '{args.alias}' ({removed_name[0]})")


def cmd_profile_list(args):
    profiles = load_profiles()
    result = []
    for alias, info in profiles.items():
        has_pw = bool(info.get("password") or info.get("password_env") or info.get("password_file"))
        pw_source = "env" if info.get("password_env") else "file" if info.get("password_file") else "direct" if info.get("password") else None
        result.append({
            "alias": alias,
            "name": info.get("name", alias),
            "host": info["host"],
            "port": info["port"],
            "db": info.get("db", 0),
            "password": f"**** ({pw_source})" if has_pw else None,
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
        limit = getattr(args, "limit", 10000)
        # Enforce hard cap to bound memory (even when limit=0 or exceeds cap)
        effective_limit = MAX_KEYS_HARD_CAP if limit == 0 else min(limit, MAX_KEYS_HARD_CAP)
        scan_timeout = 30
        # Use redis-cli --scan with early termination at limit
        profile = get_profile(args.alias)
        redis_bin = _get_redis_cli()
        scan_cmd = [redis_bin, "-h", profile["host"], "-p", str(profile["port"]),
                    "-n", str(profile.get("db", 0)), "--scan", "--pattern", pattern]
        scan_env = _minimal_env()
        password = _resolve_profile_password(profile)
        if password:
            scan_env["REDISCLI_AUTH"] = password
        else:
            scan_env.pop("REDISCLI_AUTH", None)
        proc = subprocess.Popen(scan_cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=scan_env)
        keys = []
        total_bytes = 0
        deadline = time.monotonic() + scan_timeout
        killed_by_us = False
        # Non-blocking read of both stdout and stderr with selectors
        stdout_buf = b""
        stderr_chunks: list[bytes] = []
        sel = selectors.DefaultSelector()
        sel.register(proc.stdout, selectors.EVENT_READ, "stdout")
        sel.register(proc.stderr, selectors.EVENT_READ, "stderr")
        try:
            open_streams = 2
            done = False
            while not done and open_streams > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    proc.kill()
                    killed_by_us = True
                    stderr(f"Error: SCAN timed out after {scan_timeout} seconds.")
                    sys.exit(1)
                events = sel.select(timeout=remaining)
                if not events:
                    proc.kill()
                    killed_by_us = True
                    stderr(f"Error: SCAN timed out after {scan_timeout} seconds.")
                    sys.exit(1)
                for key, _ in events:
                    chunk = key.fileobj.read(65536)
                    if not chunk:
                        sel.unregister(key.fileobj)
                        open_streams -= 1
                        if key.data == "stdout" and stdout_buf:
                            line = stdout_buf.decode("utf-8", errors="replace").rstrip("\n")
                            if line:
                                keys.append(line)
                        continue
                    total_bytes += len(chunk)
                    if total_bytes > MAX_OUTPUT_BYTES:
                        proc.kill()
                        killed_by_us = True
                        stderr(f"Error: SCAN output exceeds {MAX_OUTPUT_BYTES // (1024 * 1024)} MB limit.")
                        sys.exit(1)
                    if key.data == "stderr":
                        stderr_chunks.append(chunk)
                        continue
                    # stdout: parse lines
                    stdout_buf += chunk
                    while b"\n" in stdout_buf:
                        raw_line, stdout_buf = stdout_buf.split(b"\n", 1)
                        line = raw_line.decode("utf-8", errors="replace")
                        if line:
                            keys.append(line)
                        if len(keys) >= effective_limit:
                            proc.kill()
                            killed_by_us = True
                            done = True
                            break
        except (OSError, ValueError) as e:
            proc.kill()
            proc.wait(timeout=5)
            stderr(f"Error: I/O failure reading SCAN output: {e}")
            sys.exit(1)
        finally:
            sel.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        # Distinguish our intentional kill from unexpected signal termination
        rc = proc.returncode
        if rc is not None and rc != 0 and not killed_by_us:
            err_text = b"".join(stderr_chunks).decode("utf-8", errors="replace").strip()
            if rc < 0:
                stderr(f"Error: redis-cli killed by signal {-rc}.")
            else:
                stderr(f"Redis error (exit {rc}):")
            if err_text:
                stderr(err_text)
            sys.exit(abs(rc))
        # Use compact output for large key lists to reduce memory/CPU
        out_json(keys, compact=len(keys) > 1000)

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

# Single-word destructive commands
_DESTRUCTIVE_CMDS = {"FLUSHDB", "FLUSHALL", "DEL", "UNLINK", "SHUTDOWN", "SWAPDB",
                     "MIGRATE", "MOVE", "RESTORE", "DUMP"}
# Two-word destructive subcommands: first word -> set of destructive second words
_DESTRUCTIVE_SUBCMDS = {
    "SCRIPT": {"FLUSH"},
    "FUNCTION": {"FLUSH", "DELETE", "RESTORE"},
    "CONFIG": {"SET", "RESETSTAT", "REWRITE"},
    "CLIENT": {"KILL"},
    "DEBUG": {"SET-ACTIVE-EXPIRE", "SLEEP", "SEGFAULT", "OOM", "PANIC", "CRASH-AND-RECOVER"},
    "CLUSTER": {"FLUSHSLOTS", "RESET", "FAILOVER", "FORGET", "DELSLOTS"},
    "ACL": {"SETUSER", "DELUSER"},
    "MEMORY": {"PURGE"},
    "LATENCY": {"RESET"},
    "SLOWLOG": {"RESET"},
    "BGREWRITEAOF": set(),
    "BGSAVE": set(),
}


def cmd_run(args):
    raw_args = args.extra_args
    if raw_args and raw_args[0] == "--":
        raw_args = raw_args[1:]
    if not raw_args:
        stderr("Error: No Redis command provided. Usage: run <alias> -- <command> [args...]")
        sys.exit(1)
    # Reject ALL flag-like args: connection settings come from the profile.
    # This prevents credential exfiltration via transport-redirecting flags.
    for arg in raw_args:
        if arg.startswith("-"):
            stderr(f"Error: Flags ('{arg}') are not allowed in run. "
                   "Connection settings come from the profile. "
                   "Pass only Redis commands and their arguments.")
            sys.exit(1)
    # Extract non-flag args to identify the command and subcommand
    non_flags = raw_args  # all args are non-flags after the check above
    if non_flags and not args.confirm:
        cmd_word = non_flags[0].upper()
        sub_word = non_flags[1].upper() if len(non_flags) > 1 else None
        destructive = False
        if cmd_word in _DESTRUCTIVE_CMDS:
            destructive = True
        elif cmd_word in _DESTRUCTIVE_SUBCMDS:
            # Commands that are always destructive (empty set = any subcommand)
            subs = _DESTRUCTIVE_SUBCMDS[cmd_word]
            if not subs or (sub_word and sub_word in subs):
                destructive = True
        if destructive:
            label = f"{cmd_word} {sub_word}" if sub_word and cmd_word in _DESTRUCTIVE_SUBCMDS else cmd_word
            stderr(f"Error: --confirm required for destructive command '{label}'.")
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

def _port(value: str) -> int:
    n = int(value)
    if n < 1 or n > 65535:
        raise argparse.ArgumentTypeError(f"port must be 1-65535, got {n}")
    return n


def _db_number(value: str) -> int:
    n = int(value)
    if n < 0 or n > 15:
        raise argparse.ArgumentTypeError(f"db must be 0-15, got {n}")
    return n


def _positive_int(value: str) -> int:
    n = int(value)
    if n <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {n}")
    return n


def _nonneg_int(value: str) -> int:
    n = int(value)
    if n < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {n}")
    return n


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Redis CLI wrapper with profiles and JSON output")
    parser.add_argument("--verbose", action="store_true",
                        help="Echo redis-cli commands to stderr (off by default)")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- profile ---
    profile_parser = sub.add_parser("profile", help="Manage connection profiles")
    profile_sub = profile_parser.add_subparsers(dest="profile_action", required=True)

    p = profile_sub.add_parser("add", help="Register a connection profile")
    p.add_argument("alias", help="Short alias (e.g. 'local', 'prod')")
    p.add_argument("--host", default="127.0.0.1", help="Redis host (default: 127.0.0.1)")
    p.add_argument("--port", type=_port, default=6379, help="Redis port (default: 6379)")
    p.add_argument("--db", type=_db_number, default=0, help="Database number (default: 0)")
    pw = p.add_mutually_exclusive_group()
    pw.add_argument("--password-env", metavar="VAR",
                    help="Env var containing Redis password (preferred)")
    pw.add_argument("--password-file", metavar="PATH",
                    help="File containing Redis password (single line, mode 600)")
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
    p.add_argument("--limit", type=_nonneg_int, default=10000,
                   help="Max keys to return (default: 10000, 0 = unlimited)")

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
    p.add_argument("seconds", type=_positive_int, help="TTL in seconds")

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
    p.add_argument("--ex", type=_positive_int, help="Expire after N seconds")
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
    run_parser.add_argument("--confirm", action="store_true",
                            help="Required for destructive commands (FLUSHDB, DEL, etc.)")
    run_parser.add_argument("extra_args", nargs=argparse.REMAINDER,
                            help="Redis command and arguments (after --)")

    return parser


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

def main():
    global VERBOSE
    parser = build_parser()
    args = parser.parse_args()
    VERBOSE = args.verbose
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
