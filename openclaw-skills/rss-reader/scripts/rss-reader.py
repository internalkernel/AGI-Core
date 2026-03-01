# /// script
# requires-python = ">=3.10"
# dependencies = ["feedparser", "python-dateutil", "requests"]
# ///
"""RSS feed reader for agent consumption. JSON output, deduplication via state file."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
from dateutil import parser as dateparser


def get_data_dir() -> Path:
    workspace = os.environ.get("OPENCLAW_WORKSPACE")
    if workspace:
        d = Path(workspace) / "cache" / "rss"
    else:
        d = Path.home() / ".openclaw" / "skills" / "rss-reader" / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_json(path: Path) -> dict | list:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def stderr(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


import contextlib
import socket as _socket


def _validate_feed_url(url: str) -> str | None:
    """Validate feed URL and return pinned IP. Must be http/https, no internal/private targets."""
    from urllib.parse import urlparse
    import re
    import ipaddress
    import socket
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        stderr(f"Error: Invalid URL scheme '{parsed.scheme}'. Only http and https are allowed.")
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
    # DNS resolution check: only allow globally-routable IPs (fail closed)
    # Returns first valid IP for connect-time pinning
    first_ip = None
    try:
        for info in socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM):
            addr = ipaddress.ip_address(info[4][0])
            if not addr.is_global:
                stderr(f"Error: URL resolves to non-global IP ({addr}): {url}")
                sys.exit(1)
            if first_ip is None:
                first_ip = str(addr)
    except socket.gaierror as e:
        stderr(f"Error: DNS resolution failed for {host}: {e}")
        sys.exit(1)
    return first_ip


@contextlib.contextmanager
def _pinned_dns(hostname: str, pinned_ip: str):
    """Temporarily pin DNS resolution to eliminate DNS-rebinding TOCTOU."""
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


# --- commands ---


def cmd_subscribe(args):
    data_dir = get_data_dir()
    feeds_path = data_dir / "feeds.json"
    feeds = load_json(feeds_path)
    if not isinstance(feeds, dict):
        feeds = {}

    url = args.url
    _validate_feed_url(url)
    if url in feeds:
        stderr(f"Already subscribed to {url}")
        sys.exit(1)

    feeds[url] = {"name": args.name or url, "added": datetime.now(timezone.utc).isoformat()}
    save_json(feeds_path, feeds)
    stderr(f"Subscribed to {feeds[url]['name']} ({url})")


def cmd_unsubscribe(args):
    data_dir = get_data_dir()
    feeds_path = data_dir / "feeds.json"
    feeds = load_json(feeds_path)
    if not isinstance(feeds, dict):
        feeds = {}

    url = args.url
    if url not in feeds:
        stderr(f"Not subscribed to {url}")
        sys.exit(1)

    name = feeds[url]["name"]
    del feeds[url]
    save_json(feeds_path, feeds)

    # Clean up state for this feed
    state_path = data_dir / "state.json"
    state = load_json(state_path)
    if isinstance(state, dict) and url in state:
        del state[url]
        save_json(state_path, state)

    stderr(f"Unsubscribed from {name} ({url})")


def cmd_list(args):
    data_dir = get_data_dir()
    feeds_path = data_dir / "feeds.json"
    feeds = load_json(feeds_path)
    if not isinstance(feeds, dict):
        feeds = {}

    result = []
    for url, info in feeds.items():
        result.append({"url": url, "name": info.get("name", url), "added": info.get("added")})
    print(json.dumps(result, indent=2))


def parse_entry_date(entry) -> str | None:
    for field in ("published", "updated", "created"):
        val = entry.get(field)
        if val:
            try:
                dt = dateparser.parse(val)
                if dt:
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.isoformat()
            except (ValueError, OverflowError):
                pass
    # fallback to struct time fields
    for field in ("published_parsed", "updated_parsed", "created_parsed"):
        val = entry.get(field)
        if val:
            try:
                dt = datetime(*val[:6], tzinfo=timezone.utc)
                return dt.isoformat()
            except (ValueError, TypeError):
                pass
    return None


MAX_ENTRY_ID_LEN = 512
MAX_SEEN_PER_FEED = 5000


def entry_id(entry) -> str:
    eid = entry.get("id") or entry.get("link") or entry.get("title", "")
    # Truncate overly long IDs to prevent state file bloat
    return eid[:MAX_ENTRY_ID_LEN] if len(eid) > MAX_ENTRY_ID_LEN else eid


def truncate(text: str, length: int = 300) -> str:
    if not text:
        return ""
    text = text.strip()
    if len(text) <= length:
        return text
    return text[:length].rstrip() + "..."


def cmd_fetch(args):
    data_dir = get_data_dir()
    feeds_path = data_dir / "feeds.json"
    state_path = data_dir / "state.json"

    feeds = load_json(feeds_path)
    if not isinstance(feeds, dict):
        feeds = {}
    state = load_json(state_path)
    if not isinstance(state, dict):
        state = {}

    if not feeds:
        stderr("No feeds subscribed. Use 'subscribe' first.")
        print("[]")
        return

    # Filter to single feed if requested
    if args.feed:
        if args.feed not in feeds:
            stderr(f"Not subscribed to {args.feed}")
            print("[]")
            return
        target_feeds = {args.feed: feeds[args.feed]}
    else:
        target_feeds = feeds

    show_all = args.all
    limit = args.limit
    results = []

    for url, info in target_feeds.items():
        feed_name = info.get("name", url)
        seen = set(state.get(url, []))

        stderr(f"Fetching {feed_name}...")
        # Re-validate URL on every fetch and get pinned IP (prevents DNS rebinding)
        try:
            pinned_ip = _validate_feed_url(url)
        except SystemExit:
            stderr(f"  Skipping {feed_name}: URL validation failed")
            continue
        from urllib.parse import urlparse as _urlparse
        _host = _urlparse(url).hostname
        # Fetch content ourselves with connect-time IP pinning to prevent DNS-rebinding TOCTOU
        # Stream with 2MB cap to prevent memory exhaustion from malicious feeds
        MAX_FEED_SIZE = 2 * 1024 * 1024
        try:
            with _pinned_dns(_host, pinned_ip):
                resp = requests.get(url, timeout=30, allow_redirects=False, stream=True)
            resp.raise_for_status()
            chunks = []
            total = 0
            for chunk in resp.iter_content(chunk_size=8192):
                total += len(chunk)
                if total > MAX_FEED_SIZE:
                    resp.close()
                    stderr(f"  Skipping {feed_name}: response exceeds {MAX_FEED_SIZE} bytes")
                    break
                chunks.append(chunk)
            else:
                # Only parse if we didn't break out of the loop
                feed_content = b"".join(chunks)
                parsed = feedparser.parse(feed_content)
            if total > MAX_FEED_SIZE:
                continue
        except requests.RequestException as e:
            stderr(f"  Error fetching {feed_name}: {e}")
            continue

        if parsed.bozo and not parsed.entries:
            stderr(f"  Error fetching {feed_name}: {parsed.bozo_exception}")
            continue

        new_seen = set(seen)
        for entry in parsed.entries:
            eid = entry_id(entry)
            if not show_all and eid in seen:
                continue

            new_seen.add(eid)

            # Extract summary: prefer summary, fall back to content
            summary = ""
            if entry.get("summary"):
                summary = entry["summary"]
            elif entry.get("content"):
                for c in entry["content"]:
                    if c.get("value"):
                        summary = c["value"]
                        break

            # Strip HTML tags for clean text
            import re
            summary = re.sub(r"<[^>]+>", "", summary)

            results.append({
                "feed": feed_name,
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "published": parse_entry_date(entry),
                "summary": truncate(summary),
            })

        # Update state (cap per-feed to prevent unbounded growth)
        seen_list = list(new_seen)
        if len(seen_list) > MAX_SEEN_PER_FEED:
            seen_list = seen_list[-MAX_SEEN_PER_FEED:]
        state[url] = seen_list

    # Sort by published date descending (newest first), None dates last
    results.sort(key=lambda x: x.get("published") or "", reverse=True)

    if limit and limit > 0:
        results = results[:limit]

    # Save state after successful fetch
    save_json(state_path, state)

    print(json.dumps(results, indent=2))
    stderr(f"{len(results)} item(s)")


def main():
    parser = argparse.ArgumentParser(description="RSS feed reader for agents")
    sub = parser.add_subparsers(dest="command", required=True)

    # subscribe
    p_sub = sub.add_parser("subscribe", help="Subscribe to an RSS feed")
    p_sub.add_argument("url", help="Feed URL")
    p_sub.add_argument("--name", help="Human-readable feed name")

    # unsubscribe
    p_unsub = sub.add_parser("unsubscribe", help="Unsubscribe from a feed")
    p_unsub.add_argument("url", help="Feed URL")

    # list
    sub.add_parser("list", help="List subscribed feeds")

    # fetch
    p_fetch = sub.add_parser("fetch", help="Fetch new items from feeds")
    p_fetch.add_argument("--all", action="store_true", help="Show all items, not just new ones")
    p_fetch.add_argument("--feed", help="Fetch from a single feed URL only")
    p_fetch.add_argument("--limit", type=int, default=0, help="Max items to return (0 = unlimited)")

    args = parser.parse_args()

    if args.command == "subscribe":
        cmd_subscribe(args)
    elif args.command == "unsubscribe":
        cmd_unsubscribe(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "fetch":
        cmd_fetch(args)


if __name__ == "__main__":
    main()
