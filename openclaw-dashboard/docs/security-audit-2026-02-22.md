# OpenClaw Dashboard — Security Audit Report
**Date:** 2026-02-22
**Tool:** OpenAI Codex CLI v0.104.0 (read-only sandbox) — 3 audit passes
**Scope:** `backend/**` and `frontend/src/**` (98 source files)
**Total tokens consumed:** ~860,000 across 3 passes

---

## Remediation Summary

All 3 audit passes combined identified 28 unique findings. 24 have been fixed; 4 are deferred (architectural or CI-scope).

| Severity | Total | Fixed | Deferred |
|----------|-------|-------|----------|
| CRITICAL | 4 | 4 | 0 |
| HIGH | 9 | 7 | 2 (#3 WS query token, #8 localStorage) |
| MEDIUM | 8 | 7 | 1 (#14 CI SCA pipeline) |
| LOW | 7 | 6 | 1 (#3 WS query token — accepted tradeoff) |
| **Total** | **28** | **24** | **4** |

**Deferred items:**
- **JWT in WS query string:** WebSocket API does not support custom headers; query-param token is an accepted tradeoff. Mitigated by short token lifetime and TLS.
- **JWT in localStorage:** Requires HttpOnly cookie migration + CSRF defense — architectural change deferred.
- **Dependency CVE scanning:** CI pipeline (`pip-audit` + `npm audit`) — outside app codebase scope, flagged for DevOps setup.

---

## CRITICAL (3 findings) — ALL FIXED

### 1. Weak/default auth secrets enable trivial compromise ✅
- **Files:** `backend/app/config.py`, `backend/app/services/auth.py`
- **Issue:** `secret_key` defaults to empty string, `admin_password` defaults to `"changeme"`.
- **Fix:** `validate_secrets()` generates ephemeral key when empty with warning; `seed_admin()` refuses to create admin with insecure passwords; `_INSECURE_PASSWORDS` blocklist enforced.

### 2. WebSocket endpoints are unauthenticated ✅
- **Files:** `backend/app/main.py`, `backend/app/routers/chat.py`, `backend/app/services/auth.py`, `backend/app/websocket/manager.py`, `frontend/src/api/client.ts`, `frontend/src/pages/ChatPage.tsx`, `frontend/src/hooks/useActivityStream.ts`
- **Issue:** All `/ws/*` handlers accepted connections without token verification.
- **Fix:** `authenticate_websocket()` validates JWT from `?token=` query param, verifies user exists in DB, rejects with 1008 on failure. Frontend `wsUrl()` helper appends token. `manager.connect()` accepts `accepted=True` to avoid double-accept.

### 3. Stored XSS via markdown rendering ✅
- **Files:** `frontend/src/pages/PipelinesPage.tsx`
- **Issue:** Link `href` not safely sanitized.
- **Fix:** `sanitizeHref()` allowlists `http(s)://` and `mailto:` protocols only; attribute-escapes `"` and `'` to prevent breakout from `href="..."`.

---

## HIGH (6 findings) — 5 FIXED, 1 DEFERRED

### 4. Path traversal guard is bypassable ✅
- **Files:** `backend/app/routers/projects.py`
- **Issue:** `str.startswith()` prefix check is bypassable.
- **Fix:** `_safe_resolve()` uses `Path.is_relative_to()` for canonical containment; symlink targets verified to stay within base. Agent IDs validated with `^[a-zA-Z0-9_-]+$` regex.

### 5. Static file traversal in SPA fallback ✅
- **Files:** `backend/app/main.py`
- **Issue:** No containment check on resolved path.
- **Fix:** `fp.is_relative_to(frontend_dist.resolve())` enforced before serving.

### 6. Missing RBAC on sensitive operations ✅
- **Files:** `backend/app/routers/config.py`, `backend/app/routers/jobs.py`, `backend/app/routers/nodes.py`, `backend/app/routers/sessions_mgmt.py`
- **Issue:** Any valid token could modify config/jobs/device tokens/sessions.
- **Fix:** `require_admin` dependency added to all mutating endpoints: config PUT/POST, jobs POST/PUT/DELETE/run/control, nodes approve/reject/revoke/rotate, sessions PATCH/DELETE.

### 7. JWT claims trusted without DB user check ✅
- **Files:** `backend/app/main.py`, `backend/app/services/auth.py`
- **Issue:** Deleted/disabled users remained authorized until token expiry.
- **Fix:** Auth middleware and `authenticate_websocket()` both verify user existence in DB before granting access.

### 8. Token storage in localStorage ⏳ DEFERRED
- **Issue:** Bearer token in localStorage is accessible to any XSS.
- **Mitigation applied:** CSP hardened (removed `unsafe-inline` from `script-src`), XSS sinks addressed. Full HttpOnly cookie migration deferred.

### 9. Login lockout bypass via X-Forwarded-For ✅
- **Files:** `backend/app/routers/auth.py`
- **Issue:** Client-supplied forwarding header trusted directly.
- **Fix:** `_client_ip()` now uses socket IP (`request.client.host`) only, ignoring `X-Forwarded-For`.

---

## MEDIUM (6 findings) — 5 FIXED, 1 DEFERRED

### 10. No general API rate limiting ✅
- **Files:** `backend/app/middleware/security.py`, `backend/app/main.py`
- **Fix:** `RateLimitMiddleware` added — 120 req/min per IP on `/api/*` routes. Uses Redis with in-memory fallback.

### 11. Request size limiter bypassable ✅
- **Files:** `backend/app/middleware/security.py`
- **Issue:** Header-based check only; chunked encoding bypassed limit.
- **Fix:** `RequestSizeLimitMiddleware` now streams and enforces body limit for chunked `POST`/`PUT`/`PATCH` requests without `Content-Length`.

### 12. Full-file reads cause memory pressure ✅
- **Files:** `backend/app/routers/logs.py`, `backend/app/routers/debug.py`
- **Fix:** Log reads use seek-from-end + `deque` with bounded line count. Maximum read cap enforced.

### 13. Secret redaction incomplete ✅
- **Files:** `backend/app/routers/config.py`, `backend/app/routers/discovery.py`
- **Fix:** `_redact_secrets()` now uses `_SECRET_KEY_NAMES` set for recursive key-name matching. `_redact_list()` handles lists containing dicts with secrets. `_has_secret_keys()` also recurses into lists. Discovery endpoint redacts workspace config values.

### 14. Dependency CVE assessment not set up ⏳ DEFERRED
- **Fix needed:** Add `pip-audit`/`safety` + `npm audit`/Dependabot to CI pipeline. Flagged for DevOps setup.

### 15. CSP weak against XSS ✅
- **Files:** `backend/app/middleware/security.py`
- **Fix:** Removed `unsafe-inline` from CSP `script-src`. Current policy: `script-src 'self'`.

---

## LOW (3 findings) — ALL FIXED

### 16. Duplicate DELETE session route ✅
- **Files:** `backend/app/routers/sessions.py`
- **Fix:** Removed duplicate DELETE route stub.

### 17. Backup discovery hardcoded to year 2026 ✅
- **Files:** `backend/app/routers/system.py`
- **Fix:** Backup discovery now uses generic `iterdir()` instead of hardcoded year glob pattern.

### 18. Calendar end-range logic brittle ✅
- **Files:** `backend/app/routers/calendar.py`
- **Fix:** Uses `calendar.monthrange()` for correct end-of-month calculation.

---

## Re-Audit Results (Codex pass 2)

Second Codex audit verified 13/18 findings fully fixed, 4 partially verified, 1 expected skip. One regression (double WebSocket accept) was identified and resolved. Six follow-up findings from the re-audit were all addressed:

1. ✅ Double WebSocket accept regression → `manager.connect(accepted=True)`
2. ✅ Agent ID validation missing → regex `^[a-zA-Z0-9_-]+$`
3. ✅ Admin RBAC gaps on `jobs/control`, `jobs/run`, `sessions_mgmt` → `require_admin` added
4. ✅ WebSocket auth missing DB user check → `authenticate_websocket()` verifies user exists
5. ✅ Chunked body streaming enforcement → streaming + early rejection
6. ✅ Secret redaction for list values → `_redact_list()` + list handling in `_has_secret_keys()`
7. ✅ Href attribute escaping → `"` and `'` escaped in `sanitizeHref()`

---

## Audit Pass 3 — Additional Findings (10 items, 8 fixed)

| # | Severity | Finding | Status |
|---|----------|---------|--------|
| P3-1 | CRITICAL | `.env`/`.key`/`.pem` files readable via `/api/projects/{id}/file` | ✅ Blocked extensions set |
| P3-2 | HIGH | Discovery endpoint: top-level-only secret redaction | ✅ Recursive `_redact_secrets()` |
| P3-3 | HIGH | JWT exposed in WebSocket query string | ⏳ Architectural tradeoff |
| P3-4 | HIGH | Debug/logs/sessions/channels missing admin RBAC | ✅ `require_admin` on all endpoints |
| P3-5 | HIGH | WebSocket DoS (no rate limiting, unbounded state) | ✅ Connection limits + message rate + history bounds |
| P3-6 | MEDIUM | `str(e)` leaks internal details to clients | ✅ Generic error messages |
| P3-7 | MEDIUM | JWT in localStorage | ⏳ Previously deferred |
| P3-8 | LOW/MED | Health endpoint exposes operational metadata | ✅ Minimal liveness probe |
| P3-9 | LOW | Malformed Content-Length triggers 500 | ✅ ValueError guard → 400 |
| P3-10 | LOW | Plaintext password value in log output | ✅ Removed from log message |

---

## Notes
- No file-upload endpoints were found in reviewed scope.
- Classical CSRF risk is lower for REST APIs since auth uses bearer header (not cookie), but WebSocket auth now mitigates CSWSH risk.
- Dependency audits (`npm audit`, `pip-audit`) should be added to CI.
- WebSocket query-param token is an accepted tradeoff since the WS API does not support custom headers. Mitigated by TLS and token rotation.
