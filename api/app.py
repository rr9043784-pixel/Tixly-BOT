import os
import sqlite3
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()
DB_PATH = Path(os.getenv("DATABASE_PATH", "tixly.sqlite3"))
API_KEY = os.getenv("TIXLY_API_KEY", "")

app = FastAPI(title="Tixly API", version="0.1.0")

class GuildConfig(BaseModel):
    panel_title: str = Field(default="Contact Support", max_length=100)
    panel_description: str = Field(default="Choose the button below to open a support ticket.", max_length=1000)
    category_id: Optional[int] = None
    support_role_id: Optional[int] = None
    log_channel_id: Optional[int] = None

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id TEXT PRIMARY KEY,
                panel_title TEXT NOT NULL,
                panel_description TEXT NOT NULL,
                category_id INTEGER,
                support_role_id INTEGER,
                log_channel_id INTEGER
            )
        """)

@app.on_event("startup")
def startup():
    init_db()

def require_key(key: Optional[str]):
    if not API_KEY or key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/health")
def health():
    return {"ok": True, "service": "Tixly API"}

@app.get("/guilds/{guild_id}/config")
def get_guild_config(guild_id: int, x_tixly_key: Optional[str] = Header(default=None)):
    require_key(x_tixly_key)
    with connect() as conn:
        row = conn.execute("SELECT * FROM guild_config WHERE guild_id = ?", (str(guild_id),)).fetchone()
    if row is None:
        return GuildConfig().model_dump()
    return dict(row)

@app.put("/guilds/{guild_id}/config")
def put_guild_config(guild_id: int, config: GuildConfig, x_tixly_key: Optional[str] = Header(default=None)):
    require_key(x_tixly_key)
    with connect() as conn:
        conn.execute("""
            INSERT INTO guild_config
            (guild_id, panel_title, panel_description, category_id, support_role_id, log_channel_id)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                panel_title=excluded.panel_title,
                panel_description=excluded.panel_description,
                category_id=excluded.category_id,
                support_role_id=excluded.support_role_id,
                log_channel_id=excluded.log_channel_id
        """, (
            str(guild_id), config.panel_title, config.panel_description,
            config.category_id, config.support_role_id, config.log_channel_id
        ))
    return {"ok": True, "guild_id": guild_id}
 
