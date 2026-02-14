---
name: rss-reader
description: Subscribe to RSS feeds and fetch new items with deduplication. Per-workspace data dirs, JSON output for agent consumption.
---

# RSS Reader

Subscribe to RSS/Atom feeds and fetch new items. Tracks seen entries for deduplication so agents only process new content each run. All output is JSON to stdout; status/errors to stderr.

## Usage

```bash
RSS="uv run ~/.openclaw/skills/rss-reader/scripts/rss-reader.py"
```

## Commands

### Subscribe to a feed

```bash
$RSS subscribe https://example.com/feed.xml --name "Example Blog"
```

### Unsubscribe

```bash
$RSS unsubscribe https://example.com/feed.xml
```

### List subscriptions

```bash
$RSS list
```

Returns JSON array of `{url, name, added}`.

### Fetch new items

```bash
$RSS fetch                          # All feeds, only new items
$RSS fetch --all                    # All items regardless of seen state
$RSS fetch --feed https://...       # Single feed only
$RSS fetch --limit 20               # Cap results
```

Returns JSON array:

```json
[
  {
    "feed": "Example Blog",
    "title": "Post Title",
    "url": "https://...",
    "published": "2026-02-14T10:00:00+00:00",
    "summary": "First 300 chars..."
  }
]
```

Empty `[]` when no new items.

## Data Storage

Auto-detects workspace from `OPENCLAW_WORKSPACE` env var:

- **With workspace:** `$OPENCLAW_WORKSPACE/cache/rss/`
- **Fallback:** `~/.openclaw/skills/rss-reader/data/`

State files:

- `feeds.json` — subscribed feed URLs with labels
- `state.json` — last-seen entry GUIDs per feed for dedup

## Tips

- First fetch after subscribing returns all current items (everything is "new")
- Subsequent fetches return only items not previously seen
- Use `--all` to bypass dedup and re-fetch everything
- Use `--limit` to cap results when feeds are noisy
- Summaries are truncated to 300 chars with HTML stripped
- No API keys needed — works with any public RSS/Atom feed
