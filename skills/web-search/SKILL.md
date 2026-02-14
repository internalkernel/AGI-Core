---
name: web-search
description: Unified web search and content extraction. Tavily (primary) + Brave Search (fallback). No browser required.
---

# Web Search

Unified web search and content extraction. Uses Tavily as the primary engine (AI-optimized results with optional LLM-generated answers) and Brave Search as a fallback. No browser required.

## Setup

Dependencies are pre-installed. Requires at least one env var:

- `TAVILY_API_KEY` — primary engine (recommended)
- `BRAVE_SEARCH_API_KEY` — fallback engine

## Search

```bash
~/.openclaw/skills/web-search/search.js "query"                    # Basic search (5 results)
~/.openclaw/skills/web-search/search.js "query" -n 10              # More results
~/.openclaw/skills/web-search/search.js "query" --content          # Include page content as markdown
~/.openclaw/skills/web-search/search.js "query" -n 3 --content     # Combined
~/.openclaw/skills/web-search/search.js "query" --engine brave     # Force Brave engine
~/.openclaw/skills/web-search/search.js "query" --engine tavily    # Force Tavily engine
```

### Engine Selection

- **Auto (default):** Uses Tavily if `TAVILY_API_KEY` is set, otherwise falls back to Brave.
- **`--engine tavily`:** Force Tavily (requires `TAVILY_API_KEY`).
- **`--engine brave`:** Force Brave (requires `BRAVE_SEARCH_API_KEY`).

### Tavily Extras

When using Tavily, search results include an `Answer:` line at the top — an AI-generated summary of the query. The `--content` flag returns Tavily's server-side markdown extraction (no local fetching needed).

## Extract Page Content

```bash
~/.openclaw/skills/web-search/content.js https://example.com/article
```

Fetches a URL and extracts readable content as markdown. Uses Tavily extract (primary) with local Readability fallback.

## Output Format

```
Answer: AI-generated summary of the query (Tavily only)

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
