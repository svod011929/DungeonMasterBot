# DungeonMasterBot

Telegram RPG bot with progression, crafting, achievements, expeditions, mini-games, VIP mechanics, Crypto Pay integration and an admin interface.

## Stack

- Python 3.10+
- aiogram 3
- aiohttp
- aiosqlite
- python-dotenv

## Quick start

```bash
git clone https://github.com/svod011929/DungeonMasterBot.git
cd DungeonMasterBot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

Fill `.env` before starting:

```env
BOT_TOKEN=replace_me
CRYPTO_PAY_TOKEN=replace_me
ADMIN_IDS=123456789
HIVIEWS_API_KEY=
DB_PATH=dungeon_master.db
```

Never commit the real `.env` file.

## Features

- character classes and progression;
- quests, expeditions, crafting and achievements;
- gem shop and VIP mechanics;
- Crypto Pay integration;
- SQLite storage;
- Telegram admin tools;
- optional HiViews integration.

## Project status

The project is currently implemented as a single large `bot.py`. For continued development, the next architecture step should be splitting handlers, database code, integrations and game logic into separate modules and adding automated tests.

## Security

All credentials are expected through environment variables. Rotate any credential that has ever been committed publicly before reusing the project in production.
