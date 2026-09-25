"""Bound request buffering even when Content-Length is absent or misleading."""

from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes=1_048_576):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                return await JSONResponse({"detail": "Request body exceeds 1 MiB"}, 413)(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        sent = False

        async def replay():
            nonlocal sent
            if sent:
                return await receive()
            sent = True
            return {"type": "http.request", "body": b"".join(chunks), "more_body": False}

        await self.app(scope, replay, send)


class DemoRateLimitMiddleware:
    """Coarse instance-wide limits for the single-instance free deployment.

    No forwarded-IP trust or unbounded client map. Deliberately shared by users;
    replace with a distributed limiter before scaling beyond the portfolio tier.
    """

    def __init__(self, app, login_limit=30, mutation_limit=120):
        self.app = app
        self.limits = {"login": login_limit, "mutation": mutation_limit}
        self.windows = {}

    async def __call__(self, scope, receive, send):
        from time import monotonic

        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path = scope.get("path", "")
        bucket = (
            "login"
            if path in {"/auth/login", "/auth/callback", "/auth/dev-login"}
            else ("mutation" if scope.get("method") not in {"GET", "HEAD", "OPTIONS"} else None)
        )
        if bucket:
            now = monotonic()
            started, count = self.windows.get(bucket, (now, 0))
            if now - started >= 60:
                started, count = now, 0
            if count >= self.limits[bucket]:
                return await JSONResponse(
                    {"detail": "Demo request limit reached. Please try again shortly."},
                    429,
                    headers={"Retry-After": str(max(1, int(60 - (now - started))))},
                )(scope, receive, send)
            self.windows[bucket] = (started, count + 1)
        await self.app(scope, receive, send)
