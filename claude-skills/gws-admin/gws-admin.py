#!/usr/bin/env python3
# gws-admin.py
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""Google Workspace Admin Skill (GAM7 Wrapper)

A structured, agent-friendly wrapper around GAM7 for managing Google Workspace
from the CLI. Provides organized subcommands, safety guardrails, JSON output,
and a guided setup wizard.

Usage:
    uv run gws-admin.py <command> [options]

Environment:
    GAMCFGDIR       — GAM config directory (default: ~/.claude/skills/gws-admin/gam-config/)
    GAM_ADMIN_EMAIL — Admin email for domain-wide operations
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

GAM_CONFIG_DIR = Path.home() / ".claude" / "skills" / "gws-admin" / "gam-config"


def get_gam_path() -> str | None:
    return shutil.which("gam")


def ensure_gam_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GAMCFGDIR"] = str(GAM_CONFIG_DIR)
    return env


def run_gam(args: list[str], *, capture: bool = True, env: dict | None = None,
            password: str | None = None) -> subprocess.CompletedProcess:
    """Run a GAM command. If password is provided, it's written to a tempfile
    and passed via GAM's 'password file:<path>' syntax to avoid exposure in
    the process argument list (visible via /proc/cmdline)."""
    gam = get_gam_path()
    if not gam:
        print("ERROR: GAM is not installed. Run 'gws-admin.py setup' first.", file=sys.stderr)
        sys.exit(1)
    cmd = [gam] + args
    if env is None:
        env = ensure_gam_env()
    # Use tempfile for password to avoid /proc exposure
    pw_tmpfile = None
    if password:
        import tempfile
        pw_tmpfile = tempfile.NamedTemporaryFile(mode="w", suffix=".pw", delete=False)
        pw_tmpfile.write(password)
        pw_tmpfile.close()
        os.chmod(pw_tmpfile.name, 0o600)
        cmd.extend(["password", f"file:{pw_tmpfile.name}"])
    try:
        if capture:
            return subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)
        else:
            return subprocess.run(cmd, text=True, env=env, timeout=300)
    except FileNotFoundError:
        print("ERROR: GAM binary not found. Ensure GAM is installed and in PATH.", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("ERROR: GAM command timed out after 300 seconds.", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"ERROR: Failed to execute GAM: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if pw_tmpfile:
            try:
                os.unlink(pw_tmpfile.name)
            except OSError:
                pass


def gam_output_to_json(stdout: str) -> list[dict]:
    lines = [l.strip() for l in stdout.strip().splitlines() if l.strip()]
    if not lines:
        return []
    if "," in lines[0] and not lines[0].startswith("{"):
        import csv
        import io
        reader = csv.DictReader(io.StringIO(stdout))
        return [row for row in reader]
    results = []
    current: dict[str, str] = {}
    for line in lines:
        if ": " in line:
            key, _, value = line.partition(": ")
            current[key.strip()] = value.strip()
        elif line == "---" or line == "":
            if current:
                results.append(current)
                current = {}
        else:
            if current:
                results.append(current)
                current = {}
            current["_raw"] = line
    if current:
        results.append(current)
    return results


def print_json(data):
    print(json.dumps(data, indent=2, default=str))


def check_confirm(args, operation: str) -> bool:
    if getattr(args, "dry_run", False):
        return False
    if not getattr(args, "confirm", False):
        print(f"WARNING: {operation} is a destructive operation.")
        print("Add --confirm to execute, or --dry-run to preview.")
        return False
    return True


def _redact_gam_args(gam_args: list[str]) -> list[str]:
    """Redact password values from GAM argument lists for display."""
    redacted = []
    skip_next = False
    for arg in gam_args:
        if skip_next:
            redacted.append("****")
            skip_next = False
        elif arg == "password":
            redacted.append(arg)
            skip_next = True
        else:
            redacted.append(arg)
    return redacted


def print_dry_run(gam_args: list[str]):
    print("[DRY RUN] Would execute:")
    print(f"  gam {' '.join(_redact_gam_args(gam_args))}")


# --- Setup ---

def cmd_setup(args):
    print("=== Google Workspace Admin — First-Time Setup ===\n")

    # Step 1: Check/install GAM
    gam = get_gam_path()
    if gam:
        print(f"[OK] GAM found at: {gam}")
    else:
        print("[1/5] Installing GAM7 via pip...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "advanced-gam-for-google-workspace"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"ERROR: Failed to install GAM7:\n{result.stderr}", file=sys.stderr)
            sys.exit(1)
        print("[OK] GAM7 installed successfully.")
        gam = get_gam_path()
        if not gam:
            print("WARNING: 'gam' not found in PATH after install.")
            print("You may need to add the pip scripts directory to your PATH.")
            sys.exit(1)

    # Step 2: Create config directory
    GAM_CONFIG_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Ensure restrictive permissions on credential directory
    GAM_CONFIG_DIR.chmod(0o700)
    print(f"\n[OK] Config directory: {GAM_CONFIG_DIR}")

    env = ensure_gam_env()

    # Step 3: Create GCP project
    print("\n[2/5] Creating GCP project for GAM...")
    print("This will open a browser for Google authentication.")
    print("You need a Google Workspace super admin account.\n")
    input("Press Enter to continue (or Ctrl+C to abort)...")
    result = subprocess.run([gam, "create", "project"], text=True, env=env)
    if result.returncode != 0:
        print("WARNING: 'gam create project' exited with errors. Check output above.")

    # Step 4: OAuth authorization
    print("\n[3/5] Authorizing OAuth credentials...")
    print("This will open a browser for OAuth consent.\n")
    input("Press Enter to continue...")
    result = subprocess.run([gam, "oauth", "create"], text=True, env=env)
    if result.returncode != 0:
        print("WARNING: 'gam oauth create' exited with errors. Check output above.")

    # Step 5: Service account setup
    print("\n[4/5] Configuring service account for domain-wide delegation...")
    input("Press Enter to continue...")
    result = subprocess.run([gam, "update", "serviceaccount"], text=True, env=env)
    if result.returncode != 0:
        print("WARNING: 'gam update serviceaccount' exited with errors.")

    # Step 6: Verify service account
    print("\n[5/5] Verifying service account access...")
    result = subprocess.run([gam, "check", "serviceaccount"], text=True, env=env)
    if result.returncode != 0:
        print("WARNING: Service account check had issues. You may need to")
        print("authorize domain-wide delegation in the Google Admin console.")
        print("See README.md for detailed instructions.")

    print("\n=== Setup Complete ===")
    print(f"Config stored in: {GAM_CONFIG_DIR}")
    print("Run 'gws-admin.py status' to verify connectivity.")


# --- Status ---

def cmd_status(args):
    print("=== Google Workspace Admin — Status ===\n")
    ok = True

    # Check GAM binary
    gam = get_gam_path()
    if gam:
        print(f"[OK] GAM binary: {gam}")
        result = subprocess.run([gam, "version"], capture_output=True, text=True, env=ensure_gam_env())
        version_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else "unknown"
        print(f"     Version: {version_line}")
    else:
        print("[MISSING] GAM is not installed")
        ok = False

    # Check config directory
    print(f"\n[{'OK' if GAM_CONFIG_DIR.is_dir() else 'MISSING'}] Config dir: {GAM_CONFIG_DIR}")

    # Check config files
    config_files = {
        "gam.cfg": "Main configuration",
        "oauth2.txt": "OAuth tokens",
        "oauth2service.json": "Service account key",
        "client_secrets.json": "OAuth client credentials",
    }
    for fname, desc in config_files.items():
        fpath = GAM_CONFIG_DIR / fname
        status = "OK" if fpath.is_file() else "MISSING"
        if status == "MISSING":
            ok = False
        print(f"[{status}] {desc}: {fpath}")

    # Check admin email
    admin_email = os.environ.get("GAM_ADMIN_EMAIL", "")
    if not admin_email:
        cfg = GAM_CONFIG_DIR / "gam.cfg"
        if cfg.is_file():
            for line in cfg.read_text().splitlines():
                if line.strip().startswith("admin_email"):
                    admin_email = line.split("=", 1)[1].strip()
                    break
    if admin_email:
        print(f"\n[OK] Admin email: {admin_email}")
    else:
        print("\n[INFO] Admin email not set (set GAM_ADMIN_EMAIL or configure in gam.cfg)")

    # Connectivity test
    if gam and ok:
        print("\n--- Connectivity Test ---")
        result = run_gam(["info", "domain"])
        if result.returncode == 0:
            print("[OK] Domain info retrieved successfully")
            for line in result.stdout.strip().splitlines()[:5]:
                print(f"     {line}")
        else:
            print("[FAIL] Could not retrieve domain info")
            if result.stderr:
                print(f"     {result.stderr.strip()[:200]}")
    elif not ok:
        print("\n[SKIP] Connectivity test skipped (missing prerequisites)")

    status_data = {"gam_installed": gam is not None, "config_dir": str(GAM_CONFIG_DIR), "ready": ok}
    if getattr(args, "json_output", False):
        print_json(status_data)


# --- Users ---

def cmd_users(args):
    action = args.user_action

    if action == "list":
        gam_args = ["print", "users"]
        if getattr(args, "json_output", False):
            gam_args.extend(["fields", "primaryEmail,name,suspended,orgUnitPath,creationTime,lastLoginTime"])
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        if getattr(args, "json_output", False):
            print_json(gam_output_to_json(result.stdout))
        else:
            print(result.stdout)

    elif action == "info":
        gam_args = ["info", "user", args.email]
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        if getattr(args, "json_output", False):
            print_json(gam_output_to_json(result.stdout))
        else:
            print(result.stdout)

    elif action == "create":
        gam_args = ["create", "user", args.email]
        if args.firstname:
            gam_args.extend(["firstname", args.firstname])
        if args.lastname:
            gam_args.extend(["lastname", args.lastname])
        # Resolve password: --password value, or GWS_USER_PASSWORD env, or stdin if "-"
        password = args.password
        if password == "-":
            import getpass
            password = getpass.getpass("Enter password: ")
        elif not password:
            password = os.environ.get("GWS_USER_PASSWORD")
        if args.org:
            gam_args.extend(["org", args.org])
        if getattr(args, "dry_run", False):
            if password:
                gam_args.extend(["password", "****"])
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args, password=password)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout)

    elif action == "update":
        gam_args = ["update", "user", args.email]
        if args.suspended is not None:
            gam_args.extend(["suspended", args.suspended])
        if args.org:
            gam_args.extend(["org", args.org])
        # Resolve password: --password value, or stdin if "-"
        password = args.password
        if password == "-":
            import getpass
            password = getpass.getpass("Enter new password: ")
        if len(gam_args) == 3 and not password:
            print("ERROR: No update fields specified. Use --suspended, --org, or --password.", file=sys.stderr)
            sys.exit(1)
        if getattr(args, "dry_run", False):
            if password:
                gam_args.extend(["password", "****"])
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args, password=password)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout)

    elif action == "delete":
        if not check_confirm(args, f"Delete user {args.email}"):
            if getattr(args, "dry_run", False):
                print_dry_run(["delete", "user", args.email])
            return
        gam_args = ["delete", "user", args.email]
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout)


# --- Groups ---

def cmd_groups(args):
    action = args.group_action

    if action == "list":
        gam_args = ["print", "groups"]
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        if getattr(args, "json_output", False):
            print_json(gam_output_to_json(result.stdout))
        else:
            print(result.stdout)

    elif action == "info":
        gam_args = ["info", "group", args.email]
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        # Also fetch members
        members_result = run_gam(["print", "group-members", "group", args.email])
        if getattr(args, "json_output", False):
            group_data = gam_output_to_json(result.stdout)
            members_data = gam_output_to_json(members_result.stdout) if members_result.returncode == 0 else []
            print_json({"group": group_data, "members": members_data})
        else:
            print(result.stdout)
            if members_result.returncode == 0:
                print("\n--- Members ---")
                print(members_result.stdout)

    elif action == "create":
        gam_args = ["create", "group", args.email]
        if args.name:
            gam_args.extend(["name", args.name])
        if args.description:
            gam_args.extend(["description", args.description])
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout)

    elif action == "add-member":
        gam_args = ["update", "group", args.group, "add", args.role, args.user]
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout)

    elif action == "remove-member":
        gam_args = ["update", "group", args.group, "remove", args.user]
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout)


# --- Org Units ---

def cmd_orgs(args):
    action = args.org_action

    if action == "list":
        gam_args = ["print", "orgs"]
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        if getattr(args, "json_output", False):
            print_json(gam_output_to_json(result.stdout))
        else:
            print(result.stdout)

    elif action == "create":
        gam_args = ["create", "org", args.path]
        if args.description:
            gam_args.extend(["description", args.description])
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout)

    elif action == "info":
        gam_args = ["info", "org", args.path]
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        if getattr(args, "json_output", False):
            print_json(gam_output_to_json(result.stdout))
        else:
            print(result.stdout)


# --- Aliases ---

def cmd_aliases(args):
    action = args.alias_action

    if action == "list":
        if hasattr(args, "user") and args.user:
            gam_args = ["print", "aliases", "user", args.user]
        else:
            gam_args = ["print", "aliases"]
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        if getattr(args, "json_output", False):
            print_json(gam_output_to_json(result.stdout))
        else:
            print(result.stdout)

    elif action == "create":
        gam_args = ["create", "alias", args.alias, "user", args.target]
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout)

    elif action == "delete":
        if not check_confirm(args, f"Delete alias {args.alias}"):
            if getattr(args, "dry_run", False):
                print_dry_run(["delete", "alias", args.alias])
            return
        gam_args = ["delete", "alias", args.alias]
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout)


# --- Devices ---

def cmd_devices(args):
    action = args.device_action

    if action == "list":
        gam_args = ["print", "mobile"]
        if getattr(args, "dry_run", False):
            print_dry_run(gam_args)
            return
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        if getattr(args, "json_output", False):
            print_json(gam_output_to_json(result.stdout))
        else:
            print(result.stdout)

    elif action == "wipe":
        if not check_confirm(args, f"Remote wipe device {args.device_id}"):
            if getattr(args, "dry_run", False):
                print_dry_run(["update", "mobile", args.device_id, "action", "account_wipe"])
            return
        gam_args = ["update", "mobile", args.device_id, "action", "account_wipe"]
        result = run_gam(gam_args)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}", file=sys.stderr)
            sys.exit(1)
        print(result.stdout)


# --- Licenses ---

def cmd_licenses(args):
    gam_args = ["print", "licenses"]
    if getattr(args, "dry_run", False):
        print_dry_run(gam_args)
        return
    result = run_gam(gam_args)
    if result.returncode != 0:
        print(f"ERROR: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    if getattr(args, "json_output", False):
        print_json(gam_output_to_json(result.stdout))
    else:
        print(result.stdout)


# --- Raw passthrough ---

def cmd_raw(args):
    gam_args = args.gam_args
    if not gam_args:
        print("ERROR: No GAM arguments provided.", file=sys.stderr)
        sys.exit(1)
    print(f"[RAW] Executing: gam {' '.join(_redact_gam_args(gam_args))}")
    result = run_gam(gam_args, capture=False)
    sys.exit(result.returncode)


# --- Argument Parsing ---

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gws-admin",
        description="Google Workspace Admin — GAM7 wrapper with safety guardrails",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              gws-admin.py setup                                # First-time setup
              gws-admin.py status                               # Check install status
              gws-admin.py users list --json                    # List users as JSON
              gws-admin.py users create a@co.com --firstname A --lastname B --password P
              gws-admin.py users delete x@co.com --confirm      # Delete with confirmation
              gws-admin.py groups list                           # List all groups
              gws-admin.py raw info domain                      # Raw GAM passthrough
        """),
    )
    parser.add_argument("--json", dest="json_output", action="store_true", help="Output in JSON format")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be executed without running")

    subparsers = parser.add_subparsers(dest="command", help="Command category")

    # setup
    subparsers.add_parser("setup", help="First-time GAM install and configuration")

    # status
    subparsers.add_parser("status", help="Check GAM installation and auth status")

    # users
    users_parser = subparsers.add_parser("users", help="User management")
    users_sub = users_parser.add_subparsers(dest="user_action", help="User action")

    users_sub.add_parser("list", help="List all users")

    users_info = users_sub.add_parser("info", help="Get user details")
    users_info.add_argument("email", help="User email address")

    users_create = users_sub.add_parser("create", help="Create a new user")
    users_create.add_argument("email", help="User email address")
    users_create.add_argument("--firstname", required=True, help="First name")
    users_create.add_argument("--lastname", required=True, help="Last name")
    users_create.add_argument("--password", help="Initial password (use '-' for stdin prompt, or set GWS_USER_PASSWORD env var)")
    users_create.add_argument("--org", help="Org unit path (e.g., /Engineering)")

    users_update = users_sub.add_parser("update", help="Update user attributes")
    users_update.add_argument("email", help="User email address")
    users_update.add_argument("--suspended", choices=["on", "off"], help="Suspend or unsuspend user")
    users_update.add_argument("--org", help="Move to org unit path")
    users_update.add_argument("--password", help="Set new password (use '-' for stdin prompt)")

    users_delete = users_sub.add_parser("delete", help="Delete a user (requires --confirm)")
    users_delete.add_argument("email", help="User email address")
    users_delete.add_argument("--confirm", action="store_true", help="Confirm destructive operation")

    # groups
    groups_parser = subparsers.add_parser("groups", help="Group management")
    groups_sub = groups_parser.add_subparsers(dest="group_action", help="Group action")

    groups_sub.add_parser("list", help="List all groups")

    groups_info = groups_sub.add_parser("info", help="Get group details and members")
    groups_info.add_argument("email", help="Group email address")

    groups_create = groups_sub.add_parser("create", help="Create a new group")
    groups_create.add_argument("email", help="Group email address")
    groups_create.add_argument("--name", help="Group display name")
    groups_create.add_argument("--description", help="Group description")

    groups_add = groups_sub.add_parser("add-member", help="Add member to group")
    groups_add.add_argument("group", help="Group email address")
    groups_add.add_argument("user", help="User email to add")
    groups_add.add_argument("--role", default="member", choices=["member", "manager", "owner"], help="Member role")

    groups_remove = groups_sub.add_parser("remove-member", help="Remove member from group")
    groups_remove.add_argument("group", help="Group email address")
    groups_remove.add_argument("user", help="User email to remove")

    # orgs
    orgs_parser = subparsers.add_parser("orgs", help="Organizational unit management")
    orgs_sub = orgs_parser.add_subparsers(dest="org_action", help="Org action")

    orgs_sub.add_parser("list", help="List all org units")

    orgs_create = orgs_sub.add_parser("create", help="Create an org unit")
    orgs_create.add_argument("path", help="Org unit path (e.g., /Engineering/Frontend)")
    orgs_create.add_argument("--description", help="Org unit description")

    orgs_info = orgs_sub.add_parser("info", help="Get org unit details")
    orgs_info.add_argument("path", help="Org unit path")

    # aliases
    aliases_parser = subparsers.add_parser("aliases", help="Email alias management")
    aliases_sub = aliases_parser.add_subparsers(dest="alias_action", help="Alias action")

    aliases_list = aliases_sub.add_parser("list", help="List aliases")
    aliases_list.add_argument("user", nargs="?", help="Filter by user email (optional)")

    aliases_create = aliases_sub.add_parser("create", help="Create an alias")
    aliases_create.add_argument("alias", help="Alias email address")
    aliases_create.add_argument("--target", required=True, help="Target user email")

    aliases_delete = aliases_sub.add_parser("delete", help="Delete an alias (requires --confirm)")
    aliases_delete.add_argument("alias", help="Alias email address")
    aliases_delete.add_argument("--confirm", action="store_true", help="Confirm destructive operation")

    # devices
    devices_parser = subparsers.add_parser("devices", help="Mobile device management")
    devices_sub = devices_parser.add_subparsers(dest="device_action", help="Device action")

    devices_sub.add_parser("list", help="List mobile devices")

    devices_wipe = devices_sub.add_parser("wipe", help="Remote wipe device (requires --confirm)")
    devices_wipe.add_argument("device_id", help="Device resource ID")
    devices_wipe.add_argument("--confirm", action="store_true", help="Confirm destructive operation")

    # licenses
    subparsers.add_parser("licenses", help="License management")

    # raw
    raw_parser = subparsers.add_parser("raw", help="Pass-through to raw GAM command")
    raw_parser.add_argument("gam_args", nargs=argparse.REMAINDER, help="Arguments to pass to GAM")

    return parser


def main():
    # Extract global flags from anywhere in argv so they work in any position
    # (argparse only sees top-level flags before the subcommand)
    argv = sys.argv[1:]
    json_output = False
    dry_run = False
    cleaned = []
    for arg in argv:
        if arg == "--json":
            json_output = True
        elif arg == "--dry-run":
            dry_run = True
        else:
            cleaned.append(arg)

    parser = build_parser()
    args = parser.parse_args(cleaned)
    args.json_output = json_output
    args.dry_run = dry_run

    if not args.command:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "setup": cmd_setup,
        "status": cmd_status,
        "users": cmd_users,
        "groups": cmd_groups,
        "orgs": cmd_orgs,
        "aliases": cmd_aliases,
        "devices": cmd_devices,
        "licenses": cmd_licenses,
        "raw": cmd_raw,
    }

    handler = dispatch.get(args.command)
    if handler:
        # Check for missing subcommand on commands that require one
        sub_action_key = {
            "users": "user_action",
            "groups": "group_action",
            "orgs": "org_action",
            "aliases": "alias_action",
            "devices": "device_action",
        }
        if args.command in sub_action_key:
            if not getattr(args, sub_action_key[args.command], None):
                parser.parse_args([args.command, "--help"])
                sys.exit(1)
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
