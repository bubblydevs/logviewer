"""
Optional Discord OAuth2 login for the logviewer.

When DISCORD_AUTH_ENABLED is on, log pages are only visible to users who are in
the staff guild and hold the staff role. Membership is checked through the Java
API (which uses its discord.js client), not by the logviewer itself.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from contextvars import ContextVar
from urllib.parse import urlencode

import httpx
from sanic import Blueprint, response

DISCORD_API = "https://discord.com/api/v10"
SESSION_COOKIE = "logviewer_session"
STATE_COOKIE = "logviewer_oauth_state"
NEXT_COOKIE = "logviewer_next"


def _truthy(val):
    return str(val).strip().lower() in ("y", "yes", "t", "true", "on", "1")


AUTH_ENABLED = _truthy(os.getenv("DISCORD_AUTH_ENABLED", "no"))

REQUIRED_VARS = (
    "DISCORD_CLIENT_ID",
    "DISCORD_CLIENT_SECRET",
    "DISCORD_REDIRECT_URI",
    "SESSION_SECRET",
    "STAFF_GUILD_ID",
    "STAFF_ROLE_ID",
    "JAVA_API_URL",
    "JAVA_API_KEY",
)

if AUTH_ENABLED:
    missing = [name for name in REQUIRED_VARS if not os.getenv(name)]
    if missing:
        print("DISCORD_AUTH_ENABLED is on but these config vars are missing: " + ", ".join(missing))
        exit(1)

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "")
SESSION_SECRET = os.getenv("SESSION_SECRET", "").encode()
STAFF_GUILD_ID = os.getenv("STAFF_GUILD_ID", "")
STAFF_ROLE_ID = os.getenv("STAFF_ROLE_ID", "")
JAVA_API_URL = os.getenv("JAVA_API_URL", "").rstrip("/")
JAVA_API_KEY = os.getenv("JAVA_API_KEY", "")
SESSION_MAX_AGE = int(os.getenv("SESSION_MAX_AGE_HOURS", "168")) * 60 * 60
STAFF_RECHECK_SECONDS = int(os.getenv("STAFF_RECHECK_MINUTES", "15")) * 60
COOKIE_SECURE = _truthy(os.getenv("COOKIE_SECURE", "yes"))

# The logged in user for the current request, read by render_template.
current_user = ContextVar("current_user", default=None)

bp = Blueprint("auth")


class StaffCheckError(Exception):
    pass


# --- Signed session cookie -------------------------------------------------

def _b64encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64decode(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(payload):
    return _b64encode(hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).digest())


def encode_session(data):
    payload = _b64encode(json.dumps(data, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload)}"


def decode_session(token):
    if not token or "." not in token:
        return None
    payload, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        data = json.loads(_b64decode(payload))
    except ValueError:
        return None
    if data.get("exp", 0) < time.time():
        return None
    return data


def _set_cookie(resp, name, value, max_age):
    resp.cookies[name] = value
    resp.cookies[name]["path"] = "/"
    resp.cookies[name]["max-age"] = max_age
    resp.cookies[name]["httponly"] = True
    resp.cookies[name]["samesite"] = "Lax"
    resp.cookies[name]["secure"] = COOKIE_SECURE


def _clear_cookie(resp, name):
    _set_cookie(resp, name, "", 0)


# --- Discord / Java API ----------------------------------------------------

async def is_staff(user_id):
    """Asks the Java API whether the user is in the staff guild with the staff role."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{JAVA_API_URL}/logviewer/staff/{user_id}",
            params={"guildId": STAFF_GUILD_ID, "roleId": STAFF_ROLE_ID},
            headers={"x-api-key": JAVA_API_KEY},
        )
    if resp.status_code != 200:
        raise StaffCheckError(f"Java API returned {resp.status_code}")
    data = resp.json()
    return bool(data.get("inGuild") and data.get("hasRole"))


def _safe_next(path):
    # Only allow relative paths so ?next= can't be used as an open redirect.
    if path and path.startswith("/") and not path.startswith("//"):
        return path
    return "/"


def _render(request, name, status=200, **kwargs):
    resp = request.app.ctx.render_template(name, **kwargs)
    resp.status = status
    return resp


# --- Middleware ------------------------------------------------------------

def is_protected(path, log_prefix):
    if path == "/" or path.startswith("/static") or path in ("/login", "/callback", "/logout"):
        return False
    return path.startswith(log_prefix + "/") if log_prefix else True


async def auth_middleware(request, log_prefix):
    session = decode_session(request.cookies.get(SESSION_COOKIE))

    # The home page lists tickets for logged in staff, so it gets re-checked too.
    shows_tickets = request.path == "/" or is_protected(request.path, log_prefix)

    if session and shows_tickets and session["checked"] + STAFF_RECHECK_SECONDS < time.time():
        # Re-check periodically so removed staff lose access without waiting for the session to expire.
        try:
            still_staff = await is_staff(session["id"])
        except (httpx.HTTPError, StaffCheckError):
            return _render(request, "auth_error", status=503, message="Couldn't verify your staff status, please try again shortly.")
        if not still_staff:
            resp = _render(request, "auth_error", status=403, message="You no longer have access to view logs.")
            _clear_cookie(resp, SESSION_COOKIE)
            return resp
        session["checked"] = int(time.time())
        request.ctx.refresh_session = session

    request.ctx.user = session
    current_user.set(session)

    if session is None and is_protected(request.path, log_prefix):
        resp = response.redirect("/login")
        _set_cookie(resp, NEXT_COOKIE, _safe_next(request.path), 600)
        return resp


async def refresh_session_middleware(request, resp):
    session = getattr(request.ctx, "refresh_session", None)
    if session is not None:
        _set_cookie(resp, SESSION_COOKIE, encode_session(session), max(int(session["exp"] - time.time()), 0))


# --- Routes ----------------------------------------------------------------

@bp.get("/login")
async def login(request):
    state = secrets.token_urlsafe(32)
    query = urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "identify",
        "state": state,
        "prompt": "none",
    })
    resp = response.redirect(f"https://discord.com/oauth2/authorize?{query}")
    _set_cookie(resp, STATE_COOKIE, state, 600)
    return resp


@bp.get("/callback")
async def callback(request):
    code = request.args.get("code")
    state = request.args.get("state")
    expected_state = request.cookies.get(STATE_COOKIE)

    if not code:
        return response.redirect("/login")
    if not state or not expected_state or not hmac.compare_digest(state, expected_state):
        return _render(request, "auth_error", status=400, message="Login session expired, please try logging in again.")

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                f"{DISCORD_API}/oauth2/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_resp.raise_for_status()
            token = token_resp.json()

            if "identify" not in token.get("scope", "").split():
                return _render(request, "auth_error", status=400, message="The identify scope is required to log in.")

            user_resp = await client.get(
                f"{DISCORD_API}/users/@me",
                headers={"Authorization": f"{token['token_type']} {token['access_token']}"},
            )
            user_resp.raise_for_status()
            user = user_resp.json()

        staff = await is_staff(user["id"])
    except (httpx.HTTPError, StaffCheckError, KeyError):
        return _render(request, "auth_error", status=502, message="Something went wrong while logging in, please try again.")

    if not staff:
        resp = _render(request, "auth_error", status=403, message="You need to be a staff member with ticket access to view logs.")
        _clear_cookie(resp, STATE_COOKIE)
        return resp

    if user.get("avatar"):
        avatar = f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png"
    else:
        avatar = f"https://cdn.discordapp.com/embed/avatars/{(int(user['id']) >> 22) % 6}.png"

    now = int(time.time())
    session = {
        "id": user["id"],
        "username": user["username"],
        "global_name": user.get("global_name"),
        "avatar": avatar,
        "checked": now,
        "exp": now + SESSION_MAX_AGE,
    }

    resp = response.redirect(_safe_next(request.cookies.get(NEXT_COOKIE)))
    _set_cookie(resp, SESSION_COOKIE, encode_session(session), SESSION_MAX_AGE)
    _clear_cookie(resp, STATE_COOKIE)
    _clear_cookie(resp, NEXT_COOKIE)
    return resp


@bp.get("/logout")
async def logout(request):
    resp = response.redirect("/")
    _clear_cookie(resp, SESSION_COOKIE)
    return resp
