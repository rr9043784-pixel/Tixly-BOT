
import os
import secrets
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from api.auth import require_key
from api.database import connect, init_db


BASE_DIR = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = BASE_DIR / "dashboard"

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "")
DASHBOARD_ORIGIN = os.getenv("DASHBOARD_ORIGIN", "").rstrip("/")
SESSION_SECRET = os.getenv("DASHBOARD_SESSION_SECRET", "")

DISCORD_API = "https://discord.com/api/v10"
MANAGE_GUILD = 0x20
ADMINISTRATOR = 0x8


class GuildConfig(BaseModel):
    panel_title: str = Field(
        default="Contact Support",
        max_length=100
    )
    panel_description: str = Field(
        default="Choose the button below to open a support ticket.",
        max_length=1000
    )
    category_id: Optional[int] = None
    support_role_id: Optional[int] = None
    log_channel_id: Optional[int] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Tixly API",
    version="0.3.0",
    lifespan=lifespan
)


if SESSION_SECRET:
    app.add_middleware(
        SessionMiddleware,
        secret_key=SESSION_SECRET,
        session_cookie="tixly_session",
        max_age=604800,
        same_site="lax",
        https_only=True
    )


def oauth_ready():
    return all([
        DISCORD_CLIENT_ID,
        DISCORD_CLIENT_SECRET,
        DISCORD_REDIRECT_URI,
        DASHBOARD_ORIGIN,
        SESSION_SECRET
    ])


def require_oauth():
    if not oauth_ready():
        raise HTTPException(
            status_code=503,
            detail="Discord OAuth2 is not configured."
        )


def require_session(request: Request):
    if not SESSION_SECRET:
        raise HTTPException(status_code=503, detail="Session is not configured.")

    user = request.session.get("user")
    guilds = request.session.get("guilds")

    if not user or not isinstance(guilds, list):
        raise HTTPException(status_code=401, detail="Please sign in with Discord.")

    return user, guilds


def get_manageable_guild(guild_id: int, guilds: list):
    guild_id_str = str(guild_id)

    for guild in guilds:
        if str(guild.get("id")) != guild_id_str:
            continue

        try:
            permissions = int(guild.get("permissions", "0"))
        except (TypeError, ValueError):
            permissions = 0

        if guild.get("owner") or permissions & ADMINISTRATOR or permissions & MANAGE_GUILD:
            return guild

        break

    raise HTTPException(
        status_code=403,
        detail="You do not have permission to manage this Discord server."
    )


@app.get("/health")
def health():
    return {"ok": True, "service": "Tixly API"}


@app.get("/")
def dashboard_home():
    index_file = DASHBOARD_DIR / "index.html"
    if not index_file.is_file():
        return {"ok": True, "service": "Tixly API"}
    return FileResponse(index_file)


@app.get("/styles.css")
def dashboard_styles():
    file_path = DASHBOARD_DIR / "styles.css"
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Stylesheet not found.")
    return FileResponse(file_path, media_type="text/css")


@app.get("/app.js")
def dashboard_script():
    file_path = DASHBOARD_DIR / "app.js"
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Dashboard script not found.")
    return FileResponse(file_path, media_type="application/javascript")


@app.get("/auth/login")
def auth_login(request: Request):
    require_oauth()

    state = secrets.token_urlsafe(32)
    request.session.clear()
    request.session["oauth_state"] = state

    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
        "state": state
    }

    return RedirectResponse(
        "https://discord.com/oauth2/authorize?" + urlencode(params),
        status_code=302
    )


@app.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None
):
    require_oauth()

    if error:
        raise HTTPException(status_code=400, detail="Discord sign-in was cancelled.")

    expected_state = request.session.get("oauth_state")
    request.session.pop("oauth_state", None)

    if not state or not expected_state or not secrets.compare_digest(state, expected_state):
        request.session.clear()
        raise HTTPException(status_code=400, detail="Invalid OAuth state. Please try again.")

    if not code:
        raise HTTPException(status_code=400, detail="Discord did not return an authorization code.")

    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            f"{DISCORD_API}/oauth2/token",
            data={
                "client_id": DISCORD_CLIENT_ID,
                "client_secret": DISCORD_CLIENT_SECRET,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": DISCORD_REDIRECT_URI
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if token_response.status_code != 200:
            raise HTTPException(status_code=502, detail="Discord token exchange failed.")

        token_data = token_response.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(status_code=502, detail="Discord returned no access token.")

        headers = {"Authorization": f"Bearer {access_token}"}

        user_response = await client.get(f"{DISCORD_API}/users/@me", headers=headers)
        guild_response = await client.get(f"{DISCORD_API}/users/@me/guilds", headers=headers)

        if user_response.status_code != 200 or guild_response.status_code != 200:
            raise HTTPException(status_code=502, detail="Could not load your Discord account.")

        user_data = user_response.json()
        guild_data = guild_response.json()

    manageable_guilds = []

    for guild in guild_data:
        try:
            permissions = int(guild.get("permissions", "0"))
        except (TypeError, ValueError):
            permissions = 0

        if (
            guild.get("owner")
            or permissions & ADMINISTRATOR
            or permissions & MANAGE_GUILD
        ):
            manageable_guilds.append({
                "id": str(guild["id"]),
                "name": str(guild.get("name", "Discord Server")),
                "icon": guild.get("icon"),
                "owner": bool(guild.get("owner")),
                "permissions": str(permissions)
            })

    request.session.clear()
    request.session["user"] = {
        "id": str(user_data["id"]),
        "username": str(user_data.get("username", "Discord User")),
        "global_name": user_data.get("global_name"),
        "avatar": user_data.get("avatar")
    }
    request.session["guilds"] = manageable_guilds

    return RedirectResponse(DASHBOARD_ORIGIN + "/", status_code=303)


@app.get("/auth/me")
def auth_me(request: Request):
    user, guilds = require_session(request)
    return {"user": user, "guilds": guilds}


@app.post("/auth/logout")
def auth_logout(request: Request):
    request.session.clear()
    return {"ok": True}


# Existing bot-to-API routes. These continue using the private API key.

@app.get("/guilds/{guild_id}/config")
def get_guild_config(
    guild_id: int,
    x_tixly_key: Optional[str] = Header(default=None)
):
    require_key(x_tixly_key)

    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM guild_config WHERE guild_id = ?",
            (str(guild_id),)
        ).fetchone()

    if row is None:
        return GuildConfig().model_dump()

    data = dict(row)
    data.pop("guild_id", None)
    return data


@app.put("/guilds/{guild_id}/config")
def put_guild_config(
    guild_id: int,
    config: GuildConfig,
    x_tixly_key: Optional[str] = Header(default=None)
):
    require_key(x_tixly_key)

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO guild_config (
                guild_id,
                panel_title,
                panel_description,
                category_id,
                support_role_id,
                log_channel_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                panel_title = excluded.panel_title,
                panel_description = excluded.panel_description,
                category_id = excluded.category_id,
                support_role_id = excluded.support_role_id,
                log_channel_id = excluded.log_channel_id
            """,
            (
                str(guild_id),
                config.panel_title,
                config.panel_description,
                config.category_id,
                config.support_role_id,
                config.log_channel_id
            )
        )

    return {"ok": True, "guild_id": guild_id}


# Separate dashboard routes: a Discord session is required.

@app.get("/dashboard/guilds/{guild_id}/config")
def dashboard_get_config(guild_id: int, request: Request):
    _, guilds = require_session(request)
    get_manageable_guild(guild_id, guilds)

    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM guild_config WHERE guild_id = ?",
            (str(guild_id),)
        ).fetchone()

    if row is None:
        return GuildConfig().model_dump()

    data = dict(row)
    data.pop("guild_id", None)
    return data


@app.put("/dashboard/guilds/{guild_id}/config")
def dashboard_put_config(
    guild_id: int,
    config: GuildConfig,
    request: Request
):
    _, guilds = require_session(request)
    get_manageable_guild(guild_id, guilds)

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO guild_config (
                guild_id,
                panel_title,
                panel_description,
                category_id,
                support_role_id,
                log_channel_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                panel_title = excluded.panel_title,
                panel_description = excluded.panel_description,
                category_id = excluded.category_id,
                support_role_id = excluded.support_role_id,
                log_channel_id = excluded.log_channel_id
            """,
            (
                str(guild_id),
                config.panel_title,
                config.panel_description,
                config.category_id,
                config.support_role_id,
                config.log_channel_id
            )
        )

    return {"ok": True, "guild_id": guild_id}
