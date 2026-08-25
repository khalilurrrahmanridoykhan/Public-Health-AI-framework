"""Production HTTP controls: request IDs, limits, security headers, rate limits, and audit."""

from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import time
from typing import Any


class ProductionControls:
    def __init__(self, root: Path):
        self.root = root
        self.audit_path = root / "logs" / "audit.jsonl"
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.max_body = int(os.getenv("PHFRAME_MAX_BODY_BYTES", "52428800"))
        self.rate_limit = int(os.getenv("PHFRAME_RATE_LIMIT", "120"))

    def allowed(self, client: str, path: str) -> bool:
        limit = 10 if path == "/api/auth/login" else self.rate_limit
        now = time.monotonic(); bucket = self.requests[f"{client}:{path if path == '/api/auth/login' else '*'}"]
        while bucket and bucket[0] < now - 60: bucket.popleft()
        if len(bucket) >= limit: return False
        bucket.append(now); return True

    def audit(self, scope: dict[str, Any], status: int, actor: str = "anonymous") -> None:
        if scope.get("method", "GET") in {"GET", "HEAD", "OPTIONS"}: return
        item = {"time": datetime.now(timezone.utc).isoformat(), "request_id": scope.get("phframe.request_id"), "actor": actor, "method": scope.get("method"), "path": scope.get("path"), "status": status, "client": (scope.get("client") or ["unknown"])[0]}
        with self.audit_path.open("a", encoding="utf-8") as stream: stream.write(json.dumps(item, separators=(",", ":")) + "\n")

    def history(self, limit: int = 100) -> list[dict[str, Any]]:
        if not self.audit_path.exists(): return []
        lines = self.audit_path.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 1000)):]
        return [json.loads(line) for line in reversed(lines) if line.strip()]

    async def serve(self, app: Any, scope: dict[str, Any], receive: Any, send: Any, actor: str = "anonymous") -> None:
        request_id = secrets.token_hex(12); scope["phframe.request_id"] = request_id
        client = (scope.get("client") or ["unknown"])[0]; path = scope.get("path", "")
        if not self.allowed(client, path):
            from starlette.responses import JSONResponse
            await JSONResponse({"error": {"message": "Rate limit exceeded.", "request_id": request_id}}, status_code=429, headers={"retry-after": "60"})(scope, receive, send); return
        length = next((v for k, v in scope.get("headers", []) if k.lower() == b"content-length"), b"0")
        if int(length or 0) > self.max_body:
            from starlette.responses import JSONResponse
            await JSONResponse({"error": {"message": "Request body is too large.", "request_id": request_id}}, status_code=413)(scope, receive, send); return
        status = 500
        async def secured_send(message: dict[str, Any]) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]; headers = list(message.get("headers", [])); headers.extend([(b"x-request-id", request_id.encode()), (b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"), (b"referrer-policy", b"same-origin"), (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"), (b"content-security-policy", b"default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'")]); message["headers"] = headers
            await send(message)
        try: await app(scope, receive, secured_send)
        finally: self.audit(scope, status, actor)


def validate_production_environment(config: Any) -> list[str]:
    issues: list[str] = []
    if config.environment != "production": return issues
    if config.host in {"127.0.0.1", "localhost"}: issues.append("Production host is loopback-only.")
    if str(config.database_url).startswith("sqlite:"): issues.append("Use PostgreSQL for multi-user production deployments.")
    if not os.getenv("PHFRAME_API_TOKEN"): issues.append("PHFRAME_API_TOKEN is not configured for API writes.")
    if os.getenv("PHFRAME_CLOUDFLARE_CLIENT_ID") and not os.getenv("PHFRAME_CLOUDFLARE_CLIENT_SECRET"): issues.append("PHFRAME_CLOUDFLARE_CLIENT_SECRET is required for Cloudflare OAuth.")
    if os.getenv("PHFRAME_CLOUDFLARE_CLIENT_ID") and not os.getenv("PHFRAME_CREDENTIAL_KEY"): issues.append("PHFRAME_CREDENTIAL_KEY is required to protect Cloudflare OAuth tokens in production.")
    if os.getenv("PHFRAME_CLOUDFLARE_CLIENT_ID") and not os.getenv("PHFRAME_CLOUDFLARE_REDIRECT_URI", "").startswith("https://"): issues.append("PHFRAME_CLOUDFLARE_REDIRECT_URI must be an HTTPS callback in production.")
    return issues
