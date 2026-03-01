# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Virtualmin Remote API CLI for agents. Manage virtual servers, databases, SSL, backups, and more.

Usage:
    uv run virtualmin.py <command> [options]

Uses HTTP basic auth against the Virtualmin Remote API (port 10000).
"""

import argparse
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import urllib3

# Suppress InsecureRequestWarning for self-signed certs on port 10000
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# --- Data helpers ---


def get_data_dir() -> Path:
    d = Path.home() / ".claude" / "skills" / "virtualmin" / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_servers() -> dict:
    path = get_data_dir() / "servers.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_servers(servers: dict):
    path = get_data_dir() / "servers.json"
    path.write_text(json.dumps(servers, indent=2) + "\n")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600


def get_server(alias: str) -> dict:
    servers = load_servers()
    if alias not in servers:
        stderr(f"Server '{alias}' not found. Use 'server list' to see registered servers.")
        sys.exit(1)
    return servers[alias]


# --- Output helpers ---


def stderr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def out_json(data):
    print(json.dumps(data, indent=2, default=str))


def mask_password(pw: str) -> str:
    if not pw or len(pw) < 8:
        return "****"
    return pw[:4] + " " + "*" * (len(pw) - 5)


# --- Param parsing ---


def parse_extra_params(extra: list[str]) -> list[tuple[str, str]]:
    """Convert CLI-style args to API param tuples.

    --key value  -> ("key", "value")
    --key=value  -> ("key", "value")
    --flag       -> ("flag", "")
    Leading -- separator is stripped if present.
    """
    if not extra:
        return []
    params = []
    args = list(extra)
    # Strip leading -- separator
    if args and args[0] == "--":
        args = args[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            key_part = arg[2:]  # strip --
            if "=" in key_part:
                key, value = key_part.split("=", 1)
                params.append((key, value))
            elif i + 1 < len(args) and not args[i + 1].startswith("--"):
                params.append((key_part, args[i + 1]))
                i += 1
            else:
                params.append((key_part, ""))
        i += 1
    return params


# --- API core ---


def call_api(server: dict, program: str, params: list[tuple[str, str]] | None = None,
             json_mode: bool = True, timeout: int = 120) -> dict:
    """HTTP POST to Virtualmin remote.cgi. Returns parsed JSON or exits on error."""
    host = server["host"]
    port = server.get("port", 10000)
    url = f"https://{host}:{port}/virtual-server/remote.cgi"

    form_data: list[tuple[str, str]] = [("program", program)]
    if json_mode:
        form_data.append(("json", "1"))
    if params:
        form_data.extend(params)

    verify_ssl = server.get("verify_ssl", False)

    # Log the call (mask password in auth)
    stderr(f">> {program} on {host}:{port}")

    try:
        resp = requests.post(
            url,
            data=form_data,
            auth=(server["username"], server["password"]),
            verify=verify_ssl,
            timeout=timeout,
        )
    except requests.ConnectionError as e:
        stderr(f"Connection failed to {host}:{port}: {e}")
        sys.exit(1)
    except requests.Timeout:
        stderr(f"Request timed out after {timeout}s to {host}:{port}")
        sys.exit(1)
    except requests.RequestException as e:
        stderr(f"Request failed: {e}")
        sys.exit(1)

    if resp.status_code == 401:
        stderr(f"Authentication failed for {server['username']}@{host}:{port}")
        sys.exit(1)

    if resp.status_code >= 400:
        stderr(f"HTTP error {resp.status_code}: {resp.text[:300]}")
        sys.exit(1)

    if not json_mode:
        return {"raw": resp.text}

    try:
        data = resp.json()
    except ValueError:
        stderr(f"Non-JSON response: {resp.text[:300]}")
        sys.exit(1)

    # Virtualmin JSON responses have a "status" field: "success" or "error"
    if isinstance(data, dict) and data.get("status") == "error":
        stderr(f"API error: {data.get('error', resp.text[:300])}")
        sys.exit(1)

    return data


# --- Server commands ---


def cmd_server_add(args):
    servers = load_servers()
    if args.alias in servers:
        stderr(f"Server '{args.alias}' already exists. Remove it first.")
        sys.exit(1)

    if hasattr(args, "password") and args.password:
        stderr("Warning: --pass is visible in process listings. Consider setting VM_PASSWORD env var.")

    password = args.password or os.environ.get("VM_PASSWORD", "")
    if not password:
        stderr("Error: password required via --pass or VM_PASSWORD env var.")
        sys.exit(1)

    servers[args.alias] = {
        "name": args.name or args.alias,
        "host": args.host,
        "port": args.port,
        "username": args.user,
        "password": password,
        "verify_ssl": not args.no_verify,
        "added": datetime.now(timezone.utc).isoformat(),
    }
    save_servers(servers)
    stderr(f"Added server '{args.alias}' ({args.host}:{args.port})")


def cmd_server_remove(args):
    servers = load_servers()
    if args.alias not in servers:
        stderr(f"Server '{args.alias}' not found.")
        sys.exit(1)
    name = servers[args.alias].get("name", args.alias)
    del servers[args.alias]
    save_servers(servers)
    stderr(f"Removed server '{args.alias}' ({name})")


def cmd_server_list(args):
    servers = load_servers()
    result = []
    for alias, info in servers.items():
        result.append({
            "alias": alias,
            "name": info.get("name", alias),
            "host": info.get("host"),
            "port": info.get("port", 10000),
            "username": info.get("username"),
            "password": mask_password(info.get("password", "")),
            "verify_ssl": info.get("verify_ssl", False),
            "added": info.get("added"),
        })
    out_json(result)


# --- Passthrough ---


def cmd_run(args):
    server = get_server(args.alias)
    extra = parse_extra_params(args.extra)
    data = call_api(server, args.program, params=extra)
    out_json(data)


# --- Domain commands ---


def cmd_domains(args):
    server = get_server(args.alias)
    action = args.domains_action

    if action == "list":
        params = []
        if args.domain:
            params.append(("domain", args.domain))
        if args.user:
            params.append(("user", args.user))
        if args.name_only:
            params.append(("name-only", ""))
        if args.toplevel:
            params.append(("toplevel", ""))
        if args.with_feature:
            params.append(("with-feature", args.with_feature))
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "list-domains", params=params)
        out_json(data)

    elif action == "info":
        params = [("domain", args.domain), ("multiline", "")]
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "list-domains", params=params)
        out_json(data)

    elif action == "create":
        params = [("domain", args.domain), ("pass", args.password)]
        if args.plan:
            params.append(("plan", args.plan))
        if args.ip:
            params.append(("ip", args.ip))
        if args.features_from_plan:
            params.append(("features-from-plan", ""))
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "create-domain", params=params)
        out_json(data)
        stderr(f"Created domain {args.domain}")

    elif action == "delete":
        params = [("domain", args.domain)]
        if args.only:
            params.append(("only", args.only))
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "delete-domain", params=params)
        out_json(data)
        stderr(f"Deleted domain {args.domain}")

    elif action == "enable":
        params = [("domain", args.domain)]
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "enable-domain", params=params)
        out_json(data)
        stderr(f"Enabled domain {args.domain}")

    elif action == "disable":
        params = [("domain", args.domain)]
        if args.why:
            params.append(("why", args.why))
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "disable-domain", params=params)
        out_json(data)
        stderr(f"Disabled domain {args.domain}")

    elif action == "modify":
        params = [("domain", args.domain)]
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "modify-domain", params=params)
        out_json(data)
        stderr(f"Modified domain {args.domain}")

    elif action == "validate":
        params = []
        if args.domain:
            params.append(("domain", args.domain))
        if args.all_domains:
            params.append(("all-domains", ""))
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "validate-domains", params=params)
        out_json(data)


# --- Database commands ---


def cmd_db(args):
    server = get_server(args.alias)
    action = args.db_action

    if action == "list":
        params = [("domain", args.domain)]
        if args.type:
            params.append(("type", args.type))
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "list-databases", params=params)
        out_json(data)

    elif action == "create":
        params = [("domain", args.domain), ("name", args.name), ("type", args.type)]
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "create-database", params=params)
        out_json(data)
        stderr(f"Created {args.type} database '{args.name}' for {args.domain}")

    elif action == "delete":
        params = [("domain", args.domain), ("name", args.name), ("type", args.type)]
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "delete-database", params=params)
        out_json(data)
        stderr(f"Deleted {args.type} database '{args.name}' from {args.domain}")


# --- SSL commands ---


def cmd_ssl(args):
    server = get_server(args.alias)
    action = args.ssl_action

    if action == "list":
        params = [("domain", args.domain)]
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "list-certs", params=params)
        out_json(data)

    elif action == "expiry":
        params = []
        if args.domain:
            params.append(("domain", args.domain))
        if args.all_domains:
            params.append(("all-domains", ""))
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "list-certs-expiry", params=params)
        out_json(data)

    elif action == "letsencrypt":
        params = [("domain", args.domain)]
        if args.renew:
            params.append(("renew", ""))
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "generate-letsencrypt-cert", params=params)
        out_json(data)
        stderr(f"Let's Encrypt cert {'renewed' if args.renew else 'generated'} for {args.domain}")

    elif action == "install":
        params = [("domain", args.domain)]
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "install-cert", params=params)
        out_json(data)
        stderr(f"Installed cert for {args.domain}")


# --- Backup commands ---


def cmd_backup(args):
    server = get_server(args.alias)
    action = args.backup_action

    if action == "create":
        params = []
        if args.domain:
            params.append(("domain", args.domain))
        if args.all_domains:
            params.append(("all-domains", ""))
        if args.dest:
            params.append(("dest", args.dest))
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "backup-domain", params=params)
        out_json(data)
        stderr("Backup created")

    elif action == "restore":
        params = [("domain", args.domain), ("source", args.source)]
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "restore-domain", params=params)
        out_json(data)
        stderr(f"Restored {args.domain} from {args.source}")

    elif action == "scheduled":
        data = call_api(server, "list-scheduled-backups")
        out_json(data)

    elif action == "keys":
        data = call_api(server, "list-backup-keys")
        out_json(data)


# --- PHP commands ---


def cmd_php(args):
    server = get_server(args.alias)
    action = args.php_action

    if action == "versions":
        data = call_api(server, "list-php-versions")
        out_json(data)

    elif action == "dirs":
        params = [("domain", args.domain)]
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "list-php-directories", params=params)
        out_json(data)

    elif action == "set-dir":
        params = [
            ("domain", args.domain),
            ("dir", args.dir),
            ("version", args.version),
        ]
        params.extend(parse_extra_params(args.extra))
        data = call_api(server, "set-php-directory", params=params)
        out_json(data)
        stderr(f"Set PHP {args.version} for {args.dir} on {args.domain}")


# --- System commands ---


def cmd_system(args):
    server = get_server(args.alias)
    action = args.system_action

    if action == "info":
        data = call_api(server, "info")
        out_json(data)

    elif action == "check":
        data = call_api(server, "check-config")
        out_json(data)

    elif action == "restart":
        data = call_api(server, "restart-server")
        out_json(data)
        stderr("Server restart initiated")

    elif action == "status":
        data = call_api(server, "list-server-statuses")
        out_json(data)

    elif action == "features":
        data = call_api(server, "list-features")
        out_json(data)


# --- Argument parser ---


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Virtualmin Remote API CLI for agents"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- server ---
    server_parser = sub.add_parser("server", help="Manage registered Virtualmin servers")
    server_sub = server_parser.add_subparsers(dest="server_action", required=True)

    p = server_sub.add_parser("add", help="Register a Virtualmin server")
    p.add_argument("alias", help="Short alias for the server (e.g. 'prod')")
    p.add_argument("--host", required=True, help="Hostname or IP address")
    p.add_argument("--user", required=True, help="Virtualmin admin username")
    p.add_argument("--pass", dest="password", default="", help="Admin password (or set VM_PASSWORD env var)")
    p.add_argument("--port", type=int, default=10000, help="Webmin port (default: 10000)")
    p.add_argument("--no-verify", action="store_true", help="Skip SSL certificate verification (default: verify is off)")
    p.add_argument("--name", help="Human-readable label")

    p = server_sub.add_parser("remove", help="Remove a registered server")
    p.add_argument("alias", help="Server alias")

    server_sub.add_parser("list", help="List registered servers")

    # --- run (passthrough) ---
    run_parser = sub.add_parser("run", help="Run any Virtualmin API program")
    run_parser.add_argument("alias", help="Server alias")
    run_parser.add_argument("program", help="API program name (e.g. list-domains)")
    run_parser.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params (after --)")

    # --- domains ---
    domains_parser = sub.add_parser("domains", help="Virtual server (domain) management")
    domains_parser.add_argument("alias", help="Server alias")
    domains_sub = domains_parser.add_subparsers(dest="domains_action", required=True)

    p = domains_sub.add_parser("list", help="List virtual servers")
    p.add_argument("--domain", help="Filter by domain name")
    p.add_argument("--user", help="Filter by owner username")
    p.add_argument("--name-only", action="store_true", help="Show domain names only")
    p.add_argument("--toplevel", action="store_true", help="Only top-level domains")
    p.add_argument("--with-feature", help="Only domains with this feature enabled")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = domains_sub.add_parser("info", help="Detailed info for a single domain")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = domains_sub.add_parser("create", help="Create a virtual server")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("--pass", dest="password", required=True, help="Admin password for the domain")
    p.add_argument("--plan", help="Hosting plan name")
    p.add_argument("--ip", help="IP address to assign")
    p.add_argument("--features-from-plan", action="store_true", help="Use features from the plan")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = domains_sub.add_parser("delete", help="Delete a virtual server")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("--only", help="Only delete specific features")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = domains_sub.add_parser("enable", help="Enable a virtual server")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = domains_sub.add_parser("disable", help="Disable a virtual server")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("--why", help="Reason for disabling")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = domains_sub.add_parser("modify", help="Modify a virtual server")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params (all modify-domain flags)")

    p = domains_sub.add_parser("validate", help="Validate virtual server configuration")
    p.add_argument("--domain", help="Domain name (or use --all-domains)")
    p.add_argument("--all-domains", action="store_true", help="Validate all domains")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    # --- db ---
    db_parser = sub.add_parser("db", help="Database management")
    db_parser.add_argument("alias", help="Server alias")
    db_sub = db_parser.add_subparsers(dest="db_action", required=True)

    p = db_sub.add_parser("list", help="List databases for a domain")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("--type", help="Database type (mysql|postgres)")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = db_sub.add_parser("create", help="Create a database")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("--name", required=True, help="Database name")
    p.add_argument("--type", required=True, help="Database type (mysql|postgres)")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = db_sub.add_parser("delete", help="Delete a database")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("--name", required=True, help="Database name")
    p.add_argument("--type", required=True, help="Database type (mysql|postgres)")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    # --- ssl ---
    ssl_parser = sub.add_parser("ssl", help="SSL certificate management")
    ssl_parser.add_argument("alias", help="Server alias")
    ssl_sub = ssl_parser.add_subparsers(dest="ssl_action", required=True)

    p = ssl_sub.add_parser("list", help="List SSL certificates for a domain")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = ssl_sub.add_parser("expiry", help="Check SSL certificate expiry dates")
    p.add_argument("--domain", help="Domain name (or use --all-domains)")
    p.add_argument("--all-domains", action="store_true", help="Check all domains")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = ssl_sub.add_parser("letsencrypt", help="Generate or renew Let's Encrypt certificate")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("--renew", action="store_true", help="Renew existing certificate")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = ssl_sub.add_parser("install", help="Install an SSL certificate")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params (cert, key, ca paths)")

    # --- backup ---
    backup_parser = sub.add_parser("backup", help="Backup and restore")
    backup_parser.add_argument("alias", help="Server alias")
    backup_sub = backup_parser.add_subparsers(dest="backup_action", required=True)

    p = backup_sub.add_parser("create", help="Create a backup")
    p.add_argument("--domain", help="Domain name (or use --all-domains)")
    p.add_argument("--all-domains", action="store_true", help="Backup all domains")
    p.add_argument("--dest", help="Backup destination path")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = backup_sub.add_parser("restore", help="Restore from a backup")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("--source", required=True, help="Backup source path")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = backup_sub.add_parser("scheduled", help="List scheduled backups")

    p = backup_sub.add_parser("keys", help="List backup encryption keys")

    # --- php ---
    php_parser = sub.add_parser("php", help="PHP version management")
    php_parser.add_argument("alias", help="Server alias")
    php_sub = php_parser.add_subparsers(dest="php_action", required=True)

    php_sub.add_parser("versions", help="List available PHP versions")

    p = php_sub.add_parser("dirs", help="List PHP directories for a domain")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    p = php_sub.add_parser("set-dir", help="Set PHP version for a directory")
    p.add_argument("--domain", required=True, help="Domain name")
    p.add_argument("--dir", required=True, help="Directory path")
    p.add_argument("--version", required=True, help="PHP version (e.g. 8.2)")
    p.add_argument("extra", nargs=argparse.REMAINDER, help="Extra params")

    # --- system ---
    system_parser = sub.add_parser("system", help="System information and management")
    system_parser.add_argument("alias", help="Server alias")
    system_sub = system_parser.add_subparsers(dest="system_action", required=True)

    system_sub.add_parser("info", help="Server information")
    system_sub.add_parser("check", help="Check Virtualmin configuration")
    system_sub.add_parser("restart", help="Restart Virtualmin services")
    system_sub.add_parser("status", help="List server statuses")
    system_sub.add_parser("features", help="List available features")

    return parser


# --- Main dispatch ---


def main():
    parser = build_parser()
    args = parser.parse_args()
    cmd = args.command

    if cmd == "server":
        if args.server_action == "add":
            cmd_server_add(args)
        elif args.server_action == "remove":
            cmd_server_remove(args)
        elif args.server_action == "list":
            cmd_server_list(args)

    elif cmd == "run":
        cmd_run(args)

    elif cmd == "domains":
        cmd_domains(args)

    elif cmd == "db":
        cmd_db(args)

    elif cmd == "ssl":
        cmd_ssl(args)

    elif cmd == "backup":
        cmd_backup(args)

    elif cmd == "php":
        cmd_php(args)

    elif cmd == "system":
        cmd_system(args)


if __name__ == "__main__":
    main()
