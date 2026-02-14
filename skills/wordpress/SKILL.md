---
name: wordpress
description: WordPress REST API CLI for agents. Manage posts, pages, media, taxonomies, and plugins via Application Passwords. Per-workspace data, JSON output.
---

# WordPress

Manage WordPress sites via the REST API. Supports posts, pages, media, categories, tags, Gravity Forms, Redirection, and SEOPress. Uses Application Passwords (built into WP 5.6+) for authentication. All output is JSON to stdout; status/errors to stderr.

## Usage

```bash
WP="uv run ~/.openclaw/skills/wordpress/scripts/wordpress.py"
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
$WP posts prod get 42
$WP posts prod create --title "New Post" --content "<p>Hello</p>" [--status draft] [--categories 1,5]
$WP posts prod update 42 [--title "Updated"] [--content "..."] [--status publish]
$WP posts prod delete 42
```

### Pages

Same interface as posts:

```bash
$WP pages prod list [--status publish] [--limit 10]
$WP pages prod get 10
$WP pages prod create --title "About" --content "<p>About us</p>" [--status draft]
$WP pages prod update 10 --title "About Us"
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
$WP seo prod get 42          # Get SEO metadata for post #42
$WP seo prod update 42 --title "SEO Title" --description "Meta description"
```

## Data Storage

Auto-detects workspace from `OPENCLAW_WORKSPACE` env var:

- **With workspace:** `$OPENCLAW_WORKSPACE/cache/wordpress/`
- **Fallback:** `~/.openclaw/skills/wordpress/data/`

State files:

- `sites.json` — registered sites with URL, username, app password (chmod 600)

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
