"""PHFrame hosted Cloudflare OAuth broker."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet
from starlette.applications import Starlette
from starlette.requests import Request as WebRequest
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.routing import Route

DATA = Path(os.getenv("PHFRAME_BROKER_DATA", "/var/lib/phframe-auth"))
PUBLIC_URL = os.getenv("PHFRAME_BROKER_URL", "").rstrip("/")
ADMIN_TOKEN = os.getenv("PHFRAME_BROKER_ADMIN_TOKEN", "")
KEY = os.getenv("PHFRAME_BROKER_KEY", "").encode()
fernet = Fernet(KEY)


def now() -> datetime: return datetime.now(timezone.utc)
def encrypted_path(name: str) -> Path: return DATA / f"{name}.enc"
def save(name: str, value: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True); path = encrypted_path(name); path.write_bytes(fernet.encrypt(json.dumps(value).encode())); path.chmod(0o600)
def load(name: str) -> dict:
    path = encrypted_path(name)
    return json.loads(fernet.decrypt(path.read_bytes())) if path.exists() else {}
def remove(name: str) -> None: encrypted_path(name).unlink(missing_ok=True)
def config() -> dict: return load("config")


def admin(request: WebRequest) -> bool:
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ") or request.cookies.get("phframe_broker_admin", "")
    return bool(ADMIN_TOKEN and secrets.compare_digest(supplied, ADMIN_TOKEN))


def safe_return(value: str) -> bool:
    parsed = urlparse(value)
    local = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    secure = parsed.scheme == "https" and bool(parsed.netloc)
    return (local or secure) and parsed.path == "/api/integrations/cloudflare/broker/callback"


def cloudflare(url: str, form: dict | None = None, bearer: str = "") -> dict:
    headers = {"accept": "application/json"}; data = urlencode(form).encode() if form else None
    if form: headers["content-type"] = "application/x-www-form-urlencoded"
    if bearer: headers["authorization"] = f"Bearer {bearer}"
    with urlopen(Request(url, data=data, headers=headers), timeout=30) as response:  # nosec B310 fixed Cloudflare URLs
        return json.loads(response.read())


async def home(request: WebRequest):
    ready = bool(config().get("client_id"))
    return HTMLResponse(f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width'><title>PHFrame Authorization</title><style>body{{font:16px system-ui;background:#071c24;color:#edf7f7;margin:0}}main{{max-width:760px;margin:10vh auto;padding:32px}}article{{background:#102b34;border:1px solid #31515b;border-radius:20px;padding:30px}}b{{color:#56d6c9}}code{{background:#071c24;padding:4px 8px;border-radius:6px}}</style></head><body><main><article><h1>PHFrame Authorization Service</h1><p><b>{'Ready' if ready else 'Setup required'}</b></p><p>This isolated service securely connects PHFrame installations to Cloudflare. OAuth grants are encrypted, short-lived, and delivered through one-time codes.</p><p>Health: <code>/health</code> · Administration: <code>/admin</code></p></article></main></body></html>""")


async def health(request: WebRequest): return JSONResponse({"status": "ok", "configured": bool(config().get("client_id"))})


async def admin_login(request: WebRequest):
    if request.method == "GET": return HTMLResponse("""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width'><title>PHFrame Broker Login</title><style>body{font:16px system-ui;background:#071c24;color:#edf7f7}form{max-width:460px;margin:15vh auto;background:#102b34;padding:30px;border-radius:18px}label{display:grid;gap:8px}input,button{padding:13px;margin-top:10px;border-radius:9px}button{background:#19b8a8;border:0;font-weight:700}</style></head><body><form method=post><h1>Broker administration</h1><label>Administrator token<input type=password name=token required autofocus></label><button>Sign in</button></form></body></html>""")
    form = await request.form(); supplied = str(form.get("token", ""))
    if not ADMIN_TOKEN or not secrets.compare_digest(supplied, ADMIN_TOKEN): return JSONResponse({"error":"Invalid administrator token."}, status_code=401)
    response = RedirectResponse("/admin", 303); response.set_cookie("phframe_broker_admin", ADMIN_TOKEN, httponly=True, secure=True, samesite="strict", max_age=28800); return response


async def admin_page(request: WebRequest):
    if not admin(request): return RedirectResponse("/admin/login", 303)
    current = config()
    if request.method == "POST":
        form = await request.form(); client_id = str(form.get("client_id", "")).strip(); client_secret = str(form.get("client_secret", "")).strip(); scopes = str(form.get("scopes", "workers-platform.read workers-platform.write")).strip()
        if not client_id or not client_secret: return JSONResponse({"error": "Client ID and secret are required."}, status_code=422)
        save("config", {"client_id": client_id, "client_secret": client_secret, "scopes": scopes, "updated_at": now().isoformat()}); return RedirectResponse("/admin?saved=1", 303)
    callback = f"{PUBLIC_URL}/oauth/callback"
    return HTMLResponse(f"""<!doctype html><html><head><meta charset=utf-8><meta name=viewport content='width=device-width'><title>PHFrame Broker Admin</title><style>body{{font:16px system-ui;background:#071c24;color:#edf7f7}}main{{max-width:720px;margin:5vh auto}}section{{background:#102b34;border:1px solid #31515b;border-radius:18px;padding:28px}}label{{display:grid;gap:8px;margin:18px 0}}input{{padding:13px;border-radius:8px;border:1px solid #52717b;background:#071c24;color:white}}button{{padding:13px 20px;border:0;border-radius:9px;background:#19b8a8;font-weight:700}}code{{word-break:break-all;color:#69e1d5}}</style></head><body><main><section><h1>Authorization service setup</h1><p>Register this exact redirect URI in the Cloudflare OAuth application:</p><p><code>{callback}</code></p><form method=post action='/admin'><label>Cloudflare OAuth client ID<input name=client_id value='{current.get('client_id','')}' required></label><label>Cloudflare OAuth client secret<input type=password name=client_secret placeholder='Stored encrypted' {'required' if not current else ''}></label><label>Scopes<input name=scopes value='{current.get('scopes','workers-platform.read workers-platform.write')}' required></label><button>Save OAuth configuration</button></form></section></main></body></html>""")


async def authorize(request: WebRequest):
    cfg, return_url, client_state = config(), request.query_params.get("return_url", ""), request.query_params.get("state", "")
    if not cfg.get("client_id"): return JSONResponse({"error": "Broker setup is incomplete."}, status_code=503)
    if not safe_return(return_url) or not client_state: return JSONResponse({"error": "Invalid PHFrame return URL or state."}, status_code=400)
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64); challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    save(f"state-{state}", {"return_url": return_url, "client_state": client_state, "verifier": verifier, "expires_at": (now()+timedelta(minutes=10)).isoformat()})
    params = {"response_type":"code","client_id":cfg["client_id"],"redirect_uri":f"{PUBLIC_URL}/oauth/callback","scope":cfg["scopes"],"state":state,"code_challenge":challenge,"code_challenge_method":"S256"}
    return RedirectResponse("https://dash.cloudflare.com/oauth2/auth?" + urlencode(params), 303)


async def callback(request: WebRequest):
    state, code = request.query_params.get("state", ""), request.query_params.get("code", ""); pending = load(f"state-{state}") if state else {}
    if not pending or datetime.fromisoformat(pending["expires_at"]) < now(): return JSONResponse({"error":"Authorization expired."}, status_code=400)
    cfg = config(); token = cloudflare("https://dash.cloudflare.com/oauth2/token", {"grant_type":"authorization_code","code":code,"redirect_uri":f"{PUBLIC_URL}/oauth/callback","client_id":cfg["client_id"],"client_secret":cfg["client_secret"],"code_verifier":pending["verifier"]}); accounts = cloudflare("https://api.cloudflare.com/client/v4/accounts?per_page=50", bearer=token["access_token"]).get("result", [])
    grant = secrets.token_urlsafe(48); save(f"grant-{grant}", {"token":token,"accounts":accounts,"expires_at":(now()+timedelta(minutes=2)).isoformat()}); remove(f"state-{state}")
    return RedirectResponse(pending["return_url"] + "?" + urlencode({"broker_code":grant,"state":pending["client_state"]}), 303)


async def exchange(request: WebRequest):
    payload = await request.json(); code = str(payload.get("code", "")); grant = load(f"grant-{code}") if code else {}
    if not grant or datetime.fromisoformat(grant.get("expires_at", "1970-01-01T00:00:00+00:00")) < now(): return JSONResponse({"error":"Grant is invalid or expired."}, status_code=400)
    remove(f"grant-{code}"); return JSONResponse({"data":{"token":grant["token"],"accounts":grant["accounts"]}}, headers={"cache-control":"no-store"})


async def refresh(request: WebRequest):
    payload = await request.json(); refresh_token = str(payload.get("refresh_token", "")); cfg = config()
    if not refresh_token: return JSONResponse({"error":"Refresh token is required."}, status_code=422)
    token = cloudflare("https://dash.cloudflare.com/oauth2/token", {"grant_type":"refresh_token","refresh_token":refresh_token,"client_id":cfg["client_id"],"client_secret":cfg["client_secret"]})
    return JSONResponse({"data":{"token":token}}, headers={"cache-control":"no-store"})


app = Starlette(routes=[Route("/",home),Route("/health",health),Route("/admin/login",admin_login,methods=["GET","POST"]),Route("/admin",admin_page,methods=["GET","POST"]),Route("/oauth/authorize",authorize),Route("/oauth/callback",callback),Route("/oauth/token",exchange,methods=["POST"]),Route("/oauth/refresh",refresh,methods=["POST"])])
