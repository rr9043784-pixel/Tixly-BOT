# Tixly

A starter project for a multi-server Discord ticket bot and web dashboard.

## Project layout
- `bot/` — Discord bot (Python, discord.py)
- `api/` — FastAPI backend for per-server configuration
- `dashboard/` — static English dashboard starter
- `.env.example` — required environment variables (never commit real secrets)

## Important
This is a starter scaffold, not a deployed service. The bot and API need a server/runtime to stay online. GitHub stores the code; GitHub Pages can host only the static dashboard, not the bot or API.

## Local setup

1. Install Python 3.11+.
2. Copy `.env.example` to `.env` and fill in values.
3. Install dependencies:
   ```bash
   pip install -r bot/requirements.txt
   pip install -r api/requirements.txt
   ```
4. Run the API:
   ```bash
   uvicorn api.app:app --reload
   ```
5. In another terminal run the bot:
   ```bash
   python -m bot.main
   ```

## Discord setup
Create an application and bot in the Discord Developer Portal. Add the bot token to `.env`.
For dashboard OAuth2, configure the Discord OAuth redirect URL to match `DISCORD_REDIRECT_URI`.

## Current scope
- Bot: `/ping`, `/ticket-panel`, `/close`
- API: basic per-guild configuration endpoints protected by a shared API key
- Dashboard: static starter UI; OAuth2 flow is not yet implemented
- Storage: SQLite for local development

Before public launch, implement Discord OAuth2 server-side, proper per-user authorization checks, persistent production database, audit logging, rate limiting, and secure deployment.
 
