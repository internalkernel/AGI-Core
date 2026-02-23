# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""WordPress REST API CLI for agents. Manage posts, pages, media, and plugins via WP REST API.

Usage:
    uv run wordpress.py <command> [options]

Uses Application Passwords (WP 5.6+) for authentication.
"""

import argparse
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests


def get_data_dir() -> Path:
    workspace = os.environ.get("OPENCLAW_WORKSPACE")
    if workspace:
        d = Path(workspace) / "cache" / "wordpress"
    else:
        d = Path.home() / ".openclaw" / "skills" / "wordpress" / "data"
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
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600


def get_site(alias: str) -> dict:
    sites = load_sites()
    if alias not in sites:
        stderr(f"Site '{alias}' not found. Use 'site list' to see registered sites.")
        sys.exit(1)
    return sites[alias]


def stderr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def _resolve_and_validate(hostname: str) -> str:
    """Resolve hostname, validate all IPs are global, return first valid IP for pinning."""
    import ipaddress
    import socket
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror as e:
        stderr(f"Error: DNS resolution failed for {hostname}: {e}")
        sys.exit(1)
    first_ip = None
    for info in results:
        addr = ipaddress.ip_address(info[4][0])
        if not addr.is_global:
            stderr(f"Error: URL resolves to non-global IP ({addr}): {hostname}")
            sys.exit(1)
        if first_ip is None:
            first_ip = str(addr)
    if first_ip is None:
        stderr(f"Error: No addresses resolved for {hostname}")
        sys.exit(1)
    return first_ip


def _validate_site_url(url: str) -> str | None:
    """Validate site URL and return pinned IP. Must be https, reject internal/private targets."""
    from urllib.parse import urlparse
    import re
    parsed = urlparse(url)
    if parsed.scheme != "https":
        stderr(f"Error: Only https URLs are allowed (got '{parsed.scheme}'). WordPress app passwords must not be sent over plaintext HTTP.")
        sys.exit(1)
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"):
        stderr(f"Error: Loopback URLs are not allowed: {url}")
        sys.exit(1)
    if re.match(r"^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.|127\.)", host):
        stderr(f"Error: Private/internal network URLs are not allowed: {url}")
        sys.exit(1)
    if host.endswith((".internal", ".local", ".localhost")):
        stderr(f"Error: Internal domain URLs are not allowed: {url}")
        sys.exit(1)
    return _resolve_and_validate(host)


def mask_password(pw: str) -> str:
    if not pw or len(pw) < 8:
        return "****"
    return pw[:4] + " " + "*" * (len(pw) - 5)


# --- API core ---


import contextlib
import socket as _socket

@contextlib.contextmanager
def _pinned_dns(hostname: str, pinned_ip: str):
    """Temporarily pin DNS resolution for hostname to the pre-validated IP.
    Eliminates DNS-rebinding TOCTOU: the TCP connection is forced to use the same
    IP that passed validation, regardless of what DNS returns at connect time.
    Safe for single-threaded CLI use (not thread-safe)."""
    orig = _socket.getaddrinfo
    def patched(host, port, *args, **kwargs):
        if isinstance(host, str) and host.lower() == hostname.lower():
            return orig(pinned_ip, port, *args, **kwargs)
        return orig(host, port, *args, **kwargs)
    _socket.getaddrinfo = patched
    try:
        yield
    finally:
        _socket.getaddrinfo = orig


def wp_request(site: dict, method: str, endpoint: str,
               params: dict | None = None, json_data: dict | None = None,
               files: dict | None = None) -> dict | list:
    """Make an authenticated request to the WordPress REST API."""
    url = site["url"].rstrip("/") + "/wp-json/" + endpoint.lstrip("/")
    # Validate URL and get pinned IP (eliminates DNS-rebinding TOCTOU)
    pinned_ip = _validate_site_url(url)
    auth = (site["username"], site["app_password"])

    from urllib.parse import urlparse
    hostname = urlparse(url).hostname

    kwargs = {"auth": auth, "timeout": 30, "allow_redirects": False}
    if params:
        kwargs["params"] = params
    if json_data:
        kwargs["json"] = json_data
    if files:
        kwargs["files"] = files

    try:
        with _pinned_dns(hostname, pinned_ip):
            resp = requests.request(method, url, **kwargs)
    except requests.RequestException as e:
        stderr(f"Request failed: {e}")
        sys.exit(1)

    if resp.status_code == 204:
        return {"ok": True, "status": 204}

    try:
        data = resp.json()
    except ValueError:
        stderr(f"Non-JSON response ({resp.status_code}): {resp.text[:200]}")
        sys.exit(1)

    if resp.status_code >= 400:
        code = data.get("code", "unknown")
        message = data.get("message", resp.text[:200])
        stderr(f"API error {resp.status_code}: [{code}] {message}")
        sys.exit(1)

    return data


# --- Site management ---


def cmd_site_add(args):
    sites = load_sites()
    if args.alias in sites:
        stderr(f"Site '{args.alias}' already exists. Remove it first.")
        sys.exit(1)

    _validate_site_url(args.url)
    if hasattr(args, "password") and args.password:
        stderr("Warning: --password is visible in process listings. Prefer setting WP_APP_PASSWORD env var.")
    sites[args.alias] = {
        "name": args.name or args.alias,
        "url": args.url.rstrip("/"),
        "username": args.user,
        "app_password": args.password,
        "added": datetime.now(timezone.utc).isoformat(),
    }
    save_sites(sites)
    stderr(f"Added site '{args.alias}' ({args.url})")


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
            "url": info.get("url"),
            "username": info.get("username"),
            "app_password": mask_password(info.get("app_password", "")),
            "added": info.get("added"),
        })
    print(json.dumps(result, indent=2))


# --- CRUD helpers for posts/pages ---


def cmd_content_list(args, endpoint: str):
    site = get_site(args.alias)
    params = {"per_page": args.limit}
    if args.status and args.status != "all":
        params["status"] = args.status
    elif args.status == "all":
        params["status"] = "publish,draft,pending,private,future"
    if hasattr(args, "search") and args.search:
        params["search"] = args.search
    data = wp_request(site, "GET", f"wp/v2/{endpoint}", params=params)
    result = []
    for item in data:
        result.append({
            "id": item["id"],
            "title": item.get("title", {}).get("rendered", ""),
            "status": item.get("status"),
            "date": item.get("date"),
            "link": item.get("link"),
            "slug": item.get("slug"),
        })
    print(json.dumps(result, indent=2))


def cmd_content_get(args, endpoint: str):
    site = get_site(args.alias)
    data = wp_request(site, "GET", f"wp/v2/{endpoint}/{args.id}")
    result = {
        "id": data["id"],
        "title": data.get("title", {}).get("rendered", ""),
        "content": data.get("content", {}).get("rendered", ""),
        "excerpt": data.get("excerpt", {}).get("rendered", ""),
        "status": data.get("status"),
        "date": data.get("date"),
        "modified": data.get("modified"),
        "link": data.get("link"),
        "slug": data.get("slug"),
        "author": data.get("author"),
        "categories": data.get("categories", []),
        "tags": data.get("tags", []),
    }
    print(json.dumps(result, indent=2))


def cmd_content_create(args, endpoint: str):
    site = get_site(args.alias)
    body = {"title": args.title, "content": args.content, "status": args.status}
    if hasattr(args, "categories") and args.categories:
        body["categories"] = [int(c) for c in args.categories.split(",")]
    data = wp_request(site, "POST", f"wp/v2/{endpoint}", json_data=body)
    print(json.dumps({
        "ok": True,
        "id": data["id"],
        "link": data.get("link"),
        "status": data.get("status"),
    }, indent=2))
    stderr(f"Created {endpoint[:-1]} #{data['id']}")


def cmd_content_update(args, endpoint: str):
    site = get_site(args.alias)
    body = {}
    if args.title:
        body["title"] = args.title
    if args.content:
        body["content"] = args.content
    if args.status:
        body["status"] = args.status
    if not body:
        stderr("Nothing to update. Provide --title, --content, or --status.")
        sys.exit(1)
    data = wp_request(site, "POST", f"wp/v2/{endpoint}/{args.id}", json_data=body)
    print(json.dumps({
        "ok": True,
        "id": data["id"],
        "link": data.get("link"),
        "status": data.get("status"),
    }, indent=2))
    stderr(f"Updated {endpoint[:-1]} #{data['id']}")


def cmd_content_delete(args, endpoint: str):
    site = get_site(args.alias)
    wp_request(site, "DELETE", f"wp/v2/{endpoint}/{args.id}", params={"force": "true"})
    print(json.dumps({"ok": True, "deleted": args.id}, indent=2))
    stderr(f"Deleted {endpoint[:-1]} #{args.id}")


# --- Media ---


def cmd_media_list(args):
    site = get_site(args.alias)
    params = {"per_page": args.limit}
    if args.type:
        params["media_type"] = args.type
    data = wp_request(site, "GET", "wp/v2/media", params=params)
    result = []
    for item in data:
        result.append({
            "id": item["id"],
            "title": item.get("title", {}).get("rendered", ""),
            "media_type": item.get("media_type"),
            "mime_type": item.get("mime_type"),
            "source_url": item.get("source_url"),
            "date": item.get("date"),
        })
    print(json.dumps(result, indent=2))


def _safe_input_path(filepath: str) -> Path:
    """Ensure input file path doesn't escape the current working directory."""
    resolved = Path(filepath).resolve()
    cwd = Path.cwd().resolve()
    if not (str(resolved).startswith(str(cwd) + os.sep) or resolved == cwd):
        stderr(f"Error: File path '{filepath}' is outside the current working directory.")
        sys.exit(1)
    return resolved


def cmd_media_upload(args):
    site = get_site(args.alias)
    filepath = _safe_input_path(args.file)
    if not filepath.exists():
        stderr(f"File not found: {args.file}")
        sys.exit(1)

    import mimetypes
    mime = mimetypes.guess_type(str(filepath))[0] or "application/octet-stream"

    url = site["url"].rstrip("/") + "/wp-json/wp/v2/media"
    # Re-validate URL before upload and get pinned IP (prevents DNS rebinding TOCTOU)
    pinned_ip = _validate_site_url(url)
    auth = (site["username"], site["app_password"])
    headers = {
        "Content-Disposition": f'attachment; filename="{filepath.name}"',
        "Content-Type": mime,
    }

    from urllib.parse import urlparse
    hostname = urlparse(url).hostname

    try:
        with open(filepath, "rb") as f:
            with _pinned_dns(hostname, pinned_ip):
                resp = requests.post(url, auth=auth, headers=headers, data=f, timeout=120, allow_redirects=False)
    except requests.RequestException as e:
        stderr(f"Upload failed: {e}")
        sys.exit(1)

    if resp.status_code >= 400:
        try:
            err = resp.json()
            stderr(f"Upload error {resp.status_code}: {err.get('message', resp.text[:200])}")
        except ValueError:
            stderr(f"Upload error {resp.status_code}: {resp.text[:200]}")
        sys.exit(1)

    data = resp.json()

    # Update title/alt if provided
    update_body = {}
    if args.title:
        update_body["title"] = args.title
    if args.alt:
        update_body["alt_text"] = args.alt
    if update_body:
        wp_request(site, "POST", f"wp/v2/media/{data['id']}", json_data=update_body)

    print(json.dumps({
        "ok": True,
        "id": data["id"],
        "source_url": data.get("source_url"),
        "media_type": data.get("media_type"),
    }, indent=2))
    stderr(f"Uploaded media #{data['id']}")


def cmd_media_get(args):
    site = get_site(args.alias)
    data = wp_request(site, "GET", f"wp/v2/media/{args.id}")
    result = {
        "id": data["id"],
        "title": data.get("title", {}).get("rendered", ""),
        "media_type": data.get("media_type"),
        "mime_type": data.get("mime_type"),
        "source_url": data.get("source_url"),
        "alt_text": data.get("alt_text", ""),
        "date": data.get("date"),
        "media_details": data.get("media_details", {}),
    }
    print(json.dumps(result, indent=2))


def cmd_media_delete(args):
    site = get_site(args.alias)
    wp_request(site, "DELETE", f"wp/v2/media/{args.id}", params={"force": "true"})
    print(json.dumps({"ok": True, "deleted": args.id}, indent=2))
    stderr(f"Deleted media #{args.id}")


# --- Taxonomies ---


def cmd_categories_list(args):
    site = get_site(args.alias)
    data = wp_request(site, "GET", "wp/v2/categories", params={"per_page": 100})
    result = [{"id": c["id"], "name": c["name"], "slug": c["slug"],
               "count": c.get("count", 0), "parent": c.get("parent", 0)} for c in data]
    print(json.dumps(result, indent=2))


def cmd_tags_list(args):
    site = get_site(args.alias)
    data = wp_request(site, "GET", "wp/v2/tags", params={"per_page": 100})
    result = [{"id": t["id"], "name": t["name"], "slug": t["slug"],
               "count": t.get("count", 0)} for t in data]
    print(json.dumps(result, indent=2))


# --- Gravity Forms ---


def cmd_gf_forms(args):
    site = get_site(args.alias)
    data = wp_request(site, "GET", "gf/v2/forms")
    result = []
    for form in data:
        result.append({
            "id": form.get("id"),
            "title": form.get("title"),
            "entries": form.get("entries"),
            "is_active": form.get("is_active"),
        })
    print(json.dumps(result, indent=2))


def cmd_gf_entries(args):
    site = get_site(args.alias)
    params = {"paging[page_size]": args.limit}
    data = wp_request(site, "GET", f"gf/v2/forms/{args.form_id}/entries", params=params)
    entries = data.get("entries", data) if isinstance(data, dict) else data
    print(json.dumps(entries, indent=2))


def cmd_gf_entry(args):
    site = get_site(args.alias)
    data = wp_request(site, "GET", f"gf/v2/entries/{args.entry_id}")
    print(json.dumps(data, indent=2))


# --- Redirection ---


def cmd_redirects_list(args):
    site = get_site(args.alias)
    params = {"per_page": args.limit}
    data = wp_request(site, "GET", "redirection/v1/redirect", params=params)
    items = data.get("items", data) if isinstance(data, dict) else data
    result = []
    for r in items:
        result.append({
            "id": r.get("id"),
            "url": r.get("url"),
            "action_data": r.get("action_data", {}).get("url", r.get("action_data")),
            "action_type": r.get("action_type"),
            "action_code": r.get("action_code"),
            "hits": r.get("hits", 0),
            "enabled": r.get("enabled", True),
        })
    print(json.dumps(result, indent=2))


def cmd_redirects_create(args):
    site = get_site(args.alias)
    body = {
        "url": args.source,
        "action_data": {"url": args.target},
        "action_type": "url",
        "action_code": args.type,
        "match_type": "url",
        "group_id": 1,
    }
    data = wp_request(site, "POST", "redirection/v1/redirect", json_data=body)
    print(json.dumps({"ok": True, "id": data.get("id"), "url": data.get("url")}, indent=2))
    stderr(f"Created redirect: {args.source} -> {args.target} ({args.type})")


def cmd_redirects_delete(args):
    site = get_site(args.alias)
    wp_request(site, "DELETE", f"redirection/v1/redirect/{args.id}")
    print(json.dumps({"ok": True, "deleted": args.id}, indent=2))
    stderr(f"Deleted redirect #{args.id}")


# --- SEOPress ---


def cmd_seo_get(args):
    site = get_site(args.alias)
    data = wp_request(site, "GET", f"seopress/v1/posts/{args.post_id}/metadata")
    print(json.dumps(data, indent=2))


def cmd_seo_update(args):
    site = get_site(args.alias)
    body = {}
    if args.title:
        body["_seopress_titles_title"] = args.title
    if args.description:
        body["_seopress_titles_desc"] = args.description
    if not body:
        stderr("Nothing to update. Provide --title and/or --description.")
        sys.exit(1)
    data = wp_request(site, "PUT", f"seopress/v1/posts/{args.post_id}/metadata", json_data=body)
    print(json.dumps({"ok": True, "post_id": args.post_id}, indent=2))
    stderr(f"Updated SEO metadata for post #{args.post_id}")


# --- Argument parser ---


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WordPress REST API CLI for agents")
    sub = parser.add_subparsers(dest="command", required=True)

    # --- site ---
    site_parser = sub.add_parser("site", help="Manage registered WordPress sites")
    site_sub = site_parser.add_subparsers(dest="site_action", required=True)

    p = site_sub.add_parser("add", help="Register a WordPress site")
    p.add_argument("alias", help="Short alias for the site (e.g. 'prod')")
    p.add_argument("--url", required=True, help="Site URL (e.g. https://example.com)")
    p.add_argument("--user", required=True, help="WordPress username")
    p.add_argument("--password", required=True, help="Application password")
    p.add_argument("--name", help="Human-readable label")

    p = site_sub.add_parser("remove", help="Remove a registered site")
    p.add_argument("alias", help="Site alias")

    site_sub.add_parser("list", help="List registered sites")

    # --- posts ---
    posts_parser = sub.add_parser("posts", help="Manage posts")
    posts_parser.add_argument("alias", help="Site alias")
    posts_sub = posts_parser.add_subparsers(dest="posts_action", required=True)

    p = posts_sub.add_parser("list", help="List posts")
    p.add_argument("--status", default="publish", help="Filter by status (draft|publish|all)")
    p.add_argument("--limit", type=int, default=10, help="Number of posts")
    p.add_argument("--search", help="Search query")

    p = posts_sub.add_parser("get", help="Get a single post")
    p.add_argument("id", type=int, help="Post ID")

    p = posts_sub.add_parser("create", help="Create a new post")
    p.add_argument("--title", required=True, help="Post title")
    p.add_argument("--content", required=True, help="Post content (HTML)")
    p.add_argument("--status", default="draft", help="Post status (draft|publish)")
    p.add_argument("--categories", help="Comma-separated category IDs")

    p = posts_sub.add_parser("update", help="Update a post")
    p.add_argument("id", type=int, help="Post ID")
    p.add_argument("--title", help="New title")
    p.add_argument("--content", help="New content")
    p.add_argument("--status", help="New status")

    p = posts_sub.add_parser("delete", help="Delete a post")
    p.add_argument("id", type=int, help="Post ID")

    # --- pages ---
    pages_parser = sub.add_parser("pages", help="Manage pages")
    pages_parser.add_argument("alias", help="Site alias")
    pages_sub = pages_parser.add_subparsers(dest="pages_action", required=True)

    p = pages_sub.add_parser("list", help="List pages")
    p.add_argument("--status", default="publish", help="Filter by status")
    p.add_argument("--limit", type=int, default=10, help="Number of pages")
    p.add_argument("--search", help="Search query")

    p = pages_sub.add_parser("get", help="Get a single page")
    p.add_argument("id", type=int, help="Page ID")

    p = pages_sub.add_parser("create", help="Create a new page")
    p.add_argument("--title", required=True, help="Page title")
    p.add_argument("--content", required=True, help="Page content (HTML)")
    p.add_argument("--status", default="draft", help="Page status")

    p = pages_sub.add_parser("update", help="Update a page")
    p.add_argument("id", type=int, help="Page ID")
    p.add_argument("--title", help="New title")
    p.add_argument("--content", help="New content")
    p.add_argument("--status", help="New status")

    p = pages_sub.add_parser("delete", help="Delete a page")
    p.add_argument("id", type=int, help="Page ID")

    # --- media ---
    media_parser = sub.add_parser("media", help="Manage media")
    media_parser.add_argument("alias", help="Site alias")
    media_sub = media_parser.add_subparsers(dest="media_action", required=True)

    p = media_sub.add_parser("list", help="List media items")
    p.add_argument("--limit", type=int, default=10, help="Number of items")
    p.add_argument("--type", help="Filter by type (image|video)")

    p = media_sub.add_parser("upload", help="Upload a file")
    p.add_argument("file", help="Path to file")
    p.add_argument("--title", help="Media title")
    p.add_argument("--alt", help="Alt text")

    p = media_sub.add_parser("get", help="Get media details")
    p.add_argument("id", type=int, help="Media ID")

    p = media_sub.add_parser("delete", help="Delete media")
    p.add_argument("id", type=int, help="Media ID")

    # --- categories ---
    cat_parser = sub.add_parser("categories", help="List categories")
    cat_parser.add_argument("alias", help="Site alias")
    cat_sub = cat_parser.add_subparsers(dest="cat_action")
    cat_sub.add_parser("list", help="List all categories")

    # --- tags ---
    tag_parser = sub.add_parser("tags", help="List tags")
    tag_parser.add_argument("alias", help="Site alias")
    tag_sub = tag_parser.add_subparsers(dest="tag_action")
    tag_sub.add_parser("list", help="List all tags")

    # --- gf (Gravity Forms) ---
    gf_parser = sub.add_parser("gf", help="Gravity Forms")
    gf_parser.add_argument("alias", help="Site alias")
    gf_sub = gf_parser.add_subparsers(dest="gf_action", required=True)

    gf_sub.add_parser("forms", help="List forms")

    p = gf_sub.add_parser("entries", help="List entries for a form")
    p.add_argument("form_id", type=int, help="Form ID")
    p.add_argument("--limit", type=int, default=20, help="Number of entries")

    p = gf_sub.add_parser("entry", help="Get a single entry")
    p.add_argument("entry_id", type=int, help="Entry ID")

    # --- redirects ---
    redir_parser = sub.add_parser("redirects", help="Redirection plugin")
    redir_parser.add_argument("alias", help="Site alias")
    redir_sub = redir_parser.add_subparsers(dest="redir_action", required=True)

    p = redir_sub.add_parser("list", help="List redirects")
    p.add_argument("--limit", type=int, default=25, help="Number of results")

    p = redir_sub.add_parser("create", help="Create a redirect")
    p.add_argument("--source", required=True, help="Source URL path")
    p.add_argument("--target", required=True, help="Target URL")
    p.add_argument("--type", type=int, default=301, help="Redirect type (301|302)")

    p = redir_sub.add_parser("delete", help="Delete a redirect")
    p.add_argument("id", type=int, help="Redirect ID")

    # --- seo (SEOPress) ---
    seo_parser = sub.add_parser("seo", help="SEOPress metadata")
    seo_parser.add_argument("alias", help="Site alias")
    seo_sub = seo_parser.add_subparsers(dest="seo_action", required=True)

    p = seo_sub.add_parser("get", help="Get SEO metadata for a post")
    p.add_argument("post_id", type=int, help="Post ID")

    p = seo_sub.add_parser("update", help="Update SEO metadata")
    p.add_argument("post_id", type=int, help="Post ID")
    p.add_argument("--title", help="SEO title")
    p.add_argument("--description", help="SEO description")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # --- dispatch ---
    cmd = args.command

    if cmd == "site":
        if args.site_action == "add":
            cmd_site_add(args)
        elif args.site_action == "remove":
            cmd_site_remove(args)
        elif args.site_action == "list":
            cmd_site_list(args)

    elif cmd == "posts":
        a = args.posts_action
        if a == "list":
            cmd_content_list(args, "posts")
        elif a == "get":
            cmd_content_get(args, "posts")
        elif a == "create":
            cmd_content_create(args, "posts")
        elif a == "update":
            cmd_content_update(args, "posts")
        elif a == "delete":
            cmd_content_delete(args, "posts")

    elif cmd == "pages":
        a = args.pages_action
        if a == "list":
            cmd_content_list(args, "pages")
        elif a == "get":
            cmd_content_get(args, "pages")
        elif a == "create":
            cmd_content_create(args, "pages")
        elif a == "update":
            cmd_content_update(args, "pages")
        elif a == "delete":
            cmd_content_delete(args, "pages")

    elif cmd == "media":
        a = args.media_action
        if a == "list":
            cmd_media_list(args)
        elif a == "upload":
            cmd_media_upload(args)
        elif a == "get":
            cmd_media_get(args)
        elif a == "delete":
            cmd_media_delete(args)

    elif cmd == "categories":
        cmd_categories_list(args)

    elif cmd == "tags":
        cmd_tags_list(args)

    elif cmd == "gf":
        a = args.gf_action
        if a == "forms":
            cmd_gf_forms(args)
        elif a == "entries":
            cmd_gf_entries(args)
        elif a == "entry":
            cmd_gf_entry(args)

    elif cmd == "redirects":
        a = args.redir_action
        if a == "list":
            cmd_redirects_list(args)
        elif a == "create":
            cmd_redirects_create(args)
        elif a == "delete":
            cmd_redirects_delete(args)

    elif cmd == "seo":
        a = args.seo_action
        if a == "get":
            cmd_seo_get(args)
        elif a == "update":
            cmd_seo_update(args)


if __name__ == "__main__":
    main()
