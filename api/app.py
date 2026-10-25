
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from api.auth import require_key
from api.database import connect, init_db


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
    version="0.2.0",
    lifespan=lifespan
)


@app.get("/health")
def health():
    return {"ok": True, "service": "Tixly API"}


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
