---
name: brave-search
description: Web search and content extraction via Brave Search API. Use for searching documentation, facts, or any web content. Lightweight, no browser required.
---

# Brave Search

Web search and content extraction using the Brave Search API. No browser required.

## Setup

Dependencies are pre-installed. Requires env: `BRAVE_SEARCH_API_KEY`.

## Search

```bash
~/.openclaw/skills/brave-search/search.js "query"                    # Basic search (5 results)
~/.openclaw/skills/brave-search/search.js "query" -n 10              # More results
~/.openclaw/skills/brave-search/search.js "query" --content          # Include page content as markdown
~/.openclaw/skills/brave-search/search.js "query" -n 3 --content     # Combined
```

## Extract Page Content

```bash
~/.openclaw/skills/brave-search/content.js https://example.com/article
```

Fetches a URL and extracts readable content as markdown.

## Output Format

```
--- Result 1 ---
Title: Page Title
Link: https://example.com/page
Snippet: Description from search results
Content: (if --content flag used)
  Markdown content extracted from the page...

--- Result 2 ---
...
```

## When to Use

- Searching for documentation or API references
- Looking up facts or current information
- Fetching content from specific URLs
- Any task requiring web search without interactive browsing
