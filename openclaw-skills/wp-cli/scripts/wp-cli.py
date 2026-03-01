# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""WP-CLI remote wrapper for agents. Runs WP-CLI commands over SSH.

Usage:
    uv run wp-cli.py <command> [options]

Requires WP-CLI installed on the remote server and SSH key access.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_data_dir() -> Path:
    workspace = os.environ.get("OPENCLAW_WORKSPACE")
    if workspace:
        d = Path(workspace) / "cache" / "wp-cli"
    else:
        d = Path.home() / ".openclaw" / "skills" / "wp-cli" / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_sites() -> dict:
    path = get_data_dir() / "sites.json"
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_sites(sites: dict):
    path = get_data_dir() / "sites.json"
    path.write_text(json.dumps(sites, indent=2) + "\n")


def get_site(alias: str) -> dict:
    sites = load_sites()
    if alias not in sites:
        stderr(f"Site '{alias}' not found. Use 'site list' to see registered sites.")
        sys.exit(1)
    return sites[alias]


def stderr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def _safe_output_path(filepath: str) -> Path:
    """Ensure output path doesn't escape the current working directory."""
    resolved = Path(filepath).resolve()
    cwd = Path.cwd().resolve()
    if not (str(resolved).startswith(str(cwd) + os.sep) or resolved == cwd):
        stderr(f"Error: Output path '{filepath}' is outside the current working directory.")
        sys.exit(1)
    return resolved


# --- WP-CLI core ---


def run_wp(site: dict, wp_args: list[str], json_format: bool = True) -> str | dict | list:
    """Run a WP-CLI command on the remote site via SSH."""
    ssh_target = f"{site['ssh']}:{site['path']}"
    cmd = ["wp", f"--ssh={ssh_target}"]

    if site.get("wp_user"):
        cmd.append(f"--user={site['wp_user']}")

    cmd.extend(wp_args)

    # Add --format=json if requested and not already present
    if json_format and not any(a.startswith("--format=") or a == "--format" for a in wp_args):
        cmd.append("--format=json")

    # Redact sensitive flags from command echo
    _SENSITIVE_FLAGS = {"--password", "--auth", "--key", "--token", "--secret"}
    display_cmd = []
    for a in cmd:
        if "=" in a:
            flag_part = a.split("=", 1)[0]
            if flag_part.lower() in _SENSITIVE_FLAGS:
                display_cmd.append(f"{flag_part}=****")
                continue
        display_cmd.append(a)
    stderr(f"$ {' '.join(display_cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        stderr("Error: 'wp' command not found. Ensure WP-CLI is installed locally.")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        stderr("Error: Command timed out after 120 seconds.")
        sys.exit(1)

    if result.returncode != 0:
        stderr(f"WP-CLI error (exit {result.returncode}):")
        if result.stderr:
            stderr(result.stderr.strip())
        sys.exit(result.returncode)

    output = result.stdout.strip()
    if not output:
        return {"ok": True}

    if json_format:
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return output

    return output


# --- Site management ---


def cmd_site_add(args):
    sites = load_sites()
    if args.alias in sites:
        stderr(f"Site '{args.alias}' already exists. Remove it first.")
        sys.exit(1)

    sites[args.alias] = {
        "name": args.name or args.alias,
        "ssh": args.ssh,
        "path": args.path,
        "wp_user": args.wp_user,
        "added": datetime.now(timezone.utc).isoformat(),
    }
    save_sites(sites)
    stderr(f"Added site '{args.alias}' ({args.ssh}:{args.path})")


def cmd_site_remove(args):
    sites = load_sites()
    if args.alias not in sites:
        stderr(f"Site '{args.alias}' not found.")
        sys.exit(1)
    name = sites[args.alias].get("name", args.alias)
    del sites[args.alias]
    save_sites(sites)
    stderr(f"Removed site '{args.alias}' ({name})")


def cmd_site_list(args):
    sites = load_sites()
    result = []
    for alias, info in sites.items():
        result.append({
            "alias": alias,
            "name": info.get("name", alias),
            "ssh": info.get("ssh"),
            "path": info.get("path"),
            "wp_user": info.get("wp_user"),
            "added": info.get("added"),
        })
    print(json.dumps(result, indent=2))


# --- Passthrough ---


def cmd_run(args):
    site = get_site(args.alias)
    output = run_wp(site, args.wp_args, json_format=True)
    if isinstance(output, str):
        print(output)
    else:
        print(json.dumps(output, indent=2, default=str))


# --- Status ---


def cmd_status(args):
    site = get_site(args.alias)
    result = {}

    # Core version
    version = run_wp(site, ["core", "version"], json_format=False)
    result["core_version"] = version.strip() if isinstance(version, str) else version

    # Plugin update count
    plugins = run_wp(site, ["plugin", "list", "--update=available"])
    if isinstance(plugins, list):
        result["plugins_needing_update"] = len(plugins)
        result["plugins_to_update"] = [p.get("name") for p in plugins]
    else:
        result["plugins_needing_update"] = 0

    # Maintenance mode
    maint = run_wp(site, ["maintenance-mode", "status"], json_format=False)
    if isinstance(maint, str):
        result["maintenance_mode"] = "on" in maint.lower()
    else:
        result["maintenance_mode"] = False

    print(json.dumps(result, indent=2))


# --- Plugins ---


def cmd_plugins(args):
    site = get_site(args.alias)
    data = run_wp(site, ["plugin", "list"])
    if isinstance(data, list):
        result = []
        for p in data:
            result.append({
                "name": p.get("name"),
                "status": p.get("status"),
                "version": p.get("version"),
                "update": p.get("update"),
                "update_version": p.get("update_version", ""),
            })
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(data, indent=2, default=str))


def cmd_update_plugins(args):
    site = get_site(args.alias)
    wp_args = ["plugin", "update"]
    if args.plugin:
        wp_args.append(args.plugin)
    else:
        wp_args.append("--all")
    output = run_wp(site, wp_args, json_format=False)
    if isinstance(output, str):
        print(json.dumps({"ok": True, "output": output}, indent=2))
    else:
        print(json.dumps(output, indent=2, default=str))
    stderr("Plugin update complete.")


# --- Cache ---


def cmd_flush_cache(args):
    site = get_site(args.alias)
    results = {}

    # wp cache flush
    out = run_wp(site, ["cache", "flush"], json_format=False)
    results["cache_flush"] = out.strip() if isinstance(out, str) else out

    # wp rocket clean (may fail if no WP Rocket)
    try:
        out = run_wp(site, ["rocket", "clean", "--confirm"], json_format=False)
        results["rocket_clean"] = out.strip() if isinstance(out, str) else out
    except SystemExit:
        results["rocket_clean"] = "skipped (WP Rocket not available)"

    # wp rocket preload
    try:
        out = run_wp(site, ["rocket", "preload"], json_format=False)
        results["rocket_preload"] = out.strip() if isinstance(out, str) else out
    except SystemExit:
        results["rocket_preload"] = "skipped (WP Rocket not available)"

    print(json.dumps(results, indent=2))


# --- Maintenance ---


def cmd_maintenance(args):
    site = get_site(args.alias)
    if args.state == "status":
        out = run_wp(site, ["maintenance-mode", "status"], json_format=False)
        enabled = "on" in out.lower() if isinstance(out, str) else False
        print(json.dumps({"maintenance_mode": enabled}, indent=2))
    elif args.state in ("on", "off"):
        action = "activate" if args.state == "on" else "deactivate"
        out = run_wp(site, ["maintenance-mode", action], json_format=False)
        print(json.dumps({"ok": True, "maintenance_mode": args.state}, indent=2))
        stderr(f"Maintenance mode {args.state}")


# --- Backup ---


def cmd_backup_db(args):
    site = get_site(args.alias)
    wp_args = ["db", "export"]
    if args.output:
        wp_args.append(args.output)
    else:
        wp_args.append("-")  # stdout
    out = run_wp(site, wp_args, json_format=False)
    if args.output:
        print(json.dumps({"ok": True, "output": args.output}, indent=2))
        stderr(f"Database exported to {args.output}")
    else:
        print(out)


# --- Plugin-specific wrappers ---


def cmd_elementor(args):
    site = get_site(args.alias)
    if args.elementor_action == "flush-css":
        out = run_wp(site, ["elementor", "flush-css"], json_format=False)
        print(json.dumps({"ok": True, "output": out.strip() if isinstance(out, str) else out}, indent=2))
    elif args.elementor_action == "replace-urls":
        out = run_wp(site, ["elementor", "replace-urls", args.old, args.new], json_format=False)
        print(json.dumps({"ok": True, "output": out.strip() if isinstance(out, str) else out}, indent=2))


def cmd_rocket(args):
    site = get_site(args.alias)
    if args.rocket_action == "clean":
        out = run_wp(site, ["rocket", "clean", "--confirm"], json_format=False)
    elif args.rocket_action == "preload":
        out = run_wp(site, ["rocket", "preload"], json_format=False)
    print(json.dumps({"ok": True, "output": out.strip() if isinstance(out, str) else out}, indent=2))


def cmd_imagify(args):
    site = get_site(args.alias)
    wp_args = ["imagify", "optimize"]
    if args.lossless:
        wp_args.append("--lossless")
    out = run_wp(site, wp_args, json_format=False)
    print(json.dumps({"ok": True, "output": out.strip() if isinstance(out, str) else out}, indent=2))


def cmd_seopress(args):
    site = get_site(args.alias)
    if args.seopress_action == "export":
        out = run_wp(site, ["seopress", "export"], json_format=False)
        if args.file:
            safe_path = _safe_output_path(args.file)
            safe_path.write_text(out if isinstance(out, str) else json.dumps(out))
            print(json.dumps({"ok": True, "exported_to": str(safe_path)}, indent=2))
        else:
            print(out)
    elif args.seopress_action == "import":
        out = run_wp(site, ["seopress", "import", args.file], json_format=False)
        print(json.dumps({"ok": True, "output": out.strip() if isinstance(out, str) else out}, indent=2))


def cmd_gf(args):
    site = get_site(args.alias)
    if args.gf_action == "forms":
        data = run_wp(site, ["gf", "form", "list"])
        print(json.dumps(data, indent=2, default=str))
    elif args.gf_action == "entries":
        wp_args = ["gf", "entry", "list", str(args.form_id)]
        if args.limit:
            wp_args.extend(["--page-size", str(args.limit)])
        data = run_wp(site, wp_args)
        print(json.dumps(data, indent=2, default=str))


def cmd_redirection(args):
    site = get_site(args.alias)
    if args.redir_action == "export":
        out = run_wp(site, ["redirection", "export", args.file, "--format=json"], json_format=False)
        print(json.dumps({"ok": True, "exported_to": args.file}, indent=2))
    elif args.redir_action == "import":
        out = run_wp(site, ["redirection", "import", args.file], json_format=False)
        print(json.dumps({"ok": True, "output": out.strip() if isinstance(out, str) else out}, indent=2))


# --- Argument parser ---


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WP-CLI remote wrapper for agents")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- site ---
    site_parser = sub.add_parser("site", help="Manage registered sites")
    site_sub = site_parser.add_subparsers(dest="site_action", required=True)

    p = site_sub.add_parser("add", help="Register a site")
    p.add_argument("alias", help="Short alias (e.g. 'prod')")
    p.add_argument("--ssh", required=True, help="SSH target (user@host)")
    p.add_argument("--path", required=True, help="WP install path on server")
    p.add_argument("--name", help="Human-readable label")
    p.add_argument("--wp-user", help="WordPress user for --user flag")

    p = site_sub.add_parser("remove", help="Remove a registered site")
    p.add_argument("alias", help="Site alias")

    site_sub.add_parser("list", help="List registered sites")

    # --- run (passthrough) ---
    run_parser = sub.add_parser("run", help="Run any WP-CLI command")
    run_parser.add_argument("alias", help="Site alias")
    run_parser.add_argument("wp_args", nargs=argparse.REMAINDER, help="WP-CLI arguments (after --)")

    # --- status ---
    p = sub.add_parser("status", help="Site status overview")
    p.add_argument("alias", help="Site alias")

    # --- plugins ---
    p = sub.add_parser("plugins", help="List plugins with update info")
    p.add_argument("alias", help="Site alias")

    # --- update-plugins ---
    p = sub.add_parser("update-plugins", help="Update plugins")
    p.add_argument("alias", help="Site alias")
    p.add_argument("--plugin", help="Specific plugin name (default: all)")

    # --- flush-cache ---
    p = sub.add_parser("flush-cache", help="Flush all caches")
    p.add_argument("alias", help="Site alias")

    # --- maintenance ---
    p = sub.add_parser("maintenance", help="Maintenance mode control")
    p.add_argument("alias", help="Site alias")
    p.add_argument("state", choices=["on", "off", "status"], help="on|off|status")

    # --- backup-db ---
    p = sub.add_parser("backup-db", help="Export database")
    p.add_argument("alias", help="Site alias")
    p.add_argument("--output", help="Output file path (default: stdout)")

    # --- elementor ---
    elementor_parser = sub.add_parser("elementor", help="Elementor commands")
    elementor_parser.add_argument("alias", help="Site alias")
    elem_sub = elementor_parser.add_subparsers(dest="elementor_action", required=True)
    elem_sub.add_parser("flush-css", help="Regenerate Elementor CSS")
    p = elem_sub.add_parser("replace-urls", help="Replace URLs in Elementor data")
    p.add_argument("old", help="Old URL")
    p.add_argument("new", help="New URL")

    # --- rocket ---
    rocket_parser = sub.add_parser("rocket", help="WP Rocket commands")
    rocket_parser.add_argument("alias", help="Site alias")
    rocket_sub = rocket_parser.add_subparsers(dest="rocket_action", required=True)
    rocket_sub.add_parser("clean", help="Clean WP Rocket cache")
    rocket_sub.add_parser("preload", help="Preload WP Rocket cache")

    # --- imagify ---
    imagify_parser = sub.add_parser("imagify", help="Imagify optimization")
    imagify_parser.add_argument("alias", help="Site alias")
    imagify_sub = imagify_parser.add_subparsers(dest="imagify_action", required=True)
    p = imagify_sub.add_parser("optimize", help="Optimize images")
    p.add_argument("--lossless", action="store_true", help="Use lossless compression")

    # --- seopress ---
    seopress_parser = sub.add_parser("seopress", help="SEOPress commands")
    seopress_parser.add_argument("alias", help="Site alias")
    seopress_sub = seopress_parser.add_subparsers(dest="seopress_action", required=True)
    p = seopress_sub.add_parser("export", help="Export SEOPress settings")
    p.add_argument("file", nargs="?", help="Output file path")
    p = seopress_sub.add_parser("import", help="Import SEOPress settings")
    p.add_argument("file", help="Input file path")

    # --- gf ---
    gf_parser = sub.add_parser("gf", help="Gravity Forms commands")
    gf_parser.add_argument("alias", help="Site alias")
    gf_sub = gf_parser.add_subparsers(dest="gf_action", required=True)
    gf_sub.add_parser("forms", help="List forms")
    p = gf_sub.add_parser("entries", help="List entries for a form")
    p.add_argument("form_id", type=int, help="Form ID")
    p.add_argument("--limit", type=int, help="Number of entries")

    # --- redirection ---
    redir_parser = sub.add_parser("redirection", help="Redirection plugin commands")
    redir_parser.add_argument("alias", help="Site alias")
    redir_sub = redir_parser.add_subparsers(dest="redir_action", required=True)
    p = redir_sub.add_parser("export", help="Export redirects")
    p.add_argument("file", help="Output file path")
    p = redir_sub.add_parser("import", help="Import redirects")
    p.add_argument("file", help="Input file path")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    cmd = args.command

    if cmd == "site":
        if args.site_action == "add":
            cmd_site_add(args)
        elif args.site_action == "remove":
            cmd_site_remove(args)
        elif args.site_action == "list":
            cmd_site_list(args)

    elif cmd == "run":
        # Strip leading '--' from wp_args if present
        if args.wp_args and args.wp_args[0] == "--":
            args.wp_args = args.wp_args[1:]
        cmd_run(args)

    elif cmd == "status":
        cmd_status(args)
    elif cmd == "plugins":
        cmd_plugins(args)
    elif cmd == "update-plugins":
        cmd_update_plugins(args)
    elif cmd == "flush-cache":
        cmd_flush_cache(args)
    elif cmd == "maintenance":
        cmd_maintenance(args)
    elif cmd == "backup-db":
        cmd_backup_db(args)
    elif cmd == "elementor":
        cmd_elementor(args)
    elif cmd == "rocket":
        cmd_rocket(args)
    elif cmd == "imagify":
        cmd_imagify(args)
    elif cmd == "seopress":
        cmd_seopress(args)
    elif cmd == "gf":
        cmd_gf(args)
    elif cmd == "redirection":
        cmd_redirection(args)


if __name__ == "__main__":
    main()
