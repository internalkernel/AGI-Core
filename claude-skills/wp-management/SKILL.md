---
name: wp-management
description: WordPress REST API CLI for content management. Manage posts, pages, media, taxonomies, Gravity Forms entries, Redirection plugin, and SEOPress metadata via Application Passwords. Use for any content publishing, page updates, media uploads, or SEO metadata changes on client WordPress sites.
---

# WP Management

Manage WordPress sites via the REST API. Supports posts, pages, media, categories, tags, Gravity Forms, Redirection, and SEOPress. Uses Application Passwords (built into WP 5.6+) for authentication. All output is JSON to stdout; status/errors to stderr.

## Usage

```bash
WP="uv run ~/.claude/skills/wp-management/scripts/wordpress.py"
```

## Commands

### Register a site

```bash
$WP site add prod --url https://example.com --user admin --password "xxxx xxxx xxxx xxxx xxxx xxxx"
$WP site add staging --url https://staging.example.com --user editor --password "yyyy yyyy yyyy" --name "Staging"
```

### Remove / list sites

```bash
$WP site remove prod
$WP site list
```

`site list` masks application passwords in output.

### Posts

```bash
$WP posts prod list [--status draft|publish|all] [--limit 10] [--search "query"]
$WP posts prod list --after 2024-01-01 --before 2025-01-01 --limit 100 --orderby date
$WP posts prod list --limit 50 --page 2 --order asc --orderby date
$WP posts prod get 42
$WP posts prod create --title "New Post" --content "<p>Hello</p>" [--status draft] [--categories 1,5] [--slug "new-post"] [--parent 0]
$WP posts prod update 42 [--title "Updated"] [--content "..."] [--status publish] [--slug "updated-post"] [--parent 0]
$WP posts prod delete 42
```

**List filtering options:**
- `--page N` — page number (1-based, default 1)
- `--before DATE` — return items published before this date (ISO 8601 or `YYYY-MM-DD`)
- `--after DATE` — return items published after this date (ISO 8601 or `YYYY-MM-DD`)
- `--orderby FIELD` — sort by: date, id, title, slug, modified, include (default: date)
- `--order DIR` — sort direction: asc, desc (default: desc)

### Pages

Same interface as posts (including `--slug`, `--parent`, and list filtering):

```bash
$WP pages prod list [--status publish] [--limit 10]
$WP pages prod list --after 2024-01-01 --limit 50 --orderby title --order asc
$WP pages prod get 10
$WP pages prod create --title "Clear Braces" --content "<p>...</p>" [--status draft] [--slug "clear-braces"] [--parent 5]
$WP pages prod update 10 --title "About Us" [--slug "about-us"] [--parent 0]
$WP pages prod delete 10
```

### Media

```bash
$WP media prod list [--limit 10] [--type image|video]
$WP media prod upload /path/to/image.jpg [--title "Hero Image"] [--alt "Description"]
$WP media prod get 55
$WP media prod delete 55
```

### Taxonomies

```bash
$WP categories prod list
$WP tags prod list
```

### Plugins

Requires WP 5.5+ and administrator-level Application Password.

```bash
$WP plugins prod list [--status active|inactive]
$WP plugins prod get "akismet/akismet.php"
$WP plugins prod activate "akismet/akismet.php"
$WP plugins prod deactivate "akismet/akismet.php"
```

Plugin identifiers use the `folder/file.php` format (e.g. `akismet/akismet.php`). Always quote them.

### Themes

```bash
$WP themes prod list
$WP themes prod get hello-elementor-child
$WP themes prod activate hello-elementor-child
```

Theme identifiers use the stylesheet slug (directory name).

### Settings

```bash
$WP settings prod get
$WP settings prod update --set blogname="My Site" --set posts_per_page=10
```

`--set` is repeatable. Values are parsed as JSON when possible (numbers, booleans, null), otherwise treated as strings.

### Gravity Forms

Requires GF REST API v2 enabled on the site.

```bash
$WP gf prod forms
$WP gf prod entries 1 [--limit 20]
$WP gf prod entry 42
```

### Redirection

Requires the Redirection plugin with REST API enabled.

```bash
$WP redirects prod list [--limit 25]
$WP redirects prod create --source "/old-page" --target "/new-page" [--type 301]
$WP redirects prod delete 15
```

### SEOPress

```bash
# Get full SEO metadata (title, description, keywords, robots)
$WP seo prod get 42

# Update title and description
$WP seo prod update 42 --title "SEO Title" --description "Meta description"

# Set focus keyword
$WP seo prod update 42 --keyword "clear braces hanover pa, ceramic braces"

# Set noindex (for cannibalization fixes)
$WP seo prod update 42 --noindex

# Remove noindex (re-index a page)
$WP seo prod update 42 --index

# Set nofollow / remove nofollow
$WP seo prod update 42 --nofollow
$WP seo prod update 42 --follow

# Combine multiple SEO updates
$WP seo prod update 42 --keyword "braces cost" --noindex --title "Braces Cost | Practice Name"
```

**SEO update flags:**
- `--title` — SEO title tag
- `--description` — meta description
- `--keyword` — comma-separated target keywords (SEOPress focus keyword)
- `--noindex` / `--index` — set or remove noindex directive
- `--nofollow` / `--follow` — set or remove nofollow directive

## Data Storage

Site credentials are stored at `~/.claude/skills/wp-management/data/sites.json` (chmod 600).

## Setup

1. In WordPress admin, go to **Users > Profile > Application Passwords**
2. Enter a name (e.g. "Agent") and click **Add New Application Password**
3. Copy the generated password (spaces included)
4. Register with: `$WP site add <alias> --url https://... --user <username> --password "<app password>"`

For Gravity Forms: enable REST API in **Forms > Settings > REST API**.
For Redirection: the REST API is enabled by default when the plugin is active.

## Tips

- Application passwords include spaces — always quote them
- Posts and pages share the same CRUD interface, just swap the command
- Use `--status all` to include drafts, pending, and private items
- Media upload auto-detects MIME type from file extension
- `site list` always masks passwords for safe display
- All errors go to stderr with non-zero exit codes
