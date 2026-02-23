"""Security middleware — headers, request size limiting, and rate limiting."""

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self' ws: wss:; "
            "font-src 'self' data:; "
            "frame-ancestors 'self'"
        )
        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject request bodies larger than max_size bytes.

    Checks both the Content-Length header (fast reject) and enforces a
    streaming body limit so chunked-encoding requests are also bounded.
    """

    def __init__(self, app, max_size: int = 1_048_576):  # 1MB default
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                cl = int(content_length)
            except ValueError:
                return JSONResponse(
                    {"detail": "Invalid Content-Length"},
                    status_code=400,
                )
        else:
            cl = None
        if cl is not None and cl > self.max_size:
            return JSONResponse(
                {"detail": "Request body too large"},
                status_code=413,
            )
        # For chunked requests without Content-Length, stream and enforce limit
        if request.method in ("POST", "PUT", "PATCH") and not content_length:
            total = 0
            chunks = []
            async for chunk in request.stream():
                total += len(chunk)
                if total > self.max_size:
                    return JSONResponse(
                        {"detail": "Request body too large"},
                        status_code=413,
                    )
                chunks.append(chunk)
            # Re-attach the consumed body so downstream handlers can read it
            request._body = b"".join(chunks)
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple per-IP rate limiting using Redis (or in-memory fallback).

    Limits apply to /api/* routes only.  Default: 120 requests per minute.
    """

    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._local_buckets: dict[str, list] = {}  # fallback when Redis is unavailable

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        ip = request.client.host if request.client else "unknown"
        allowed = await self._check_rate(ip)
        if not allowed:
            return JSONResponse(
                {"detail": "Rate limit exceeded. Try again shortly."},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        return await call_next(request)

    async def _check_rate(self, ip: str) -> bool:
        from app.redis.client import get_redis
        redis = get_redis()

        if redis:
            key = f"ratelimit:{ip}"
            try:
                count = await redis.incr(key)
                if count == 1:
                    await redis.expire(key, 60)
                return count <= self.rpm
            except Exception:
                pass

        # In-memory fallback
        now = time.time()
        bucket = self._local_buckets.setdefault(ip, [])
        # Prune old entries
        cutoff = now - 60
        self._local_buckets[ip] = bucket = [t for t in bucket if t > cutoff]
        if len(bucket) >= self.rpm:
            return False
        bucket.append(now)
        return True
