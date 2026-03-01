# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///
"""Dry-run tests for wordpress.py extensions (slug, parent, pagination, SEOPress).

Mocks wp_request to capture API calls without hitting any real site.
Run: uv run test_extensions.py
"""

import json
import sys
from unittest.mock import patch, MagicMock

# Import the module under test
import wordpress as wp

# ── Capture helper ──────────────────────────────────────────────

_calls: list[dict] = []

def mock_wp_request(site, method, endpoint, params=None, json_data=None, files=None):
    """Record the call and return plausible fake data."""
    _calls.append({
        "method": method,
        "endpoint": endpoint,
        "params": params,
        "json_data": json_data,
    })
    # Return fake responses depending on endpoint pattern
    if method == "GET" and endpoint.endswith("/metadata"):
        return {"_seopress_titles_title": "Test Title", "_seopress_titles_desc": "Test desc"}
    if method == "GET" and endpoint.endswith("/target-keywords"):
        return {"_seopress_analysis_target_kw": "braces, invisalign"}
    if method == "GET" and endpoint.endswith("/meta-robot-settings"):
        return {"_seopress_robots_index": "", "_seopress_robots_follow": ""}
    if method == "PUT":
        return {"ok": True}
    if method == "GET" and ("/posts" in endpoint or "/pages" in endpoint):
        if endpoint.count("/") <= 2:  # list endpoint
            return [{"id": 1, "title": {"rendered": "Test"}, "status": "publish",
                      "date": "2024-06-01T12:00:00", "link": "https://example.com/test", "slug": "test"}]
        else:  # single get
            return {"id": 1, "title": {"rendered": "Test"}, "content": {"rendered": "<p>hi</p>"},
                    "excerpt": {"rendered": ""}, "status": "publish", "date": "2024-06-01",
                    "modified": "2024-06-01", "link": "https://example.com/test", "slug": "test",
                    "author": 1, "categories": [], "tags": []}
    if method == "POST":
        return {"id": 99, "link": "https://example.com/new", "status": "draft", "slug": "new"}
    return {}

def mock_get_site(alias):
    return {"url": "https://example.com", "username": "admin", "app_password": "xxxx"}

# ── Test runner ─────────────────────────────────────────────────

passed = 0
failed = 0

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        print(f"  FAIL  {name}  {detail}")

def run_cli(*argv):
    """Parse args and dispatch, capturing stdout."""
    _calls.clear()
    parser = wp.build_parser()
    args = parser.parse_args(list(argv))
    return args

# ── Tests ───────────────────────────────────────────────────────

@patch("wordpress.wp_request", side_effect=mock_wp_request)
@patch("wordpress.get_site", side_effect=mock_get_site)
def test_all(mock_site, mock_req):
    global passed, failed

    print("\n═══ 1. --slug and --parent on create ═══")

    # Posts create with slug + parent
    args = run_cli("posts", "test", "create", "--title", "T", "--content", "C", "--slug", "my-slug", "--parent", "5")
    check("posts create: --slug parsed", args.slug == "my-slug")
    check("posts create: --parent parsed", args.parent == 5)
    # Execute and check body
    wp.cmd_content_create(args, "posts")
    body = _calls[-1]["json_data"]
    check("posts create: slug in body", body.get("slug") == "my-slug")
    check("posts create: parent in body", body.get("parent") == 5)

    # Pages create with slug + parent
    _calls.clear()
    args = run_cli("pages", "test", "create", "--title", "P", "--content", "C", "--slug", "about-us", "--parent", "0")
    wp.cmd_content_create(args, "pages")
    body = _calls[-1]["json_data"]
    check("pages create: slug in body", body.get("slug") == "about-us")
    check("pages create: parent in body", body.get("parent") == 0)

    # Create without slug/parent (should not be in body)
    _calls.clear()
    args = run_cli("posts", "test", "create", "--title", "T2", "--content", "C2")
    wp.cmd_content_create(args, "posts")
    body = _calls[-1]["json_data"]
    check("posts create: no slug when omitted", "slug" not in body)
    check("posts create: no parent when omitted", "parent" not in body)

    print("\n═══ 2. --slug and --parent on update ═══")

    _calls.clear()
    args = run_cli("posts", "test", "update", "42", "--slug", "new-slug", "--parent", "10")
    wp.cmd_content_update(args, "posts")
    body = _calls[-1]["json_data"]
    check("posts update: slug in body", body.get("slug") == "new-slug")
    check("posts update: parent in body", body.get("parent") == 10)

    _calls.clear()
    args = run_cli("pages", "test", "update", "10", "--title", "Hello", "--slug", "hello-page")
    wp.cmd_content_update(args, "pages")
    body = _calls[-1]["json_data"]
    check("pages update: slug in body", body.get("slug") == "hello-page")
    check("pages update: title + slug combined", body.get("title") == "Hello")

    # Slug-only update (no title/content/status)
    _calls.clear()
    args = run_cli("posts", "test", "update", "42", "--slug", "slug-only")
    wp.cmd_content_update(args, "posts")
    body = _calls[-1]["json_data"]
    check("posts update: slug-only update works", body == {"slug": "slug-only"})

    print("\n═══ 3. Pagination and date filtering on list ═══")

    _calls.clear()
    args = run_cli("posts", "test", "list", "--after", "2024-01-01", "--before", "2025-01-01",
                   "--limit", "100", "--orderby", "date", "--order", "asc", "--page", "2")
    wp.cmd_content_list(args, "posts")
    params = _calls[-1]["params"]
    check("list: after param", params.get("after") == "2024-01-01")
    check("list: before param", params.get("before") == "2025-01-01")
    check("list: per_page param", params.get("per_page") == 100)
    check("list: orderby param", params.get("orderby") == "date")
    check("list: order param", params.get("order") == "asc")
    check("list: page param", params.get("page") == 2)

    # Defaults: page=1, orderby=date, order=desc — these should still be passed
    _calls.clear()
    args = run_cli("pages", "test", "list")
    wp.cmd_content_list(args, "pages")
    params = _calls[-1]["params"]
    check("list defaults: page=1", params.get("page") == 1)
    check("list defaults: orderby=date", params.get("orderby") == "date")
    check("list defaults: order=desc", params.get("order") == "desc")
    check("list defaults: no before", "before" not in params)
    check("list defaults: no after", "after" not in params)

    print("\n═══ 4. SEOPress seo get (multi-endpoint merge) ═══")

    _calls.clear()
    args = run_cli("seo", "test", "get", "42")
    # Capture stdout
    import io
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    wp.cmd_seo_get(args)
    sys.stdout = old_stdout
    output = json.loads(buf.getvalue())

    check("seo get: 3 API calls made", len(_calls) == 3)
    check("seo get: metadata endpoint", _calls[0]["endpoint"].endswith("/metadata"))
    check("seo get: target-keywords endpoint", _calls[1]["endpoint"].endswith("/target-keywords"))
    check("seo get: meta-robot-settings endpoint", _calls[2]["endpoint"].endswith("/meta-robot-settings"))
    check("seo get: title in merged output", "_seopress_titles_title" in output)
    check("seo get: keywords in merged output", "_seopress_analysis_target_kw" in output)
    check("seo get: robots in merged output", "_seopress_robots_index" in output)

    print("\n═══ 5. SEOPress seo update — metadata only ═══")

    _calls.clear()
    args = run_cli("seo", "test", "update", "42", "--title", "New Title", "--description", "New desc")
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    wp.cmd_seo_update(args)
    sys.stdout = old_stdout
    output = json.loads(buf.getvalue())

    check("seo update meta: 1 API call", len(_calls) == 1)
    check("seo update meta: PUT to /metadata", _calls[0]["endpoint"].endswith("/metadata") and _calls[0]["method"] == "PUT")
    check("seo update meta: title in body", _calls[0]["json_data"]["_seopress_titles_title"] == "New Title")
    check("seo update meta: desc in body", _calls[0]["json_data"]["_seopress_titles_desc"] == "New desc")
    check("seo update meta: updated list", output["updated"] == ["metadata"])

    print("\n═══ 6. SEOPress seo update — keyword only ═══")

    _calls.clear()
    args = run_cli("seo", "test", "update", "42", "--keyword", "clear braces, ceramic braces")
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    wp.cmd_seo_update(args)
    sys.stdout = old_stdout
    output = json.loads(buf.getvalue())

    check("seo update kw: 1 API call", len(_calls) == 1)
    check("seo update kw: PUT to /target-keywords", _calls[0]["endpoint"].endswith("/target-keywords"))
    check("seo update kw: keyword in body", _calls[0]["json_data"]["_seopress_analysis_target_kw"] == "clear braces, ceramic braces")
    check("seo update kw: updated list", output["updated"] == ["target-keywords"])

    print("\n═══ 7. SEOPress seo update — noindex flag ═══")

    _calls.clear()
    args = run_cli("seo", "test", "update", "42", "--noindex")
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    wp.cmd_seo_update(args)
    sys.stdout = old_stdout
    output = json.loads(buf.getvalue())

    check("seo update noindex: 1 API call", len(_calls) == 1)
    check("seo update noindex: PUT to /meta-robot-settings", _calls[0]["endpoint"].endswith("/meta-robot-settings"))
    check("seo update noindex: value is 'yes'", _calls[0]["json_data"]["_seopress_robots_index"] == "yes")
    check("seo update noindex: updated list", output["updated"] == ["robots"])

    print("\n═══ 8. SEOPress seo update — --index (remove noindex) ═══")

    _calls.clear()
    args = run_cli("seo", "test", "update", "42", "--index")
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    wp.cmd_seo_update(args)
    sys.stdout = old_stdout
    output = json.loads(buf.getvalue())

    check("seo update --index: value is empty string", _calls[0]["json_data"]["_seopress_robots_index"] == "")

    print("\n═══ 9. SEOPress seo update — nofollow + follow ═══")

    _calls.clear()
    args = run_cli("seo", "test", "update", "42", "--nofollow")
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    wp.cmd_seo_update(args)
    sys.stdout = old_stdout

    check("seo update nofollow: value is 'yes'", _calls[0]["json_data"]["_seopress_robots_follow"] == "yes")

    _calls.clear()
    args = run_cli("seo", "test", "update", "42", "--follow")
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    wp.cmd_seo_update(args)
    sys.stdout = old_stdout

    check("seo update --follow: value is empty string", _calls[0]["json_data"]["_seopress_robots_follow"] == "")

    print("\n═══ 10. SEOPress seo update — combined multi-endpoint ═══")

    _calls.clear()
    args = run_cli("seo", "test", "update", "42",
                   "--title", "Combined", "--keyword", "braces cost", "--noindex", "--nofollow")
    old_stdout = sys.stdout
    sys.stdout = buf = io.StringIO()
    wp.cmd_seo_update(args)
    sys.stdout = old_stdout
    output = json.loads(buf.getvalue())

    check("seo update combined: 3 API calls", len(_calls) == 3)
    check("seo update combined: metadata call", _calls[0]["endpoint"].endswith("/metadata"))
    check("seo update combined: keywords call", _calls[1]["endpoint"].endswith("/target-keywords"))
    check("seo update combined: robots call", _calls[2]["endpoint"].endswith("/meta-robot-settings"))
    check("seo update combined: robots has both flags",
          _calls[2]["json_data"].get("_seopress_robots_index") == "yes"
          and _calls[2]["json_data"].get("_seopress_robots_follow") == "yes")
    check("seo update combined: updated list", set(output["updated"]) == {"metadata", "target-keywords", "robots"})

    # ── Summary ──
    print(f"\n{'═' * 50}")
    print(f"  {passed} passed, {failed} failed, {passed + failed} total")
    print(f"{'═' * 50}")
    return failed


if __name__ == "__main__":
    failures = test_all()
    sys.exit(1 if failures else 0)
