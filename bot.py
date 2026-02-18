"""
🐉 DUNGEON MASTER BOT v3.0 — RPG Telegram Bot
Полноценный RPG бот с монетизацией через Crypto Pay API.
Расширенные механики: гем-магазин, крафт, достижения,
экспедиции, колесо фортуны, VIP, кнопочная админка.
Интеграция HiViews для автоматических показов рекламы.

Настройка:

Создай .env файл (или задай переменные окружения)
python bot.py (зависимости установятся автоматически)
"""

# ======================== АВТОУСТАНОВКА ЗАВИСИМОСТЕЙ ========================
import subprocess
import sys

REQUIRED_PACKAGES = {
    "aiogram": "aiogram",
    "aiohttp": "aiohttp",
    "aiosqlite": "aiosqlite",
    "dotenv": "python-dotenv",
}


def install_deps():
    for module, package in REQUIRED_PACKAGES.items():
        try:
            __import__(module)
        except ImportError:
            print(f"📦 Устанавливаю {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])
            print(f"✅ {package} установлен!")


install_deps()

# ======================== ИМПОРТЫ ========================
import asyncio
import aiohttp
import aiosqlite
import random
import json
import time
import logging
import os
import math
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, Router, F, BaseMiddleware
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup,
    Update, TelegramObject
)
from aiogram.filters import Command, CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# ======================== НАСТРОЙКИ ЧЕРЕЗ .ENV ========================
# Ищем .env рядом с bot.py
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_ENV_PATH = os.path.join(_SCRIPT_DIR, ".env")

# Загружаем .env — пробуем несколько путей
if os.path.exists(_ENV_PATH):
    load_dotenv(_ENV_PATH)
    print(f"✅ .env загружен из: {_ENV_PATH}")
elif os.path.exists(".env"):
    load_dotenv(".env")
    print("✅ .env загружен из текущей директории")
else:
    load_dotenv()  # попробует найти .env автоматически
    print("⚠️ Файл .env не найден! Используются переменные окружения или значения по умолчанию.")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", os.path.join(_SCRIPT_DIR, "dungeon_master.db"))

# Парсим ADMIN_IDS безопасно
_admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = []
if _admin_ids_raw:
    for _id in _admin_ids_raw.split(","):
        _id = _id.strip()
        if _id.isdigit():
            ADMIN_IDS.append(int(_id))
if not ADMIN_IDS:
    print("⚠️ ADMIN_IDS не задан или некорректный. Админ-панель будет недоступна.")

# HiViews — автоматические показы рекламы
# Получи API ключ на https://hiviews.net или у @hiviews_bot
HIVIEWS_API_KEY = os.getenv("HIVIEWS_API_KEY", "")
HIVIEWS_API_URL = os.getenv("HIVIEWS_API_URL", "https://hiviews.net/sendMessage")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ===== Проверка токена перед запуском =====
if not BOT_TOKEN or BOT_TOKEN in ("YOUR_BOT_TOKEN_HERE", ""):
    print("\n" + "=" * 60)
    print("❌ ОШИБКА: BOT_TOKEN не задан!")
    print("=" * 60)
    print("Создай файл .env рядом с bot.py и добавь:")
    print("")
    print("  BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ")
    print("  CRYPTO_PAY_TOKEN=твой_токен_от_CryptoBot")
    print("  ADMIN_IDS=твой_telegram_id")
    print("")
    print("Получить токен бота: https://t.me/BotFather")
    print("=" * 60 + "\n")
    sys.exit(1)

# Проверяем формат токена (число:строка)
if ":" not in BOT_TOKEN or not BOT_TOKEN.split(":")[0].isdigit():
    print("\n" + "=" * 60)
    print(f"❌ ОШИБКА: BOT_TOKEN имеет неверный формат!")
    print(f"  Текущий: {BOT_TOKEN[:20]}...")
    print(f"  Ожидаемый: 1234567890:ABCdefGHIjklMNO...")
    print("=" * 60 + "\n")
    sys.exit(1)

print(f"🔑 BOT_TOKEN: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:]}")
print(f"💳 CRYPTO_PAY: {'✅ задан' if CRYPTO_PAY_TOKEN else '❌ не задан'}")
print(f"👑 ADMIN_IDS: {ADMIN_IDS}")
print(f"🗄️ DB_PATH: {DB_PATH}")
print(f"📢 HIVIEWS: {'✅ задан' if HIVIEWS_API_KEY else '❌ не задан'}")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()


# ======================== HIVIEWS — ПРЯМОЙ ВЫЗОВ ========================
async def send_hiviews(user_id: int, message_id: int, user_first_name: str,
                       language_code: str, is_start: bool):
    """
    Отправляет данные на HiViews API для автоматического показа рекламы.
    Вызывается напрямую из хендлеров (не через middleware).
    Основано на официальном примере интеграции:
      URL: https://hiviews.net/sendMessage
      Auth: заголовок Authorization с API ключом
    """
    if not HIVIEWS_API_KEY:
        return
    try:
        headers = {
            'Authorization': HIVIEWS_API_KEY,
            'Content-Type': 'application/json',
        }
        payload = {
            'UserId': user_id,
            'MessageId': message_id,
            'UserFirstName': user_first_name,
            'LanguageCode': language_code or 'ru',
            'StartPlace': is_start,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(HIVIEWS_API_URL, headers=headers, json=payload) as response:
                resp_text = await response.text('utf-8')
                logger.info(f'[HiViews] status={response.status} user={user_id} '
                            f'start={is_start} response={resp_text}')
    except Exception as e:
        logger.warning(f'[HiViews] Error sending for user={user_id}: {e}')


def fire_hiviews(user_id: int, message_id: int, user_first_name: str,
                 language_code: str, is_start: bool = False):
    """Запускает send_hiviews как фоновую задачу (fire-and-forget)."""
    asyncio.create_task(send_hiviews(
        user_id=user_id,
        message_id=message_id,
        user_first_name=user_first_name,
        language_code=language_code,
        is_start=is_start,
    ))


def fire_hiviews_message(message: Message, is_start: bool = False):
    """Хелпер для вызова из обработчиков Message."""
    if message.chat.type != 'private':
        return
    fire_hiviews(
        user_id=message.from_user.id,
        message_id=message.message_id,
        user_first_name=message.from_user.first_name or '',
        language_code=message.from_user.language_code or 'ru',
        is_start=is_start,
    )


def fire_hiviews_callback(callback: CallbackQuery):
    """Хелпер для вызова из обработчиков CallbackQuery."""
    if not callback.message or callback.message.chat.type != 'private':
        return
    fire_hiviews(
        user_id=callback.from_user.id,
        message_id=callback.message.message_id,
        user_first_name=callback.from_user.first_name or '',
        language_code=callback.from_user.language_code or 'ru',
        is_start=False,
    )


dp.include_router(router)

# ======================== ИГРОВЫЕ ДАННЫЕ ========================
CLASSES = {
    "warrior": {"name": "⚔️ Воин", "emoji": "⚔️", "hp": 150, "atk": 12, "def": 10, "crit": 5,
                "desc": "Мастер ближнего боя с высоким здоровьем и защитой"},
    "mage": {"name": "🧙 Маг", "emoji": "🧙", "hp": 90, "atk": 20, "def": 4, "crit": 10,
             "desc": "Повелитель стихий с огромной атакой"},
    "archer": {"name": "🏹 Лучник", "emoji": "🏹", "hp": 110, "atk": 15, "def": 6, "crit": 20,
               "desc": "Меткий стрелок с высоким шансом крита"},
    "assassin": {"name": "🗡️ Ассасин", "emoji": "🗡️", "hp": 100, "atk": 18, "def": 5, "crit": 25,
                 "desc": "Мастер теней, наносящий смертельные удары"},
}

TITLES = {
    0: "🌱 Новичок", 5: "⚔️ Воитель", 10: "🛡️ Защитник", 15: "🔥 Разрушитель",
    20: "💀 Каратель", 25: "👑 Легенда", 30: "🐉 Убийца драконов",
    40: "⭐ Мифический герой", 50: "🌟 Бог войны",
}

DUNGEONS = {
    1: {"name": "🌲 Тёмный лес", "min_lvl": 1, "monsters": [
        {"name": "🐺 Волк", "hp": 30, "atk": 5, "gold": 10, "xp": 15},
        {"name": "🕷️ Паук", "hp": 25, "atk": 7, "gold": 12, "xp": 18},
        {"name": "👺 Гоблин", "hp": 40, "atk": 8, "gold": 15, "xp": 22},
    ], "boss": {"name": "🐻 Лесной медведь", "hp": 100, "atk": 15, "gold": 50, "xp": 80}},
    2: {"name": "🏚️ Заброшенные руины", "min_lvl": 5, "monsters": [
        {"name": "💀 Скелет", "hp": 50, "atk": 12, "gold": 20, "xp": 30},
        {"name": "🧟 Зомби", "hp": 60, "atk": 10, "gold": 22, "xp": 35},
        {"name": "👻 Призрак", "hp": 45, "atk": 15, "gold": 25, "xp": 40},
    ], "boss": {"name": "🦴 Костяной рыцарь", "hp": 200, "atk": 25, "gold": 120, "xp": 180}},
    3: {"name": "🌋 Огненные пещеры", "min_lvl": 10, "monsters": [
        {"name": "🦎 Саламандра", "hp": 80, "atk": 18, "gold": 35, "xp": 50},
        {"name": "🔥 Огненный элементаль", "hp": 70, "atk": 22, "gold": 40, "xp": 55},
        {"name": "🐉 Дракончик", "hp": 100, "atk": 20, "gold": 45, "xp": 60},
    ], "boss": {"name": "🐲 Древний дракон", "hp": 400, "atk": 40, "gold": 300, "xp": 400}},
    4: {"name": "🏔️ Ледяной пик", "min_lvl": 15, "monsters": [
        {"name": "❄️ Ледяной голем", "hp": 120, "atk": 25, "gold": 50, "xp": 70},
        {"name": "🐧 Ледяной дух", "hp": 90, "atk": 30, "gold": 55, "xp": 75},
        {"name": "🦣 Мамонт", "hp": 150, "atk": 22, "gold": 60, "xp": 80},
    ], "boss": {"name": "🧊 Ледяной король", "hp": 600, "atk": 55, "gold": 500, "xp": 600}},
    5: {"name": "😈 Бездна", "min_lvl": 20, "monsters": [
        {"name": "👿 Демон", "hp": 180, "atk": 35, "gold": 80, "xp": 100},
        {"name": "🦇 Вампир", "hp": 160, "atk": 40, "gold": 85, "xp": 110},
        {"name": "💀 Лич", "hp": 200, "atk": 45, "gold": 90, "xp": 120},
    ], "boss": {"name": "😈 Повелитель бездны", "hp": 1000, "atk": 70, "gold": 1000, "xp": 1200}},
    6: {"name": "🌀 Пустота", "min_lvl": 28, "monsters": [
        {"name": "🌑 Тёмная сущность", "hp": 250, "atk": 50, "gold": 120, "xp": 150},
        {"name": "👁️ Око бездны", "hp": 220, "atk": 55, "gold": 130, "xp": 160},
        {"name": "🕳️ Пожиратель душ", "hp": 280, "atk": 48, "gold": 140, "xp": 170},
    ], "boss": {"name": "🌀 Хранитель пустоты", "hp": 1500, "atk": 90, "gold": 1500, "xp": 2000}},
    7: {"name": "✨ Небесный чертог", "min_lvl": 35, "monsters": [
        {"name": "👼 Падший ангел", "hp": 350, "atk": 60, "gold": 180, "xp": 220},
        {"name": "⚡ Громовой титан", "hp": 400, "atk": 65, "gold": 200, "xp": 250},
        {"name": "🌪️ Повелитель бурь", "hp": 380, "atk": 70, "gold": 220, "xp": 270},
    ], "boss": {"name": "✨ Архангел Тьмы", "hp": 2500, "atk": 120, "gold": 3000, "xp": 4000}},
}

ELITE_MONSTERS = [
    {"name": "🌟 Золотой дракон", "hp": 500, "atk": 50, "gold": 500, "xp": 300, "gems": 3, "min_lvl": 10},
    {"name": "💜 Теневой лорд", "hp": 400, "atk": 60, "gold": 400, "xp": 250, "gems": 2, "min_lvl": 8},
    {"name": "🔮 Кристальный голем", "hp": 600, "atk": 45, "gold": 350, "xp": 350, "gems": 4, "min_lvl": 12},
    {"name": "☠️ Костяной император", "hp": 800, "atk": 55, "gold": 600, "xp": 400, "gems": 5, "min_lvl": 15},
    {"name": "🌈 Радужный феникс", "hp": 700, "atk": 65, "gold": 700, "xp": 500, "gems": 6, "min_lvl": 20},
]

SHOP_ITEMS = {
    "hp_potion": {"name": "❤️ Зелье здоровья", "desc": "Восстанавливает 50 HP", "price": 30,
                  "type": "consumable", "effect": {"hp": 50}},
    "big_hp_potion": {"name": "💖 Большое зелье здоровья", "desc": "Восстанавливает 150 HP", "price": 80,
                      "type": "consumable", "effect": {"hp": 150}},
    "atk_scroll": {"name": "📜 Свиток силы", "desc": "+5 к атаке на 3 боя", "price": 100,
                   "type": "buff", "effect": {"atk": 5, "duration": 3}},
    "def_scroll": {"name": "🛡️ Свиток защиты", "desc": "+5 к защите на 3 боя", "price": 100,
                   "type": "buff", "effect": {"def": 5, "duration": 3}},
    "iron_sword": {"name": "🗡️ Железный меч", "desc": "+3 к атаке", "price": 200,
                   "type": "equipment", "slot": "weapon", "effect": {"atk": 3}},
    "steel_sword": {"name": "⚔️ Стальной меч", "desc": "+7 к атаке", "price": 500,
                    "type": "equipment", "slot": "weapon", "effect": {"atk": 7}},
    "iron_armor": {"name": "🥋 Железная броня", "desc": "+4 к защите", "price": 250,
                   "type": "equipment", "slot": "armor", "effect": {"def": 4}},
    "steel_armor": {"name": "🛡️ Стальная броня", "desc": "+8 к защите", "price": 600,
                    "type": "equipment", "slot": "armor", "effect": {"def": 8}},
    "lucky_ring": {"name": "💍 Кольцо удачи", "desc": "+10% крит", "price": 400,
                   "type": "equipment", "slot": "accessory", "effect": {"crit": 10}},
    "revive_stone": {"name": "💎 Камень воскрешения", "desc": "Автовоскрешение при смерти", "price": 150,
                     "type": "consumable", "effect": {"revive": 1}},
}

GEM_SHOP_ITEMS = {
    "mythic_sword": {"name": "⚡ Мифический клинок", "desc": "+15 ATK, +5% крит", "price_gems": 25,
                     "type": "equipment", "slot": "weapon", "effect": {"atk": 15, "crit": 5}},
    "mythic_armor": {"name": "🔮 Мифическая броня", "desc": "+15 DEF, +30 HP", "price_gems": 25,
                     "type": "equipment", "slot": "armor", "effect": {"def": 15, "max_hp": 30}},
    "mythic_ring": {"name": "💎 Кольцо бессмертия", "desc": "+20% крит, +5 ATK", "price_gems": 30,
                    "type": "equipment", "slot": "accessory", "effect": {"crit": 20, "atk": 5}},
    "xp_booster": {"name": "📗 Книга мудрости", "desc": "x2 опыта на 10 боёв", "price_gems": 8,
                   "type": "buff", "effect": {"xp_mult": 2, "duration": 10}},
    "gold_booster": {"name": "📙 Книга алхимии", "desc": "x2 золота на 10 боёв", "price_gems": 8,
                     "type": "buff", "effect": {"gold_mult": 2, "duration": 10}},
    "mega_potion": {"name": "🧪 Мега-зелье", "desc": "Полное исцеление + макс энергия", "price_gems": 5,
                    "type": "consumable", "effect": {"full_heal": 1, "full_energy": 1}},
    "energy_refill": {"name": "⚡ Кристалл энергии", "desc": "Мгновенно +10 энергии", "price_gems": 3,
                      "type": "consumable", "effect": {"energy": 10}},
    "respec_token": {"name": "🔄 Камень перерождения", "desc": "Сменить класс персонажа", "price_gems": 15,
                     "type": "consumable", "effect": {"respec": 1}},
    "max_energy_up": {"name": "🔋 Ёмкость энергии+", "desc": "+5 к макс энергии (навсегда)", "price_gems": 20,
                      "type": "consumable", "effect": {"max_energy_up": 5}},
    "lucky_charm": {"name": "🍀 Талисман удачи", "desc": "+15% к дропу гемов на 20 боёв", "price_gems": 10,
                    "type": "buff", "effect": {"gem_luck": 15, "duration": 20}},
}

GEM_CHESTS = {
    "bronze_chest": {"name": "🟫 Бронзовый сундук", "price_gems": 5, "rewards": [
        {"type": "gold", "min": 50, "max": 200, "weight": 50},
        {"type": "xp", "min": 30, "max": 100, "weight": 30},
        {"type": "item", "items": ["hp_potion", "big_hp_potion", "revive_stone"], "weight": 15},
        {"type": "gems", "min": 1, "max": 3, "weight": 5},
    ]},
    "silver_chest": {"name": "⬜ Серебряный сундук", "price_gems": 15, "rewards": [
        {"type": "gold", "min": 200, "max": 800, "weight": 35},
        {"type": "xp", "min": 100, "max": 400, "weight": 25},
        {"type": "item", "items": ["atk_scroll", "def_scroll", "iron_sword", "iron_armor"], "weight": 20},
        {"type": "gems", "min": 3, "max": 8, "weight": 10},
        {"type": "item", "items": ["steel_sword", "steel_armor", "lucky_ring"], "weight": 10},
    ]},
    "golden_chest": {"name": "🟨 Золотой сундук", "price_gems": 35, "rewards": [
        {"type": "gold", "min": 500, "max": 2000, "weight": 25},
        {"type": "xp", "min": 300, "max": 1000, "weight": 15},
        {"type": "item", "items": ["steel_sword", "steel_armor", "lucky_ring"], "weight": 20},
        {"type": "gems", "min": 8, "max": 20, "weight": 15},
        {"type": "gem_item", "items": ["mythic_sword", "mythic_armor", "mythic_ring"], "weight": 10},
        {"type": "vip_days", "min": 1, "max": 7, "weight": 15},
    ]},
}

CRAFT_RECIPES = {
    "enchanted_sword": {
        "name": "✨ Зачарованный меч", "desc": "+10 ATK, +8% крит",
        "ingredients": {"steel_sword": 1, "atk_scroll": 2}, "cost_gold": 300, "cost_gems": 5,
        "result_type": "equipment", "slot": "weapon", "effect": {"atk": 10, "crit": 8},
    },
    "enchanted_armor": {
        "name": "✨ Зачарованная броня", "desc": "+12 DEF, +20 HP",
        "ingredients": {"steel_armor": 1, "def_scroll": 2}, "cost_gold": 300, "cost_gems": 5,
        "result_type": "equipment", "slot": "armor", "effect": {"def": 12, "max_hp": 20},
    },
    "mega_ring": {
        "name": "👑 Кольцо власти", "desc": "+15% крит, +3 ATK, +3 DEF",
        "ingredients": {"lucky_ring": 1, "revive_stone": 3}, "cost_gold": 500, "cost_gems": 10,
        "result_type": "equipment", "slot": "accessory", "effect": {"crit": 15, "atk": 3, "def": 3},
    },
    "super_potion": {
        "name": "🌈 Радужное зелье", "desc": "Полное исцеление",
        "ingredients": {"hp_potion": 3, "big_hp_potion": 1}, "cost_gold": 100, "cost_gems": 0,
        "result_type": "consumable", "effect": {"hp": 9999},
    },
}

ACHIEVEMENTS = {
    "first_blood": {"name": "🩸 Первая кровь", "desc": "Убей первого монстра", "check": "dungeon_wins",
                    "value": 1, "reward_gold": 20, "reward_gems": 1},
    "hunter_10": {"name": "🎯 Охотник", "desc": "Убей 10 монстров", "check": "dungeon_wins",
                  "value": 10, "reward_gold": 50, "reward_gems": 2},
    "hunter_100": {"name": "💀 Истребитель", "desc": "Убей 100 монстров", "check": "dungeon_wins",
                   "value": 100, "reward_gold": 200, "reward_gems": 10},
    "hunter_500": {"name": "☠️ Уничтожитель", "desc": "Убей 500 монстров", "check": "dungeon_wins",
                   "value": 500, "reward_gold": 1000, "reward_gems": 30},
    "boss_1": {"name": "👑 Убийца боссов", "desc": "Убей первого босса", "check": "boss_kills",
               "value": 1, "reward_gold": 50, "reward_gems": 3},
    "boss_10": {"name": "🐲 Драконоборец", "desc": "Убей 10 боссов", "check": "boss_kills",
                "value": 10, "reward_gold": 200, "reward_gems": 8},
    "boss_50": {"name": "⚡ Повелитель боссов", "desc": "Убей 50 боссов", "check": "boss_kills",
                "value": 50, "reward_gold": 500, "reward_gems": 25},
    "pvp_1": {"name": "⚔️ Первый бой", "desc": "Выиграй PvP бой", "check": "wins",
              "value": 1, "reward_gold": 30, "reward_gems": 1},
    "pvp_10": {"name": "🏆 Гладиатор", "desc": "Выиграй 10 PvP боёв", "check": "wins",
               "value": 10, "reward_gold": 100, "reward_gems": 5},
    "pvp_50": {"name": "🏟️ Чемпион арены", "desc": "Выиграй 50 PvP боёв", "check": "wins",
               "value": 50, "reward_gold": 500, "reward_gems": 20},
    "lvl_5": {"name": "📊 Новичок+", "desc": "Достигни 5 уровня", "check": "level",
              "value": 5, "reward_gold": 30, "reward_gems": 2},
    "lvl_10": {"name": "📊 Опытный", "desc": "Достигни 10 уровня", "check": "level",
               "value": 10, "reward_gold": 100, "reward_gems": 5},
    "lvl_20": {"name": "📊 Ветеран", "desc": "Достигни 20 уровня", "check": "level",
               "value": 20, "reward_gold": 300, "reward_gems": 10},
    "lvl_30": {"name": "📊 Легенда", "desc": "Достигни 30 уровня", "check": "level",
               "value": 30, "reward_gold": 500, "reward_gems": 20},
    "gold_1000": {"name": "💰 Богач", "desc": "Заработай 1000 золота", "check": "total_gold_earned",
                  "value": 1000, "reward_gold": 100, "reward_gems": 3},
    "gold_10000": {"name": "💰 Миллионер", "desc": "Заработай 10000 золота", "check": "total_gold_earned",
                   "value": 10000, "reward_gold": 500, "reward_gems": 15},
    "streak_7": {"name": "🔥 Неделька", "desc": "7 дней подряд заходи в бот", "check": "streak",
                 "value": 7, "reward_gold": 200, "reward_gems": 10},
    "streak_30": {"name": "🔥 Месяц!", "desc": "30 дней подряд!", "check": "streak",
                  "value": 30, "reward_gold": 1000, "reward_gems": 50},
    "ref_5": {"name": "🔗 Рекрутер", "desc": "Пригласи 5 друзей", "check": "referral_count",
              "value": 5, "reward_gold": 200, "reward_gems": 10},
}

EXPEDITIONS = {
    "forest_patrol": {"name": "🌲 Патруль леса", "duration_min": 30, "gold": (20, 60),
                      "xp": (10, 30), "gem_chance": 5},
    "mine_expedition": {"name": "⛏️ Разведка шахты", "duration_min": 60, "gold": (50, 150),
                        "xp": (30, 80), "gem_chance": 10},
    "treasure_hunt": {"name": "🗺️ Охота за сокровищами", "duration_min": 120, "gold": (100, 400),
                      "xp": (60, 200), "gem_chance": 20},
    "dragon_lair": {"name": "🐲 Логово дракона", "duration_min": 240, "gold": (300, 1000),
                    "xp": (150, 500), "gem_chance": 35},
    "void_rift": {"name": "🌀 Разлом пустоты", "duration_min": 480, "gold": (500, 2000),
                  "xp": (300, 1000), "gem_chance": 50, "min_lvl": 15},
}

WHEEL_SEGMENTS = [
    {"name": "💰 50 золота", "type": "gold", "amount": 50, "weight": 25, "color": "🟡"},
    {"name": "💰 150 золота", "type": "gold", "amount": 150, "weight": 15, "color": "🟡"},
    {"name": "💰 500 золота", "type": "gold", "amount": 500, "weight": 5, "color": "🟡"},
    {"name": "💎 1 гем", "type": "gems", "amount": 1, "weight": 20, "color": "💜"},
    {"name": "💎 3 гема", "type": "gems", "amount": 3, "weight": 10, "color": "💜"},
    {"name": "💎 10 гемов", "type": "gems", "amount": 10, "weight": 2, "color": "💜"},
    {"name": "✨ 100 XP", "type": "xp", "amount": 100, "weight": 15, "color": "🔵"},
    {"name": "⚡ +5 энергии", "type": "energy", "amount": 5, "weight": 10, "color": "🟢"},
    {"name": "❤️ Полное исцеление", "type": "heal", "amount": 0, "weight": 8, "color": "🔴"},
    {"name": "💀 Ничего", "type": "nothing", "amount": 0, "weight": 15, "color": "⚫"},
    {"name": "🎁 x2 награда!", "type": "double", "amount": 0, "weight": 3, "color": "🌈"},
]

VIP_BENEFITS = {
    "xp_bonus": 1.5, "gold_bonus": 1.5, "energy_regen": 5,
    "max_energy_bonus": 5, "gem_drop_bonus": 10, "daily_gems": 2, "expedition_speed": 0.75,
}

DONATE_ITEMS = {
    "gold_100": {"name": "💰 100 золота", "price_usd": 0.5, "gold": 100, "gems": 0},
    "gold_500": {"name": "💰 500 золота", "price_usd": 2.0, "gold": 500, "gems": 0},
    "gold_2000": {"name": "💰 2000 золота", "price_usd": 7.0, "gold": 2000, "gems": 0},
    "gems_10": {"name": "💎 10 кристаллов", "price_usd": 1.0, "gold": 0, "gems": 10},
    "gems_50": {"name": "💎 50 кристаллов", "price_usd": 4.0, "gold": 0, "gems": 50},
    "gems_150": {"name": "💎 150 кристаллов", "price_usd": 10.0, "gold": 0, "gems": 150},
    "vip_7": {"name": "👑 VIP 7 дней", "price_usd": 3.0, "gold": 0, "gems": 0, "vip_days": 7},
    "vip_30": {"name": "👑 VIP 30 дней", "price_usd": 9.0, "gold": 0, "gems": 0, "vip_days": 30},
    "starter_pack": {"name": "🎁 Стартовый набор", "price_usd": 3.0, "gold": 300, "gems": 15},
    "vip_pack": {"name": "👑 VIP набор", "price_usd": 5.0, "gold": 500, "gems": 30, "vip_days": 7},
    "mega_pack": {"name": "🔥 МЕГА набор", "price_usd": 20.0, "gold": 5000, "gems": 200, "vip_days": 30},
}

SLOT_SYMBOLS = ["🍒", "🍋", "🍊", "🍇", "💎", "7️⃣", "🔔", "⭐"]
SLOT_PAYOUTS = {
    ("7️⃣", "7️⃣", "7️⃣"): 50, ("💎", "💎", "💎"): 30, ("⭐", "⭐", "⭐"): 20,
    ("🔔", "🔔", "🔔"): 15, ("🍇", "🍇", "🍇"): 10, ("🍊", "🍊", "🍊"): 7,
    ("🍋", "🍋", "🍋"): 5, ("🍒", "🍒", "🍒"): 3,
}


# ======================== БАЗА ДАННЫХ ========================
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, username TEXT DEFAULT '', class TEXT DEFAULT '',
                level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, xp_needed INTEGER DEFAULT 100,
                hp INTEGER DEFAULT 100, max_hp INTEGER DEFAULT 100, atk INTEGER DEFAULT 10,
                def INTEGER DEFAULT 5, crit INTEGER DEFAULT 5, gold INTEGER DEFAULT 50,
                gems INTEGER DEFAULT 0, wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0,
                dungeon_wins INTEGER DEFAULT 0, boss_kills INTEGER DEFAULT 0,
                elite_kills INTEGER DEFAULT 0, total_gold_earned INTEGER DEFAULT 0,
                total_gems_earned INTEGER DEFAULT 0, total_spent_usd REAL DEFAULT 0,
                inventory TEXT DEFAULT '{}', equipment TEXT DEFAULT '{}',
                buffs TEXT DEFAULT '[]', achievements TEXT DEFAULT '[]',
                daily_claimed TEXT DEFAULT '', streak INTEGER DEFAULT 0,
                energy INTEGER DEFAULT 10, max_energy INTEGER DEFAULT 10,
                last_energy TEXT DEFAULT '', vip_until TEXT DEFAULT '',
                expedition TEXT DEFAULT '', expedition_start TEXT DEFAULT '',
                wheel_spins INTEGER DEFAULT 0, last_wheel TEXT DEFAULT '',
                crafts_done INTEGER DEFAULT 0, chests_opened INTEGER DEFAULT 0,
                referrer_id INTEGER DEFAULT 0, referral_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT '', is_banned INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, invoice_id INTEGER,
                item_key TEXT, amount_usd REAL, status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT '', paid_at TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY, gold INTEGER DEFAULT 0, gems INTEGER DEFAULT 0,
                max_uses INTEGER DEFAULT 1, used_count INTEGER DEFAULT 0, created_at TEXT DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS promo_uses (user_id INTEGER, code TEXT, PRIMARY KEY (user_id, code));
        """)
        await db.commit()


async def get_user(user_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_user(user_id: int, username: str):
    now = datetime.now().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, created_at, last_energy) VALUES (?, ?, ?, ?)",
            (user_id, username, now, now))
        await db.commit()


async def update_user(user_id: int, **kwargs):
    if not kwargs:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        sets = ", ".join(f'"{k}" = ?' for k in kwargs)
        vals = list(kwargs.values()) + [user_id]
        await db.execute(f"UPDATE users SET {sets} WHERE user_id = ?", vals)
        await db.commit()


async def get_top_players(order_by="level", limit=10):
    # Защита от SQL-инъекций — разрешаем только известные колонки
    allowed = {"level", "wins", "gold", "boss_kills", "total_gems_earned", "elite_kills",
               "dungeon_wins", "xp", "losses"}
    if order_by not in allowed:
        order_by = "level"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f'SELECT * FROM users WHERE class != "" AND is_banned = 0 '
            f'ORDER BY "{order_by}" DESC, xp DESC LIMIT ?', (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_all_users_count():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            return (await cur.fetchone())[0]


async def get_total_revenue():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COALESCE(SUM(amount_usd), 0) FROM payments WHERE status = 'paid'") as cur:
            return (await cur.fetchone())[0]


async def get_global_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}
        queries = {
            "total_players": "SELECT COUNT(*) FROM users WHERE class != ''",
            "avg_level": "SELECT COALESCE(AVG(level), 0) FROM users WHERE class != ''",
            "max_level": "SELECT COALESCE(MAX(level), 0) FROM users WHERE class != ''",
            "total_fights": "SELECT COALESCE(SUM(dungeon_wins), 0) FROM users",
            "total_bosses": "SELECT COALESCE(SUM(boss_kills), 0) FROM users",
            "total_pvp": "SELECT COALESCE(SUM(wins), 0) FROM users",
            "total_elites": "SELECT COALESCE(SUM(elite_kills), 0) FROM users",
            "total_gold": "SELECT COALESCE(SUM(total_gold_earned), 0) FROM users",
            "total_gems": "SELECT COALESCE(SUM(total_gems_earned), 0) FROM users",
            "total_chests": "SELECT COALESCE(SUM(chests_opened), 0) FROM users",
            "total_crafts": "SELECT COALESCE(SUM(crafts_done), 0) FROM users",
        }
        for key, query in queries.items():
            async with db.execute(query) as c:
                val = (await c.fetchone())[0]
                stats[key] = round(val, 1) if key == "avg_level" else val
        for cls in CLASSES:
            async with db.execute("SELECT COUNT(*) FROM users WHERE class = ?", (cls,)) as c:
                stats[f"class_{cls}"] = (await c.fetchone())[0]
        day_ago = (datetime.now() - timedelta(days=1)).isoformat()
        async with db.execute("SELECT COUNT(*) FROM users WHERE last_energy >= ?", (day_ago,)) as c:
            stats["active_24h"] = (await c.fetchone())[0]
        return stats


# ======================== CRYPTO PAY API ========================
CRYPTO_PAY_API = "https://pay.crypt.bot/api"


async def crypto_create_invoice(amount: float, description: str, payload: str) -> Optional[dict]:
    if not CRYPTO_PAY_TOKEN:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
            params = {
                "currency_type": "fiat", "fiat": "USD", "amount": str(amount),
                "description": description, "payload": payload,
                "paid_btn_name": "callback",
                "paid_btn_url": f"https://t.me/{(await bot.get_me()).username}",
            }
            async with session.get(f"{CRYPTO_PAY_API}/createInvoice",
                                   headers=headers, params=params) as resp:
                data = await resp.json()
                return data["result"] if data.get("ok") else None
    except Exception as e:
        logger.error(f"Crypto Pay exception: {e}")
        return None


async def crypto_get_invoices(invoice_ids: str) -> list:
    if not CRYPTO_PAY_TOKEN:
        return []
    try:
        async with aiohttp.ClientSession() as session:
            headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
            async with session.get(f"{CRYPTO_PAY_API}/getInvoices", headers=headers,
                                   params={"invoice_ids": invoice_ids}) as resp:
                data = await resp.json()
                return data["result"].get("items", []) if data.get("ok") else []
    except Exception as e:
        logger.error(f"Crypto Pay check error: {e}")
        return []


# ======================== УТИЛИТЫ ========================
def xp_for_level(level: int) -> int:
    return int(100 * (level ** 1.5))


def is_vip(user: dict) -> bool:
    if not user.get("vip_until"):
        return False
    try:
        return datetime.fromisoformat(user["vip_until"]) > datetime.now()
    except Exception:
        return False


def get_title(level: int) -> str:
    title = "🌱 Новичок"
    for lvl, t in sorted(TITLES.items()):
        if level >= lvl:
            title = t
    return title


def calc_stats(user: dict) -> dict:
    stats = {"atk": user["atk"], "def": user["def"], "crit": user["crit"],
             "hp": user["hp"], "max_hp": user["max_hp"]}
    equipment = json.loads(user["equipment"]) if user["equipment"] else {}
    for slot, item_key in equipment.items():
        item = SHOP_ITEMS.get(item_key) or GEM_SHOP_ITEMS.get(item_key) or CRAFT_RECIPES.get(item_key)
        if item:
            for k, v in item.get("effect", {}).items():
                if k in stats:
                    stats[k] += v
    buffs = json.loads(user["buffs"]) if user["buffs"] else []
    for buff in buffs:
        for k, v in buff.get("effect", {}).items():
            if k in stats and k not in ("duration", "xp_mult", "gold_mult", "gem_luck"):
                stats[k] += v
    return stats


def get_buff_multipliers(user: dict) -> dict:
    mults = {"xp_mult": 1.0, "gold_mult": 1.0, "gem_luck": 0}
    buffs = json.loads(user["buffs"]) if user["buffs"] else []
    for buff in buffs:
        eff = buff.get("effect", {})
        if "xp_mult" in eff:
            mults["xp_mult"] = max(mults["xp_mult"], eff["xp_mult"])
        if "gold_mult" in eff:
            mults["gold_mult"] = max(mults["gold_mult"], eff["gold_mult"])
        if "gem_luck" in eff:
            mults["gem_luck"] += eff["gem_luck"]
    if is_vip(user):
        mults["xp_mult"] *= VIP_BENEFITS["xp_bonus"]
        mults["gold_mult"] *= VIP_BENEFITS["gold_bonus"]
        mults["gem_luck"] += VIP_BENEFITS["gem_drop_bonus"]
    return mults


async def add_xp(user_id: int, xp: int) -> str:
    user = await get_user(user_id)
    new_xp = user["xp"] + xp
    level = user["level"]
    xp_needed = user["xp_needed"]
    msg = ""
    total_hp_bonus = 0
    total_atk_bonus = 0
    total_def_bonus = 0

    while new_xp >= xp_needed:
        new_xp -= xp_needed
        level += 1
        xp_needed = xp_for_level(level)
        hp_b = 10 + (5 if user["class"] == "warrior" else 0)
        atk_b = 2 + (1 if user["class"] in ("mage", "assassin") else 0)
        def_b = 1 + (1 if user["class"] == "warrior" else 0)
        total_hp_bonus += hp_b
        total_atk_bonus += atk_b
        total_def_bonus += def_b
        msg += f"\n🎉 <b>Уровень {level}!</b> {get_title(level)}"
        msg += f"\n  ❤️+{hp_b} ⚔️+{atk_b} 🛡️+{def_b}"

    new_max_hp = user["max_hp"] + total_hp_bonus
    new_hp = min(new_max_hp, user["hp"] + total_hp_bonus)
    await update_user(user_id,
                      xp=new_xp, level=level, xp_needed=xp_needed,
                      max_hp=new_max_hp, hp=new_hp,
                      atk=user["atk"] + total_atk_bonus,
                      **{"def": user["def"] + total_def_bonus})
    return msg


async def check_achievements(user_id: int) -> str:
    user = await get_user(user_id)
    old_unlocked = json.loads(user["achievements"]) if user["achievements"] else []
    unlocked = list(old_unlocked)
    msg = ""
    new_keys = []
    for key, ach in ACHIEVEMENTS.items():
        if key in unlocked:
            continue
        val = user.get(ach["check"], 0)
        if val >= ach["value"]:
            unlocked.append(key)
            new_keys.append(key)
            msg += f"\n🏅 <b>Достижение: {ach['name']}!</b> +{ach['reward_gold']}💰 +{ach['reward_gems']}💎"
    if new_keys:
        total_gold = sum(ACHIEVEMENTS[k]["reward_gold"] for k in new_keys)
        total_gems = sum(ACHIEVEMENTS[k]["reward_gems"] for k in new_keys)
        await update_user(user_id,
                          gold=user["gold"] + total_gold,
                          gems=user["gems"] + total_gems,
                          total_gems_earned=user["total_gems_earned"] + total_gems,
                          achievements=json.dumps(unlocked))
    return msg


async def regen_energy(user_id: int):
    user = await get_user(user_id)
    if not user or not user.get("last_energy"):
        return
    try:
        last = datetime.fromisoformat(user["last_energy"])
    except Exception:
        return
    now = datetime.now()
    minutes_passed = (now - last).total_seconds() / 60
    regen_rate = VIP_BENEFITS["energy_regen"] if is_vip(user) else 10
    regen = int(minutes_passed / regen_rate)
    if regen > 0:
        max_e = user["max_energy"] + (VIP_BENEFITS["max_energy_bonus"] if is_vip(user) else 0)
        new_energy = min(user["energy"] + regen, max_e)
        await update_user(user_id, energy=new_energy, last_energy=now.isoformat())


def make_kb(buttons: list[list[tuple]]) -> InlineKeyboardMarkup:
    keyboard = []
    for row in buttons:
        keyboard.append([
            InlineKeyboardButton(text=t, url=d) if d.startswith("http")
            else InlineKeyboardButton(text=t, callback_data=d)
            for t, d in row
        ])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_vip_end(user: dict) -> datetime:
    if user.get("vip_until") and user["vip_until"]:
        try:
            return max(datetime.fromisoformat(user["vip_until"]), datetime.now())
        except Exception:
            pass
    return datetime.now()


# ======================== ОБРАБОТЧИКИ ========================
@router.message(CommandStart())
async def cmd_start(message: Message):
    uid = message.from_user.id
    username = message.from_user.first_name or "Герой"

    # HiViews — отправляем данные при /start
    fire_hiviews_message(message, is_start=True)

    await create_user(uid, username)
    user = await get_user(uid)

    # Реферал
    if message.text:
        args = message.text.split()
        if len(args) > 1 and args[1].isdigit():
            ref_id = int(args[1])
            if ref_id != uid and user["referrer_id"] == 0:
                ref_user = await get_user(ref_id)
                if ref_user:
                    await update_user(uid, referrer_id=ref_id)
                    await update_user(ref_id, gold=ref_user["gold"] + 50, gems=ref_user["gems"] + 2,
                                      referral_count=ref_user["referral_count"] + 1,
                                      total_gems_earned=ref_user["total_gems_earned"] + 2)
                    try:
                        await bot.send_message(ref_id, f"🎉 Новый реферал: {username}! +50💰 +2💎")
                    except Exception:
                        pass

    if user["class"]:
        await send_main_menu(message)
    else:
        text = ("🐉 <b>Добро пожаловать в Dungeon Master!</b>\n\n"
                "Тебя ждут подземелья, боссы, PvP арена, крафт, "
                "экспедиции и многое другое!\n\n⚔️ <b>Выбери свой класс:</b>\n\n")
        for key, cls in CLASSES.items():
            text += (f"{cls['name']} — {cls['desc']}\n"
                     f"  ❤️{cls['hp']} ⚔️{cls['atk']} 🛡️{cls['def']} 🎯{cls['crit']}%\n\n")
        kb = make_kb([
            [("⚔️ Воин", "class_warrior"), ("🧙 Маг", "class_mage")],
            [("🏹 Лучник", "class_archer"), ("🗡️ Ассасин", "class_assassin")],
        ])
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("class_"))
async def choose_class(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    cls_key = callback.data.replace("class_", "")
    if cls_key not in CLASSES:
        return await callback.answer("❌ Неизвестный класс")
    cls = CLASSES[cls_key]
    await update_user(callback.from_user.id,
                      **{"class": cls_key},
                      hp=cls["hp"], max_hp=cls["hp"],
                      atk=cls["atk"],
                      **{"def": cls["def"]},
                      crit=cls["crit"])
    await callback.message.edit_text(
        f"🎉 <b>Ты стал {cls['name']}!</b>\n\n"
        f"❤️{cls['hp']} ⚔️{cls['atk']} 🛡️{cls['def']} 🎯{cls['crit']}%\n\nУдачи, герой! 🐉")
    await asyncio.sleep(1)
    await send_main_menu(callback.message, edit=False)
    await callback.answer()


async def send_main_menu(message: Message, edit=False):
    kb = make_kb([
        [("👤 Профиль", "profile"), ("🗺️ Подземелья", "dungeons")],
        [("🏟️ PvP Арена", "pvp"), ("🎰 Мини-игры", "games")],
        [("🛒 Магазин", "shop"), ("💎 Гем-магазин", "gem_shop")],
        [("🔨 Крафт", "craft"), ("🎯 Экспедиции", "expeditions")],
        [("🎡 Колесо фортуны", "wheel"), ("🏆 Достижения", "achievements")],
        [("🏆 Рейтинг", "leaderboard"), ("🎁 Ежедневная", "daily")],
        [("📊 Статистика мира", "world_stats"), ("📦 Инвентарь", "inventory")],
        [("💳 Донат-магазин", "donate_shop"), ("🔗 Реферал", "referral")],
    ])
    text = "🐉 <b>Dungeon Master</b> — Главное меню\n\nВыбери действие:"
    try:
        if edit:
            await message.edit_text(text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)
    except Exception:
        await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    await send_main_menu(callback.message, edit=True)
    await callback.answer()


# ===================== ПРОФИЛЬ =====================
@router.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    if not user or not user["class"]:
        return await callback.answer("Сначала создай персонажа!")
    await regen_energy(callback.from_user.id)
    user = await get_user(callback.from_user.id)
    stats = calc_stats(user)
    cls = CLASSES[user["class"]]
    title = get_title(user["level"])
    vip_text = "👑 VIP" if is_vip(user) else ""
    equipment = json.loads(user["equipment"]) if user["equipment"] else {}
    eq_text = ""
    for slot, item_key in equipment.items():
        item = SHOP_ITEMS.get(item_key) or GEM_SHOP_ITEMS.get(item_key) or CRAFT_RECIPES.get(item_key)
        if item:
            eq_text += f"  {item['name']}\n"
    if not eq_text:
        eq_text = "  Ничего\n"
    unlocked = json.loads(user["achievements"]) if user["achievements"] else []
    max_e = user["max_energy"] + (VIP_BENEFITS["max_energy_bonus"] if is_vip(user) else 0)
    text = (
        f"👤 <b>{user['username']}</b> {cls['emoji']} {vip_text}\n"
        f"{title}\n{'━' * 25}\n"
        f"📊 Уровень: <b>{user['level']}</b> | ✨ {user['xp']}/{user['xp_needed']}\n"
        f"❤️ HP: {user['hp']}/{stats['max_hp']}\n"
        f"⚔️{stats['atk']} 🛡️{stats['def']} 🎯{stats['crit']}%\n"
        f"⚡ Энергия: {user['energy']}/{max_e}\n{'━' * 25}\n"
        f"💰 {user['gold']} | 💎 {user['gems']}\n{'━' * 25}\n"
        f"⚔️ PvP: {user['wins']}W/{user['losses']}L\n"
        f"🏰 Данжи: {user['dungeon_wins']} | 👑 Боссы: {user['boss_kills']}\n"
        f"🌟 Элиты: {user['elite_kills']} | 🏅 Достижения: {len(unlocked)}/{len(ACHIEVEMENTS)}\n"
        f"{'━' * 25}\n🎽 <b>Экипировка:</b>\n{eq_text}"
    )
    kb = make_kb([
        [("❤️ Лечиться (10💰)", "heal"), ("⚡ +Энергия (3💎)", "gem_energy")],
        [("🔙 Назад", "main_menu")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "heal")
async def cb_heal(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    if user["hp"] >= user["max_hp"]:
        return await callback.answer("❤️ Здоровье полное!")
    if user["gold"] < 10:
        return await callback.answer("💰 Недостаточно золота!")
    heal = min(50, user["max_hp"] - user["hp"])
    await update_user(callback.from_user.id, hp=user["hp"] + heal, gold=user["gold"] - 10)
    await callback.answer(f"❤️ +{heal} HP!")
    await cb_profile(callback)


@router.callback_query(F.data == "gem_energy")
async def cb_gem_energy(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    if user["gems"] < 3:
        return await callback.answer("💎 Нужно 3 гема!", show_alert=True)
    max_e = user["max_energy"] + (VIP_BENEFITS["max_energy_bonus"] if is_vip(user) else 0)
    if user["energy"] >= max_e:
        return await callback.answer("⚡ Энергия уже полная!")
    new_e = min(user["energy"] + 10, max_e)
    await update_user(callback.from_user.id, gems=user["gems"] - 3, energy=new_e,
                      last_energy=datetime.now().isoformat())
    await callback.answer("⚡ Энергия восстановлена!")
    await cb_profile(callback)


# ===================== ЕЖЕДНЕВНАЯ НАГРАДА =====================
@router.callback_query(F.data == "daily")
async def cb_daily(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    if user["daily_claimed"] == today:
        return await callback.answer("🎁 Уже забрал! Приходи завтра.", show_alert=True)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    streak = user["streak"] + 1 if user["daily_claimed"] == yesterday else 1
    gold = 20 + streak * 10
    gems = (1 if streak >= 3 else 0) + (VIP_BENEFITS["daily_gems"] if is_vip(user) else 0)
    energy_bonus = 3 if streak >= 5 else 0
    wheel_spin = 1 if streak >= 2 else 0
    max_e = user["max_energy"] + (VIP_BENEFITS["max_energy_bonus"] if is_vip(user) else 0)
    await update_user(callback.from_user.id, daily_claimed=today, streak=streak,
                      gold=user["gold"] + gold, gems=user["gems"] + gems,
                      total_gems_earned=user["total_gems_earned"] + gems,
                      energy=min(user["energy"] + energy_bonus, max_e),
                      wheel_spins=user["wheel_spins"] + wheel_spin)
    text = f"🎁 <b>Ежедневная награда!</b>\n🔥 Стрик: <b>{streak}</b>\n\n💰 +{gold}\n"
    if gems:
        text += f"💎 +{gems}\n"
    if energy_bonus:
        text += f"⚡ +{energy_bonus}\n"
    if wheel_spin:
        text += f"🎡 +{wheel_spin} вращение колеса!\n"
    text += "\n💡 Заходи каждый день!"
    ach_msg = await check_achievements(callback.from_user.id)
    if ach_msg:
        text += ach_msg
    kb = make_kb([[("🔙 Назад", "main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ===================== ПОДЗЕМЕЛЬЯ =====================
@router.callback_query(F.data == "dungeons")
async def cb_dungeons(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    if not user or not user["class"]:
        return await callback.answer("Создай персонажа!")
    await regen_energy(callback.from_user.id)
    user = await get_user(callback.from_user.id)
    max_e = user["max_energy"] + (VIP_BENEFITS["max_energy_bonus"] if is_vip(user) else 0)
    text = f"🗺️ <b>Подземелья</b>\n⚡ {user['energy']}/{max_e}\n\n"
    buttons = []
    for d_id, dungeon in DUNGEONS.items():
        locked = user["level"] < dungeon["min_lvl"]
        status = "🔒" if locked else "✅"
        text += f"{status} {dungeon['name']} (ур.{dungeon['min_lvl']}+)\n"
        if not locked:
            buttons.append([(f"{dungeon['name']}", f"enter_dungeon_{d_id}")])
    text += "\n⚡ Монстр=1, Босс=2, Элитный=3"
    buttons.append([("🔙 Назад", "main_menu")])
    await callback.message.edit_text(text, reply_markup=make_kb(buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("enter_dungeon_"))
async def cb_enter_dungeon(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    d_id = int(callback.data.replace("enter_dungeon_", ""))
    user = await get_user(callback.from_user.id)
    dungeon = DUNGEONS.get(d_id)
    if not dungeon or user["level"] < dungeon["min_lvl"]:
        return await callback.answer("🔒 Недоступно!")
    await regen_energy(callback.from_user.id)
    user = await get_user(callback.from_user.id)
    kb = make_kb([
        [("⚔️ Монстр (1⚡)", f"fight_monster_{d_id}")],
        [("👑 Босс (2⚡)", f"fight_boss_{d_id}")],
        [("🌟 Элитный (3⚡)", f"fight_elite_{d_id}")],
        [("🔙 К подземельям", "dungeons")],
    ])
    text = (f"🏰 <b>{dungeon['name']}</b>\n"
            f"⚡ {user['energy']} | ❤️ {user['hp']}/{user['max_hp']}\n\nМонстры:\n")
    for m in dungeon["monsters"]:
        text += f"  {m['name']} — ❤️{m['hp']} ⚔️{m['atk']}\n"
    text += f"\n👑 Босс: {dungeon['boss']['name']}"
    text += f"\n\n🌟 <i>Элитные монстры дают гемы!</i>"
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


async def do_battle(user_id: int, enemy: dict) -> tuple:
    user = await get_user(user_id)
    stats = calc_stats(user)
    mults = get_buff_multipliers(user)
    p_hp = user["hp"]
    e_hp = enemy["hp"]
    log = f"⚔️ <b>Бой с {enemy['name']}</b>\n{'━' * 20}\n"
    turn = 0
    while p_hp > 0 and e_hp > 0 and turn < 30:
        turn += 1
        is_crit = random.randint(1, 100) <= stats["crit"]
        dmg = max(1, stats["atk"] - random.randint(0, 3))
        if is_crit:
            dmg = int(dmg * 2)
            log += f"🎯 КРИТ! -{dmg}\n"
        else:
            log += f"⚔️ -{dmg}\n"
        e_hp -= dmg
        if e_hp <= 0:
            break
        e_dmg = max(1, enemy["atk"] - stats["def"] // 2 + random.randint(-2, 2))
        p_hp -= e_dmg
        log += f"{enemy['name']} -{e_dmg}\n"

    won = e_hp <= 0
    p_hp = max(0, p_hp)

    if not won and p_hp <= 0:
        inventory = json.loads(user["inventory"]) if user["inventory"] else {}
        if inventory.get("revive_stone", 0) > 0:
            inventory["revive_stone"] -= 1
            if inventory["revive_stone"] <= 0:
                del inventory["revive_stone"]
            p_hp = user["max_hp"] // 2
            won = True
            log += f"\n💎 <b>Камень воскрешения!</b> HP: {p_hp}\n"
            await update_user(user_id, inventory=json.dumps(inventory))

    final_hp = p_hp if won else max(1, p_hp)
    await update_user(user_id, hp=final_hp)

    if won:
        gold = int(max(0, enemy["gold"] + random.randint(-5, 10)) * mults["gold_mult"])
        xp = int(enemy["xp"] * mults["xp_mult"])
        gems_drop = enemy.get("gems", 0)
        gem_chance = 5 + mults["gem_luck"]
        if not gems_drop and random.randint(1, 100) <= gem_chance:
            gems_drop = 1

        user = await get_user(user_id)
        upd = {"gold": user["gold"] + gold, "total_gold_earned": user["total_gold_earned"] + gold}
        if gems_drop:
            upd["gems"] = user["gems"] + gems_drop
            upd["total_gems_earned"] = user["total_gems_earned"] + gems_drop
        await update_user(user_id, **upd)
        level_msg = await add_xp(user_id, xp)
        log += f"\n🏆 <b>Победа!</b>\n💰+{gold} ✨+{xp}"
        if gems_drop:
            log += f" 💎+{gems_drop}"
        log += level_msg

        user = await get_user(user_id)
        log += f"\n❤️ HP: {user['hp']}/{user['max_hp']}"

        # Уменьшаем длительность баффов
        buffs = json.loads(user["buffs"]) if user["buffs"] else []
        new_buffs = []
        for b in buffs:
            dur = b["effect"].get("duration", 0)
            if dur > 1:
                b["effect"]["duration"] = dur - 1
                new_buffs.append(b)
        await update_user(user_id, buffs=json.dumps(new_buffs))

        ach_msg = await check_achievements(user_id)
        if ach_msg:
            log += ach_msg
    else:
        log += f"\n💀 <b>Поражение...</b>\n❤️ HP: 1/{user['max_hp']}"

    return log, won


@router.callback_query(F.data.startswith("fight_monster_"))
async def cb_fight_monster(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    d_id = int(callback.data.replace("fight_monster_", ""))
    await regen_energy(callback.from_user.id)
    user = await get_user(callback.from_user.id)
    dungeon = DUNGEONS.get(d_id)
    if not dungeon:
        return await callback.answer("❌ Подземелье не найдено!")
    if user["energy"] < 1:
        return await callback.answer("⚡ Нет энергии!", show_alert=True)
    if user["hp"] <= 1:
        return await callback.answer("❤️ Мало HP! Вылечись.", show_alert=True)
    await update_user(callback.from_user.id, energy=user["energy"] - 1,
                      last_energy=datetime.now().isoformat())
    monster = random.choice(dungeon["monsters"])
    log, won = await do_battle(callback.from_user.id, monster)
    if won:
        u = await get_user(callback.from_user.id)
        await update_user(callback.from_user.id, dungeon_wins=u["dungeon_wins"] + 1)
    kb = make_kb([
        [("⚔️ Ещё", f"fight_monster_{d_id}"), ("👑 Босс", f"fight_boss_{d_id}")],
        [("🔙 Подземелья", "dungeons"), ("🏠 Меню", "main_menu")],
    ])
    await callback.message.edit_text(log, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("fight_boss_"))
async def cb_fight_boss(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    d_id = int(callback.data.replace("fight_boss_", ""))
    await regen_energy(callback.from_user.id)
    user = await get_user(callback.from_user.id)
    dungeon = DUNGEONS.get(d_id)
    if not dungeon:
        return await callback.answer("❌ Не найдено!")
    if user["energy"] < 2:
        return await callback.answer("⚡ Нужно 2 энергии!", show_alert=True)
    if user["hp"] <= 5:
        return await callback.answer("❤️ Мало HP!", show_alert=True)
    await update_user(callback.from_user.id, energy=user["energy"] - 2,
                      last_energy=datetime.now().isoformat())
    log, won = await do_battle(callback.from_user.id, dungeon["boss"])
    if won:
        u = await get_user(callback.from_user.id)
        await update_user(callback.from_user.id, boss_kills=u["boss_kills"] + 1)
        if random.randint(1, 100) <= 30:
            u = await get_user(callback.from_user.id)
            await update_user(callback.from_user.id, gems=u["gems"] + 2,
                              total_gems_earned=u["total_gems_earned"] + 2)
            log += "\n💎 <b>+2 гема из босса!</b>"
    kb = make_kb([
        [("⚔️ Монстр", f"fight_monster_{d_id}"), ("👑 Босс", f"fight_boss_{d_id}")],
        [("🔙 Подземелья", "dungeons")],
    ])
    await callback.message.edit_text(log, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("fight_elite_"))
async def cb_fight_elite(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    d_id = int(callback.data.replace("fight_elite_", ""))
    await regen_energy(callback.from_user.id)
    user = await get_user(callback.from_user.id)
    if user["energy"] < 3:
        return await callback.answer("⚡ Нужно 3 энергии!", show_alert=True)
    if user["hp"] <= 5:
        return await callback.answer("❤️ Мало HP!", show_alert=True)
    available = [m for m in ELITE_MONSTERS if user["level"] >= m["min_lvl"]]
    if not available:
        return await callback.answer("🌟 Нет доступных элитных монстров!", show_alert=True)
    await update_user(callback.from_user.id, energy=user["energy"] - 3,
                      last_energy=datetime.now().isoformat())
    elite = random.choice(available)
    log, won = await do_battle(callback.from_user.id, elite)
    if won:
        u = await get_user(callback.from_user.id)
        await update_user(callback.from_user.id, elite_kills=u["elite_kills"] + 1)
    kb = make_kb([
        [("⚔️ Монстр", f"fight_monster_{d_id}"), ("🌟 Ещё элитный", f"fight_elite_{d_id}")],
        [("🔙 Подземелья", "dungeons")],
    ])
    await callback.message.edit_text(log, reply_markup=kb)
    await callback.answer()


# ===================== PVP =====================
@router.callback_query(F.data == "pvp")
async def cb_pvp(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    if not user or not user["class"]:
        return await callback.answer("Создай персонажа!")
    text = (f"🏟️ <b>PvP Арена</b>\n\n⚔️ {user['wins']}W / {user['losses']}L\n"
            f"❤️ {user['hp']}/{user['max_hp']}\n⚡ Стоимость: 2 энергии\n"
            f"💰 Награда: 30-50 золота + шанс 💎")
    kb = make_kb([[("⚔️ Найти соперника!", "pvp_fight")], [("🔙 Назад", "main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "pvp_fight")
async def cb_pvp_fight(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user_id = callback.from_user.id
    await regen_energy(user_id)
    user = await get_user(user_id)
    if user["energy"] < 2:
        return await callback.answer("⚡ Нужно 2 энергии!", show_alert=True)
    if user["hp"] <= 5:
        return await callback.answer("❤️ Мало HP!", show_alert=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id != ? AND class != '' AND is_banned = 0 "
            "AND level BETWEEN ? AND ? ORDER BY RANDOM() LIMIT 1",
            (user_id, max(1, user["level"] - 3), user["level"] + 3)
        ) as cur:
            opp_row = await cur.fetchone()
    if not opp_row:
        opponent = {"name": random.choice(["🤖 Голем", "🧑‍🦱 Странник", "🧝 Эльф"]),
                    "hp": user["max_hp"], "atk": user["atk"] + random.randint(-3, 3),
                    "gold": 30, "xp": 20}
    else:
        o = dict(opp_row)
        os_stats = calc_stats(o)
        opponent = {"name": f"{CLASSES[o['class']]['emoji']} {o['username']}",
                    "hp": o["max_hp"], "atk": os_stats["atk"],
                    "gold": random.randint(30, 50), "xp": 25}
    await update_user(user_id, energy=user["energy"] - 2, last_energy=datetime.now().isoformat())
    log, won = await do_battle(user_id, opponent)
    u = await get_user(user_id)
    if won:
        await update_user(user_id, wins=u["wins"] + 1)
    else:
        await update_user(user_id, losses=u["losses"] + 1)
    kb = make_kb([[("⚔️ Ещё!", "pvp_fight")],
                  [("🔙 Арена", "pvp"), ("🏠 Меню", "main_menu")]])
    await callback.message.edit_text(log, reply_markup=kb)
    await callback.answer()


# ===================== МИНИ-ИГРЫ =====================
@router.callback_query(F.data == "games")
async def cb_games(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    text = ("🎰 <b>Мини-игры</b>\n\nИспытай удачу!\n\n"
            "🎲 Кости — угадай больше/меньше\n🎰 Слоты — крути барабан!\n"
            "🃏 Рулетка — красное/чёрное\n")
    kb = make_kb([
        [("🎲 Кости (10💰)", "game_dice"), ("🎰 Слоты (20💰)", "game_slots")],
        [("🃏 Рулетка (15💰)", "game_roulette")],
        [("🔙 Назад", "main_menu")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "game_dice")
async def cb_game_dice(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    if user["gold"] < 10:
        return await callback.answer("💰 Нужно 10 золота!", show_alert=True)
    kb = make_kb([
        [("⬆️ Больше 7 (x2)", "dice_high"), ("⬇️ Меньше 7 (x2)", "dice_low")],
        [("7️⃣ Ровно 7 (x5)", "dice_seven")],
        [("🔙 Назад", "games")],
    ])
    await callback.message.edit_text("🎲 <b>Кости</b>\n\nБросаю 2d6. Больше или меньше 7?",
                                     reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("dice_"))
async def cb_dice_result(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    if user["gold"] < 10:
        return await callback.answer("💰 Нужно 10 золота!", show_alert=True)
    bet = callback.data.replace("dice_", "")
    d1, d2 = random.randint(1, 6), random.randint(1, 6)
    total = d1 + d2
    won, mult = False, 0
    if bet == "high" and total > 7:
        won, mult = True, 2
    elif bet == "low" and total < 7:
        won, mult = True, 2
    elif bet == "seven" and total == 7:
        won, mult = True, 5
    winnings = 10 * mult if won else 0
    new_gold = user["gold"] - 10 + winnings
    await update_user(callback.from_user.id, gold=new_gold)
    result_text = f"🏆 +{winnings}💰" if won else "💀 -10💰"
    text = f"🎲 {d1} + {d2} = <b>{total}</b>\n\n{result_text}\n💰 {new_gold}"
    kb = make_kb([[("🎲 Ещё", "game_dice")],
                  [("🔙 Игры", "games"), ("🏠 Меню", "main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "game_slots")
async def cb_game_slots(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    if user["gold"] < 20:
        return await callback.answer("💰 Нужно 20 золота!", show_alert=True)
    weights = [30, 25, 20, 15, 5, 2, 10, 8]
    s1, s2, s3 = [random.choices(SLOT_SYMBOLS, weights=weights, k=1)[0] for _ in range(3)]
    payout = SLOT_PAYOUTS.get((s1, s2, s3), 0)
    winnings = payout * 20 if payout else (10 if s1 == s2 or s2 == s3 or s1 == s3 else 0)
    new_gold = user["gold"] - 20 + winnings
    await update_user(callback.from_user.id, gold=new_gold)
    jackpot = " 🔥🔥🔥" if payout and payout >= 20 else ""
    result_text = f"🏆 +{winnings}💰{jackpot}" if winnings else "💀 -20💰"
    text = (f"🎰 <b>С Л О Т Ы</b>\n\n╔═══════════╗\n║ {s1} {s2} {s3} ║\n"
            f"╚═══════════╝\n\n{result_text}\n💰 {new_gold}")
    kb = make_kb([[("🎰 Ещё!", "game_slots")],
                  [("🔙 Игры", "games"), ("🏠 Меню", "main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "game_roulette")
async def cb_game_roulette(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    kb = make_kb([
        [("🔴 Красное (x2)", "roul_red"), ("⚫ Чёрное (x2)", "roul_black")],
        [("🟢 Зеро (x10)", "roul_green")],
        [("🔙 Назад", "games")],
    ])
    await callback.message.edit_text("🃏 <b>Рулетка</b>\nСтавка: 15💰", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("roul_"))
async def cb_roulette_result(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    if user["gold"] < 15:
        return await callback.answer("💰 Нужно 15 золота!", show_alert=True)
    bet = callback.data.replace("roul_", "")
    r = random.randint(1, 100)
    result = "green" if r <= 3 else ("red" if r <= 51 else "black")
    names = {"green": "🟢 ЗЕРО!", "red": "🔴 Красное", "black": "⚫ Чёрное"}
    won = bet == result
    mult = {"red": 2, "black": 2, "green": 10}.get(bet, 0) if won else 0
    winnings = 15 * mult
    new_gold = user["gold"] - 15 + winnings
    await update_user(callback.from_user.id, gold=new_gold)
    result_text = f"🏆 +{winnings}💰" if won else "💀 -15💰"
    text = f"🃏 Результат: <b>{names[result]}</b>\n\n{result_text}\n💰 {new_gold}"
    kb = make_kb([[("🃏 Ещё", "game_roulette")],
                  [("🔙 Игры", "games"), ("🏠 Меню", "main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ===================== МАГАЗИН =====================
@router.callback_query(F.data == "shop")
async def cb_shop(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    text = f"🛒 <b>Магазин</b>\n💰 {user['gold']} | 💎 {user['gems']}\n\n"
    buttons = []
    cats = {"consumable": "🧪 Расходники", "buff": "📜 Свитки", "equipment": "🎽 Экипировка"}
    for cat, name in cats.items():
        items = [(k, v) for k, v in SHOP_ITEMS.items() if v["type"] == cat]
        if items:
            text += f"<b>{name}:</b>\n"
            for key, item in items:
                text += f"  {item['name']} — {item['price']}💰\n"
                buttons.append([(f"{item['name']} ({item['price']}💰)", f"buy_{key}")])
    buttons.append([("🔙 Назад", "main_menu")])
    await callback.message.edit_text(text, reply_markup=make_kb(buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("buy_"))
async def cb_buy_item(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    item_key = callback.data.replace("buy_", "")
    if item_key not in SHOP_ITEMS:
        return await callback.answer("❌ Не найдено")
    user = await get_user(callback.from_user.id)
    item = SHOP_ITEMS[item_key]
    if user["gold"] < item["price"]:
        return await callback.answer("💰 Не хватает!", show_alert=True)

    upd = {"gold": user["gold"] - item["price"]}

    if item["type"] == "consumable":
        inventory = json.loads(user["inventory"]) if user["inventory"] else {}
        if "hp" in item["effect"]:
            new_hp = min(user["hp"] + item["effect"]["hp"], user["max_hp"])
            upd["hp"] = new_hp
            await callback.answer(f"❤️ +{item['effect']['hp']} HP!")
        elif "revive" in item["effect"]:
            inventory[item_key] = inventory.get(item_key, 0) + 1
            upd["inventory"] = json.dumps(inventory)
            await callback.answer("✅ Камень воскрешения в инвентаре!")
        else:
            inventory[item_key] = inventory.get(item_key, 0) + 1
            upd["inventory"] = json.dumps(inventory)
            await callback.answer("✅ Добавлено!")
    elif item["type"] == "buff":
        buffs = json.loads(user["buffs"]) if user["buffs"] else []
        buffs.append({"name": item["name"], "effect": dict(item["effect"])})
        upd["buffs"] = json.dumps(buffs)
        await callback.answer("📜 Бафф активирован!")
    elif item["type"] == "equipment":
        equipment = json.loads(user["equipment"]) if user["equipment"] else {}
        old = equipment.get(item["slot"])
        if old:
            inventory = json.loads(user.get("inventory") or "{}")
            inventory[old] = inventory.get(old, 0) + 1
            upd["inventory"] = json.dumps(inventory)
        equipment[item["slot"]] = item_key
        upd["equipment"] = json.dumps(equipment)
        await callback.answer("🎽 Экипировано!", show_alert=True)

    await update_user(callback.from_user.id, **upd)
    await cb_shop(callback)


# ===================== ГЕМ-МАГАЗИН =====================
@router.callback_query(F.data == "gem_shop")
async def cb_gem_shop(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    text = f"💎 <b>Гем-магазин</b>\n💎 Кристаллов: {user['gems']}\n\n"
    buttons = []
    text += "<b>🎽 Мифическая экипировка:</b>\n"
    for key, item in GEM_SHOP_ITEMS.items():
        if item["type"] == "equipment":
            text += f"  {item['name']} — {item['price_gems']}💎\n  <i>{item['desc']}</i>\n"
            buttons.append([(f"{item['name']} ({item['price_gems']}💎)", f"gbuy_{key}")])
    text += "\n<b>📜 Баффы и расходники:</b>\n"
    for key, item in GEM_SHOP_ITEMS.items():
        if item["type"] != "equipment":
            text += f"  {item['name']} — {item['price_gems']}💎\n  <i>{item['desc']}</i>\n"
            buttons.append([(f"{item['name']} ({item['price_gems']}💎)", f"gbuy_{key}")])
    text += "\n<b>🎁 Сундуки с лутом:</b>\n"
    for key, chest in GEM_CHESTS.items():
        text += f"  {chest['name']} — {chest['price_gems']}💎\n"
        buttons.append([(f"{chest['name']} ({chest['price_gems']}💎)", f"chest_{key}")])
    text += "\n<b>💱 Обмен:</b>\n  💎1 гем = 💰50 золота\n"
    buttons.append([("💱 1💎 → 50💰", "gem_exchange_1"), ("💱 10💎 → 500💰", "gem_exchange_10")])
    buttons.append([("🔙 Назад", "main_menu")])
    await callback.message.edit_text(text, reply_markup=make_kb(buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("gbuy_"))
async def cb_gem_buy(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    key = callback.data.replace("gbuy_", "")
    if key not in GEM_SHOP_ITEMS:
        return await callback.answer("❌ Не найдено")
    user = await get_user(callback.from_user.id)
    item = GEM_SHOP_ITEMS[key]
    if user["gems"] < item["price_gems"]:
        return await callback.answer("💎 Не хватает гемов!", show_alert=True)

    upd = {"gems": user["gems"] - item["price_gems"]}

    if item["type"] == "equipment":
        equipment = json.loads(user["equipment"]) if user["equipment"] else {}
        old = equipment.get(item["slot"])
        if old:
            inventory = json.loads(user.get("inventory") or "{}")
            inventory[old] = inventory.get(old, 0) + 1
            upd["inventory"] = json.dumps(inventory)
        equipment[item["slot"]] = key
        upd["equipment"] = json.dumps(equipment)
        await callback.answer(f"🎽 {item['name']} экипировано!", show_alert=True)
    elif item["type"] == "buff":
        buffs = json.loads(user["buffs"]) if user["buffs"] else []
        buffs.append({"name": item["name"], "effect": dict(item["effect"])})
        upd["buffs"] = json.dumps(buffs)
        await callback.answer(f"📜 {item['name']} активирован!")
    elif item["type"] == "consumable":
        eff = item["effect"]
        if eff.get("full_heal"):
            upd["hp"] = user["max_hp"]
        if eff.get("full_energy"):
            max_e = user["max_energy"] + (VIP_BENEFITS["max_energy_bonus"] if is_vip(user) else 0)
            upd["energy"] = max_e
        if eff.get("energy"):
            max_e = user["max_energy"] + (VIP_BENEFITS["max_energy_bonus"] if is_vip(user) else 0)
            upd["energy"] = min(user["energy"] + eff["energy"], max_e)
        if eff.get("respec"):
            inv = json.loads(user["inventory"]) if user["inventory"] else {}
            inv["respec_token"] = inv.get("respec_token", 0) + 1
            upd["inventory"] = json.dumps(inv)
        if eff.get("max_energy_up"):
            upd["max_energy"] = user["max_energy"] + eff["max_energy_up"]
        await callback.answer(f"✅ {item['name']} использован!", show_alert=True)

    await update_user(callback.from_user.id, **upd)
    await cb_gem_shop(callback)


@router.callback_query(F.data.startswith("gem_exchange_"))
async def cb_gem_exchange(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    amount = int(callback.data.replace("gem_exchange_", ""))
    user = await get_user(callback.from_user.id)
    if user["gems"] < amount:
        return await callback.answer(f"💎 Нужно {amount} гемов!", show_alert=True)
    gold = amount * 50
    await update_user(callback.from_user.id, gems=user["gems"] - amount, gold=user["gold"] + gold)
    await callback.answer(f"💱 {amount}💎 → {gold}💰", show_alert=True)
    await cb_gem_shop(callback)


@router.callback_query(F.data.startswith("chest_"))
async def cb_open_chest(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    key = callback.data.replace("chest_", "")
    if key not in GEM_CHESTS:
        return await callback.answer("❌ Не найдено")
    user = await get_user(callback.from_user.id)
    chest = GEM_CHESTS[key]
    if user["gems"] < chest["price_gems"]:
        return await callback.answer(f"💎 Нужно {chest['price_gems']} гемов!", show_alert=True)
    await update_user(callback.from_user.id, gems=user["gems"] - chest["price_gems"],
                      chests_opened=user["chests_opened"] + 1)
    user = await get_user(callback.from_user.id)
    rewards = chest["rewards"]
    weights = [r["weight"] for r in rewards]
    reward = random.choices(rewards, weights=weights, k=1)[0]
    text = f"🎁 <b>Открываем {chest['name']}...</b>\n\n"
    if reward["type"] == "gold":
        amount = random.randint(reward["min"], reward["max"])
        await update_user(callback.from_user.id, gold=user["gold"] + amount,
                          total_gold_earned=user["total_gold_earned"] + amount)
        text += f"💰 <b>+{amount} золота!</b>"
    elif reward["type"] == "xp":
        amount = random.randint(reward["min"], reward["max"])
        lvl_msg = await add_xp(callback.from_user.id, amount)
        text += f"✨ <b>+{amount} опыта!</b>{lvl_msg}"
    elif reward["type"] == "gems":
        amount = random.randint(reward["min"], reward["max"])
        await update_user(callback.from_user.id, gems=user["gems"] + amount,
                          total_gems_earned=user["total_gems_earned"] + amount)
        text += f"💎 <b>+{amount} гемов!</b>"
    elif reward["type"] == "item":
        item_key2 = random.choice(reward["items"])
        item = SHOP_ITEMS.get(item_key2)
        if item:
            inv = json.loads(user["inventory"]) if user["inventory"] else {}
            inv[item_key2] = inv.get(item_key2, 0) + 1
            await update_user(callback.from_user.id, inventory=json.dumps(inv))
            text += f"📦 <b>{item['name']}!</b>"
    elif reward["type"] == "gem_item":
        item_key2 = random.choice(reward["items"])
        item = GEM_SHOP_ITEMS.get(item_key2)
        if item:
            equipment = json.loads(user["equipment"]) if user["equipment"] else {}
            equipment[item["slot"]] = item_key2
            await update_user(callback.from_user.id, equipment=json.dumps(equipment))
            text += f"⚡ <b>{item['name']}!</b> 🔥 РЕДКИЙ ДРОП!"
    elif reward["type"] == "vip_days":
        days = random.randint(reward["min"], reward["max"])
        vip_end = get_vip_end(user) + timedelta(days=days)
        await update_user(callback.from_user.id, vip_until=vip_end.isoformat())
        text += f"👑 <b>VIP на {days} дней!</b>"
    kb = make_kb([[("🎁 Ещё сундук", f"chest_{key}")], [("🔙 Гем-магазин", "gem_shop")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ===================== КРАФТ =====================
@router.callback_query(F.data == "craft")
async def cb_craft(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    inventory = json.loads(user["inventory"]) if user["inventory"] else {}
    equipment = json.loads(user["equipment"]) if user["equipment"] else {}
    text = f"🔨 <b>Мастерская крафта</b>\n💰 {user['gold']} | 💎 {user['gems']}\n\n"
    buttons = []
    for key, recipe in CRAFT_RECIPES.items():
        text += f"<b>{recipe['name']}</b> — {recipe['desc']}\n  Нужно: "
        parts = []
        can_craft = True
        for ing_key, count in recipe["ingredients"].items():
            item = SHOP_ITEMS.get(ing_key) or GEM_SHOP_ITEMS.get(ing_key)
            have = inventory.get(ing_key, 0)
            for slot, eq_key in equipment.items():
                if eq_key == ing_key:
                    have += 1
            if have < count:
                can_craft = False
            name = item["name"] if item else ing_key
            parts.append(f"{name} x{count}")
        if recipe["cost_gold"]:
            parts.append(f"{recipe['cost_gold']}💰")
            if user["gold"] < recipe["cost_gold"]:
                can_craft = False
        if recipe["cost_gems"]:
            parts.append(f"{recipe['cost_gems']}💎")
            if user["gems"] < recipe["cost_gems"]:
                can_craft = False
        text += ", ".join(parts) + f" {'✅' if can_craft else '❌'}\n\n"
        if can_craft:
            buttons.append([(f"🔨 {recipe['name']}", f"docraft_{key}")])
    if not buttons:
        text += "❌ <i>Недостаточно материалов</i>\n"
    buttons.append([("🔙 Назад", "main_menu")])
    await callback.message.edit_text(text, reply_markup=make_kb(buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("docraft_"))
async def cb_docraft(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    key = callback.data.replace("docraft_", "")
    if key not in CRAFT_RECIPES:
        return await callback.answer("❌ Рецепт не найден")
    user = await get_user(callback.from_user.id)
    recipe = CRAFT_RECIPES[key]
    inventory = json.loads(user["inventory"]) if user["inventory"] else {}
    equipment = json.loads(user["equipment"]) if user["equipment"] else {}

    if user["gold"] < recipe["cost_gold"] or user["gems"] < recipe["cost_gems"]:
        return await callback.answer("❌ Не хватает ресурсов!", show_alert=True)

    for ing_key, count in recipe["ingredients"].items():
        have = inventory.get(ing_key, 0)
        for slot, eq_key in equipment.items():
            if eq_key == ing_key:
                have += 1
        if have < count:
            return await callback.answer("❌ Не хватает ингредиентов!", show_alert=True)

    for ing_key, count in recipe["ingredients"].items():
        remaining = count
        if ing_key in inventory:
            take = min(inventory[ing_key], remaining)
            inventory[ing_key] -= take
            remaining -= take
            if inventory[ing_key] <= 0:
                del inventory[ing_key]
        if remaining > 0:
            for slot in list(equipment.keys()):
                if equipment.get(slot) == ing_key and remaining > 0:
                    del equipment[slot]
                    remaining -= 1

    upd = {"gold": user["gold"] - recipe["cost_gold"],
           "gems": user["gems"] - recipe["cost_gems"],
           "inventory": json.dumps(inventory),
           "crafts_done": user["crafts_done"] + 1}

    if recipe["result_type"] == "equipment":
        equipment[recipe["slot"]] = key
        upd["equipment"] = json.dumps(equipment)
    elif recipe["result_type"] == "consumable":
        if "hp" in recipe["effect"]:
            upd["hp"] = min(user["hp"] + recipe["effect"]["hp"], user["max_hp"])
        upd["equipment"] = json.dumps(equipment)

    await update_user(callback.from_user.id, **upd)
    await callback.answer(f"🔨 Скрафтил {recipe['name']}!", show_alert=True)
    await cb_craft(callback)


# ===================== ЭКСПЕДИЦИИ =====================
@router.callback_query(F.data == "expeditions")
async def cb_expeditions(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    text = "🎯 <b>Экспедиции</b>\n<i>Отправь героя на задание!</i>\n\n"
    if user.get("expedition") and user.get("expedition_start"):
        exp = EXPEDITIONS.get(user["expedition"])
        if exp:
            start = datetime.fromisoformat(user["expedition_start"])
            duration = exp["duration_min"] * (VIP_BENEFITS["expedition_speed"] if is_vip(user) else 1)
            end = start + timedelta(minutes=duration)
            now = datetime.now()
            if now >= end:
                text += f"✅ <b>{exp['name']}</b> — ЗАВЕРШЕНА!\n"
                kb = make_kb([[("🎁 Забрать награду!", "exp_collect")],
                              [("🔙 Назад", "main_menu")]])
            else:
                mins = int((end - now).total_seconds() / 60)
                text += f"⏳ <b>{exp['name']}</b> — в процессе\n⏰ Осталось: {mins} мин.\n"
                kb = make_kb([[("🔙 Назад", "main_menu")]])
            await callback.message.edit_text(text, reply_markup=kb)
            return await callback.answer()
    buttons = []
    for key, exp in EXPEDITIONS.items():
        min_lvl = exp.get("min_lvl", 1)
        locked = user["level"] < min_lvl
        dur = int(exp["duration_min"] * (VIP_BENEFITS["expedition_speed"] if is_vip(user) else 1))
        gold_range = f"{exp['gold'][0]}-{exp['gold'][1]}"
        text += (f"{'🔒' if locked else '✅'} <b>{exp['name']}</b> ({dur} мин)\n"
                 f"  💰{gold_range} | 💎 {exp['gem_chance']}%\n")
        if not locked:
            buttons.append([(f"{exp['name']} ({dur}мин)", f"exp_start_{key}")])
    buttons.append([("🔙 Назад", "main_menu")])
    await callback.message.edit_text(text, reply_markup=make_kb(buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("exp_start_"))
async def cb_exp_start(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    key = callback.data.replace("exp_start_", "")
    if key not in EXPEDITIONS:
        return await callback.answer("❌ Не найдено")
    user = await get_user(callback.from_user.id)
    if user.get("expedition"):
        return await callback.answer("⏳ У тебя уже есть экспедиция!", show_alert=True)
    await update_user(callback.from_user.id, expedition=key,
                      expedition_start=datetime.now().isoformat())
    dur = int(EXPEDITIONS[key]["duration_min"] *
              (VIP_BENEFITS["expedition_speed"] if is_vip(user) else 1))
    await callback.answer(f"🎯 Начата! Жди {dur} мин.", show_alert=True)
    await cb_expeditions(callback)


@router.callback_query(F.data == "exp_collect")
async def cb_exp_collect(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    exp = EXPEDITIONS.get(user.get("expedition", ""))
    if not exp:
        await update_user(callback.from_user.id, expedition="", expedition_start="")
        return await callback.answer("❌ Нет экспедиции!")
    mults = get_buff_multipliers(user)
    gold = int(random.randint(*exp["gold"]) * mults["gold_mult"])
    xp = int(random.randint(*exp["xp"]) * mults["xp_mult"])
    gems = 1 if random.randint(1, 100) <= exp["gem_chance"] else 0
    upd = {"expedition": "", "expedition_start": "",
           "gold": user["gold"] + gold,
           "total_gold_earned": user["total_gold_earned"] + gold}
    if gems:
        upd["gems"] = user["gems"] + gems
        upd["total_gems_earned"] = user["total_gems_earned"] + gems
    await update_user(callback.from_user.id, **upd)
    lvl_msg = await add_xp(callback.from_user.id, xp)
    text = f"🎯 <b>{exp['name']} — завершена!</b>\n\n💰+{gold} ✨+{xp}"
    if gems:
        text += f" 💎+{gems}"
    text += lvl_msg
    kb = make_kb([[("🎯 Новая экспедиция", "expeditions")], [("🏠 Меню", "main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ===================== КОЛЕСО ФОРТУНЫ =====================
@router.callback_query(F.data == "wheel")
async def cb_wheel(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    free_spin = user.get("last_wheel", "") != today
    text = (f"🎡 <b>Колесо Фортуны</b>\n\n🎟️ Вращений: {user['wheel_spins']}\n"
            f"{'✅ Бесплатное доступно!' if free_spin else '❌ Бесплатное использовано'}\n")
    buttons = []
    if free_spin:
        buttons.append([("🎡 Бесплатное!", "spin_free")])
    if user["wheel_spins"] > 0:
        buttons.append([(f"🎡 Токен ({user['wheel_spins']})", "spin_token")])
    buttons.append([("🎡 За 5💎", "spin_gems")])
    buttons.append([("🔙 Назад", "main_menu")])
    await callback.message.edit_text(text, reply_markup=make_kb(buttons))
    await callback.answer()


async def do_spin(callback: CallbackQuery):
    user = await get_user(callback.from_user.id)
    weights = [s["weight"] for s in WHEEL_SEGMENTS]
    seg = random.choices(WHEEL_SEGMENTS, weights=weights, k=1)[0]
    text = f"🎡 <b>Колесо крутится...</b>\n\n➡️ {seg['color']} <b>{seg['name']}</b>\n\n"
    if seg["type"] == "gold":
        await update_user(callback.from_user.id, gold=user["gold"] + seg["amount"],
                          total_gold_earned=user["total_gold_earned"] + seg["amount"])
        text += f"💰 +{seg['amount']}!"
    elif seg["type"] == "gems":
        await update_user(callback.from_user.id, gems=user["gems"] + seg["amount"],
                          total_gems_earned=user["total_gems_earned"] + seg["amount"])
        text += f"💎 +{seg['amount']}!"
    elif seg["type"] == "xp":
        lvl_msg = await add_xp(callback.from_user.id, seg["amount"])
        text += f"✨ +{seg['amount']}!{lvl_msg}"
    elif seg["type"] == "energy":
        max_e = user["max_energy"] + (VIP_BENEFITS["max_energy_bonus"] if is_vip(user) else 0)
        await update_user(callback.from_user.id,
                          energy=min(user["energy"] + seg["amount"], max_e))
        text += f"⚡ +{seg['amount']}!"
    elif seg["type"] == "heal":
        await update_user(callback.from_user.id, hp=user["max_hp"])
        text += "❤️ Полное исцеление!"
    elif seg["type"] == "nothing":
        text += "💀 Не повезло..."
    elif seg["type"] == "double":
        bg = random.randint(100, 500)
        bge = random.randint(1, 5)
        await update_user(callback.from_user.id, gold=user["gold"] + bg, gems=user["gems"] + bge,
                          total_gold_earned=user["total_gold_earned"] + bg,
                          total_gems_earned=user["total_gems_earned"] + bge)
        text += f"🌈 ДЖЕКПОТ! +{bg}💰 +{bge}💎!"
    kb = make_kb([[("🎡 Ещё", "wheel")], [("🏠 Меню", "main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "spin_free")
async def cb_spin_free(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    today = datetime.now().strftime("%Y-%m-%d")
    if user.get("last_wheel", "") == today:
        return await callback.answer("❌ Уже использовано!", show_alert=True)
    await update_user(callback.from_user.id, last_wheel=today)
    await do_spin(callback)
    await callback.answer()


@router.callback_query(F.data == "spin_token")
async def cb_spin_token(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    if user["wheel_spins"] <= 0:
        return await callback.answer("🎟️ Нет вращений!", show_alert=True)
    await update_user(callback.from_user.id, wheel_spins=user["wheel_spins"] - 1)
    await do_spin(callback)
    await callback.answer()


@router.callback_query(F.data == "spin_gems")
async def cb_spin_gems(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    if user["gems"] < 5:
        return await callback.answer("💎 Нужно 5 гемов!", show_alert=True)
    await update_user(callback.from_user.id, gems=user["gems"] - 5)
    await do_spin(callback)
    await callback.answer()


# ===================== ДОСТИЖЕНИЯ =====================
@router.callback_query(F.data == "achievements")
async def cb_achievements(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    unlocked = json.loads(user["achievements"]) if user["achievements"] else []
    text = f"🏆 <b>Достижения</b> ({len(unlocked)}/{len(ACHIEVEMENTS)})\n\n"
    for key, ach in ACHIEVEMENTS.items():
        done = key in unlocked
        val = user.get(ach["check"], 0)
        progress = min(val, ach["value"])
        status = "✅" if done else f"({progress}/{ach['value']})"
        text += f"{'✅' if done else '⬜'} <b>{ach['name']}</b> {status}\n"
        text += f"  <i>{ach['desc']}</i> — {ach['reward_gold']}💰 {ach['reward_gems']}💎\n"
    kb = make_kb([[("🔙 Назад", "main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ===================== ИНВЕНТАРЬ =====================
@router.callback_query(F.data == "inventory")
async def cb_inventory(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    inventory = json.loads(user["inventory"]) if user["inventory"] else {}
    equipment = json.loads(user["equipment"]) if user["equipment"] else {}
    buffs = json.loads(user["buffs"]) if user["buffs"] else []
    text = "📦 <b>Инвентарь</b>\n\n🎽 <b>Экипировка:</b>\n"
    if equipment:
        for slot, item_key in equipment.items():
            item = (SHOP_ITEMS.get(item_key) or GEM_SHOP_ITEMS.get(item_key)
                    or CRAFT_RECIPES.get(item_key))
            text += f"  [{slot}] {item['name'] if item else item_key}\n"
    else:
        text += "  Пусто\n"
    text += "\n🧪 <b>Предметы:</b>\n"
    has = False
    for ik, cnt in inventory.items():
        item = SHOP_ITEMS.get(ik) or GEM_SHOP_ITEMS.get(ik)
        if item and cnt > 0:
            text += f"  {item['name']} x{cnt}\n"
            has = True
    if not has:
        text += "  Пусто\n"
    text += "\n📜 <b>Баффы:</b>\n"
    if buffs:
        for b in buffs:
            text += f"  {b['name']} ({b['effect'].get('duration', 0)} боёв)\n"
    else:
        text += "  Нет баффов\n"
    kb = make_kb([[("🔙 Назад", "main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ===================== РЕЙТИНГ =====================
@router.callback_query(F.data == "leaderboard")
async def cb_leaderboard(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    kb = make_kb([
        [("📊 По уровню", "top_level"), ("⚔️ По PvP", "top_pvp")],
        [("💰 По золоту", "top_gold"), ("👑 По боссам", "top_bosses")],
        [("💎 По гемам", "top_gems"), ("🌟 По элитам", "top_elites")],
        [("🔙 Назад", "main_menu")],
    ])
    await callback.message.edit_text("🏆 <b>Рейтинг</b>\nВыбери категорию:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("top_"))
async def cb_top(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    cat = callback.data.replace("top_", "")
    order_map = {
        "level": ("level", "📊 По уровню"),
        "pvp": ("wins", "⚔️ PvP"),
        "gold": ("gold", "💰 По золоту"),
        "bosses": ("boss_kills", "👑 Боссы"),
        "gems": ("total_gems_earned", "💎 По гемам"),
        "elites": ("elite_kills", "🌟 Элиты"),
    }
    order_by, title = order_map.get(cat, ("level", "Рейтинг"))
    players = await get_top_players(order_by)
    medals = ["🥇", "🥈", "🥉"]
    text = f"🏆 <b>{title}</b>\n{'━' * 25}\n\n"
    for i, p in enumerate(players):
        medal = medals[i] if i < 3 else f"{i + 1}."
        cls = CLASSES.get(p["class"], {})
        vip = "👑" if is_vip(p) else ""
        text += f"{medal} {cls.get('emoji', '')} {p['username']} {vip} — {p[order_by]}\n"
    if not players:
        text += "Пока никого нет.\n"
    kb = make_kb([[("🔙 Рейтинг", "leaderboard")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ===================== СТАТИСТИКА МИРА =====================
@router.callback_query(F.data == "world_stats")
async def cb_world_stats(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    stats = await get_global_stats()
    text = (
        f"📊 <b>Статистика мира Dungeon Master</b>\n{'━' * 30}\n\n"
        f"👥 Всего героев: <b>{stats['total_players']}</b>\n"
        f"🕐 Активных за 24ч: <b>{stats['active_24h']}</b>\n"
        f"📊 Средний уровень: <b>{stats['avg_level']}</b>\n"
        f"🏆 Макс. уровень: <b>{stats['max_level']}</b>\n\n"
        f"<b>⚔️ Боевая статистика:</b>\n"
        f"  🗡️ Боёв: {stats['total_fights']:,}\n"
        f"  👑 Боссов: {stats['total_bosses']:,}\n"
        f"  🌟 Элитных: {stats['total_elites']:,}\n"
        f"  ⚔️ PvP: {stats['total_pvp']:,}\n\n"
        f"<b>💰 Экономика:</b>\n"
        f"  💰 Золота: {stats['total_gold']:,}\n"
        f"  💎 Гемов: {stats['total_gems']:,}\n"
        f"  🎁 Сундуков: {stats['total_chests']:,}\n"
        f"  🔨 Крафтов: {stats['total_crafts']:,}\n\n"
        f"<b>📊 Классы:</b>\n"
    )
    total = max(stats["total_players"], 1)
    for cls_key, cls in CLASSES.items():
        count = stats.get(f"class_{cls_key}", 0)
        pct = round(count / total * 100)
        bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
        text += f"  {cls['emoji']} {cls['name']}: {count} ({pct}%)\n  {bar}\n"
    kb = make_kb([[("🔙 Назад", "main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ===================== РЕФЕРАЛ =====================
@router.callback_query(F.data == "referral")
async def cb_referral(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    me = await bot.get_me()
    ref_link = f"https://t.me/{me.username}?start={callback.from_user.id}"
    text = (f"🔗 <b>Реферальная программа</b>\n\n"
            f"Приглашай друзей: <b>+50💰 +2💎</b>\n\n"
            f"👥 Приглашено: <b>{user['referral_count']}</b>\n"
            f"💰 Заработано: {user['referral_count'] * 50}💰 + {user['referral_count'] * 2}💎\n\n"
            f"🔗 Ссылка:\n<code>{ref_link}</code>")
    kb = make_kb([[("🔙 Назад", "main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# ===================== ДОНАТ-МАГАЗИН =====================
@router.callback_query(F.data == "donate_shop")
async def cb_donate_shop(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    user = await get_user(callback.from_user.id)
    vip_text = "👑 VIP активен!" if is_vip(user) else ""
    text = (f"💳 <b>Донат-магазин</b> {vip_text}\n"
            f"💰{user['gold']} | 💎{user['gems']}\n"
            f"Оплата через <b>Crypto Pay</b>\n{'━' * 25}\n\n")
    buttons = []
    for key, item in DONATE_ITEMS.items():
        rewards = []
        if item.get("gold"):
            rewards.append(f"{item['gold']}💰")
        if item.get("gems"):
            rewards.append(f"{item['gems']}💎")
        if item.get("vip_days"):
            rewards.append(f"👑{item['vip_days']}д")
        text += f"  {item['name']} — <b>${item['price_usd']}</b>\n  {' + '.join(rewards)}\n"
        buttons.append([(f"{item['name']} (${item['price_usd']})", f"donate_buy_{key}")])
    buttons.append([("🔙 Назад", "main_menu")])
    await callback.message.edit_text(text, reply_markup=make_kb(buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("donate_buy_"))
async def cb_donate_buy(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    item_key = callback.data.replace("donate_buy_", "")
    if item_key not in DONATE_ITEMS:
        return await callback.answer("❌ Не найдено")
    item = DONATE_ITEMS[item_key]
    user_id = callback.from_user.id
    payload = json.dumps({"user_id": user_id, "item": item_key, "ts": int(time.time())})
    desc = f"Dungeon Master: {item['name']}"
    await callback.answer("⏳ Создаю счёт...")
    invoice = await crypto_create_invoice(item["price_usd"], desc, payload)
    if not invoice:
        return await callback.message.edit_text(
            "❌ Ошибка создания счёта. Попробуй позже.\n\n"
            "<i>Убедитесь, что CRYPTO_PAY_TOKEN задан в .env</i>",
            reply_markup=make_kb([[("🔙 Назад", "donate_shop")]]))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO payments (user_id, invoice_id, item_key, amount_usd, created_at) "
            "VALUES (?,?,?,?,?)",
            (user_id, invoice["invoice_id"], item_key, item["price_usd"],
             datetime.now().isoformat()))
        await db.commit()
    pay_url = invoice.get("pay_url") or invoice.get("mini_app_invoice_url", "")
    text = (f"💳 <b>Счёт создан!</b>\n\n"
            f"📦 {item['name']}\n💵 ${item['price_usd']}\n\n"
            f"Оплати и нажми «Проверить».")
    kb = make_kb([
        [("💳 Оплатить", pay_url)],
        [("✅ Проверить оплату", f"check_payment_{invoice['invoice_id']}")],
        [("🔙 Назад", "donate_shop")],
    ])
    await callback.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("check_payment_"))
async def cb_check_payment(callback: CallbackQuery):
    fire_hiviews_callback(callback)
    invoice_id = callback.data.replace("check_payment_", "")
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM payments WHERE invoice_id = ? AND user_id = ?",
                              (int(invoice_id), user_id)) as cur:
            payment = await cur.fetchone()
    if not payment:
        return await callback.answer("❌ Не найден")
    payment = dict(payment)
    if payment["status"] == "paid":
        return await callback.answer("✅ Уже обработан!", show_alert=True)
    invoices = await crypto_get_invoices(invoice_id)
    if not invoices:
        return await callback.answer("⏳ Попробуй позже.", show_alert=True)
    inv = invoices[0]
    if inv.get("status") == "paid":
        item = DONATE_ITEMS.get(payment["item_key"])
        if item:
            user = await get_user(user_id)
            upd = {
                "gold": user["gold"] + item.get("gold", 0),
                "gems": user["gems"] + item.get("gems", 0),
                "total_spent_usd": user["total_spent_usd"] + item["price_usd"],
            }
            if item.get("gems"):
                upd["total_gems_earned"] = user["total_gems_earned"] + item["gems"]
            if item.get("vip_days"):
                upd["vip_until"] = (get_vip_end(user) + timedelta(days=item["vip_days"])).isoformat()
            await update_user(user_id, **upd)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("UPDATE payments SET status='paid', paid_at=? WHERE invoice_id=?",
                                 (datetime.now().isoformat(), int(invoice_id)))
                await db.commit()
            rewards = []
            if item.get("gold"):
                rewards.append(f"+{item['gold']}💰")
            if item.get("gems"):
                rewards.append(f"+{item['gems']}💎")
            if item.get("vip_days"):
                rewards.append(f"👑VIP {item['vip_days']}д")
            text = (f"✅ <b>Оплата получена!</b>\n\n"
                    f"📦 {item['name']}\n{' '.join(rewards)}\n\nСпасибо! 🐉")
            kb = make_kb([[("🔙 Меню", "main_menu")]])
            await callback.message.edit_text(text, reply_markup=kb)
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(
                        admin_id,
                        f"💰 <b>Платёж!</b>\n👤 {user['username']} (ID:{user_id})\n"
                        f"📦 {item['name']} — ${item['price_usd']}")
                except Exception:
                    pass
    elif inv.get("status") == "expired":
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("UPDATE payments SET status='expired' WHERE invoice_id=?",
                             (int(invoice_id),))
            await db.commit()
        await callback.answer("⏰ Истёк. Создай новый.", show_alert=True)
    else:
        await callback.answer("⏳ Ожидание оплаты...", show_alert=True)


# ===================== ПРОМОКОДЫ =====================
@router.message(Command("promo"))
async def cmd_promo(message: Message):
    fire_hiviews_message(message)
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("Формат: /promo КОД")
    code = args[1].upper()
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        return await message.answer("Сначала /start")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM promo_codes WHERE code = ?", (code,)) as cur:
            promo = await cur.fetchone()
        if not promo:
            return await message.answer("❌ Не найден!")
        promo = dict(promo)
        if promo["used_count"] >= promo["max_uses"]:
            return await message.answer("❌ Промокод исчерпан!")
        async with db.execute("SELECT * FROM promo_uses WHERE user_id=? AND code=?",
                              (user_id, code)) as cur:
            if await cur.fetchone():
                return await message.answer("❌ Уже использован!")
        await db.execute("INSERT INTO promo_uses VALUES (?,?)", (user_id, code))
        await db.execute("UPDATE promo_codes SET used_count=used_count+1 WHERE code=?", (code,))
        await db.commit()
    await update_user(user_id, gold=user["gold"] + promo["gold"],
                      gems=user["gems"] + promo["gems"],
                      total_gems_earned=user["total_gems_earned"] + promo["gems"])
    r = []
    if promo["gold"]:
        r.append(f"+{promo['gold']}💰")
    if promo["gems"]:
        r.append(f"+{promo['gems']}💎")
    await message.answer(f"🎉 Промокод <b>{code}</b>: {' '.join(r)}")


# ===================== КНОПОЧНАЯ АДМИН-ПАНЕЛЬ =====================
@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    fire_hiviews_message(message)
    await show_admin_panel(message)


async def show_admin_panel(target, edit=False):
    total_users = await get_all_users_count()
    total_revenue = await get_total_revenue()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM payments WHERE status='paid'") as c:
            total_payments = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?",
                              ((datetime.now() - timedelta(days=1)).isoformat(),)) as c:
            new_today = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE class != ''") as c:
            active = (await c.fetchone())[0]
        async with db.execute("SELECT COALESCE(AVG(level),0) FROM users WHERE class!=''") as c:
            avg_lvl = round((await c.fetchone())[0], 1)
        day_ago = (datetime.now() - timedelta(days=1)).isoformat()
        async with db.execute("SELECT COUNT(*) FROM users WHERE last_energy >= ?", (day_ago,)) as c:
            dau = (await c.fetchone())[0]
    arpu = total_revenue / total_payments if total_payments else 0
    text = (
        f"👑 <b>АДМИН-ПАНЕЛЬ</b>\n{'━' * 28}\n\n"
        f"👥 Игроков: <b>{total_users}</b> (активных: {active})\n"
        f"🆕 Новых за 24ч: <b>{new_today}</b>\n"
        f"📅 DAU: <b>{dau}</b>\n"
        f"📊 Средний ур.: <b>{avg_lvl}</b>\n{'━' * 28}\n"
        f"💰 Доход: <b>${total_revenue:.2f}</b>\n"
        f"💳 Платежей: <b>{total_payments}</b>\n"
        f"📈 ARPU: <b>${arpu:.2f}</b>\n"
    )
    kb = make_kb([
        [("📊 Доход по дням", "adm_revenue"), ("👥 Топ донатеров", "adm_top_don")],
        [("📈 Подробная стата", "adm_stats"), ("🏆 Топ игроков", "adm_top_players")],
        [("🎫 Промокоды", "adm_promo"), ("📢 Рассылка", "adm_broadcast")],
        [("💰 Выдать ресурсы", "adm_give"), ("🔨 Бан/Разбан", "adm_ban")],
        [("🔍 Найти игрока", "adm_find"), ("⚙️ Система", "adm_system")],
    ])
    if edit and hasattr(target, 'edit_text'):
        await target.edit_text(text, reply_markup=kb)
    elif hasattr(target, 'answer'):
        await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "adm_panel")
async def cb_adm_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    await show_admin_panel(callback.message, edit=True)
    await callback.answer()


@router.callback_query(F.data == "adm_revenue")
async def cb_adm_revenue(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT date(paid_at) as day, SUM(amount_usd) as total, COUNT(*) as cnt "
            "FROM payments WHERE status='paid' AND paid_at >= ? "
            "GROUP BY day ORDER BY day",
            ((datetime.now() - timedelta(days=7)).isoformat(),)
        ) as cur:
            rows = await cur.fetchall()
    text = "📊 <b>Доход за 7 дней:</b>\n\n"
    total = 0
    for r in rows:
        text += f"📅 {r['day']}: <b>${r['total']:.2f}</b> ({r['cnt']})\n"
        total += r['total']
    if rows:
        text += f"\n💰 Итого: <b>${total:.2f}</b>"
    else:
        text += "Нет данных.\n"
    kb = make_kb([[("🔙 Панель", "adm_panel")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "adm_top_don")
async def cb_adm_top_don(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT username, user_id, total_spent_usd FROM users "
            "WHERE total_spent_usd > 0 ORDER BY total_spent_usd DESC LIMIT 10"
        ) as cur:
            top = await cur.fetchall()
    text = "👥 <b>Топ донатеров:</b>\n\n"
    for i, r in enumerate(top, 1):
        text += f"{i}. {r['username']} (ID:{r['user_id']}) — <b>${r['total_spent_usd']:.2f}</b>\n"
    if not top:
        text += "Нет данных.\n"
    kb = make_kb([[("🔙 Панель", "adm_panel")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "adm_stats")
async def cb_adm_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    stats = await get_global_stats()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COALESCE(SUM(total_spent_usd),0) FROM users") as c:
            revenue = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE total_spent_usd > 0") as c:
            paying = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM users WHERE vip_until > ?",
                              (datetime.now().isoformat(),)) as c:
            vip_count = (await c.fetchone())[0]
    arpu = revenue / paying if paying else 0
    text = (
        f"📈 <b>Подробная статистика</b>\n{'━' * 28}\n\n"
        f"👥 Всего: {stats['total_players']} | DAU: {stats['active_24h']}\n"
        f"👑 VIP: {vip_count}\n{'━' * 28}\n"
        f"💰 ${revenue:.2f} | 💳 {paying} | ARPU: ${arpu:.2f}\n{'━' * 28}\n"
        f"⚔️ {stats['total_fights']} | 👑 {stats['total_bosses']} | "
        f"🌟 {stats['total_elites']} | PvP {stats['total_pvp']}\n"
        f"🎁 {stats['total_chests']} | 🔨 {stats['total_crafts']}\n"
    )
    kb = make_kb([[("🔙 Панель", "adm_panel")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "adm_top_players")
async def cb_adm_top_players(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    players = await get_top_players("level", 15)
    text = "🏆 <b>Топ-15:</b>\n\n"
    for i, p in enumerate(players, 1):
        cls = CLASSES.get(p["class"], {})
        text += (f"{i}. {cls.get('emoji', '')} {p['username']} — "
                 f"ур.{p['level']} 💰{p['gold']} 💎{p['gems']}\n")
    kb = make_kb([[("🔙 Панель", "adm_panel")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.in_({"adm_promo", "adm_broadcast", "adm_give", "adm_ban", "adm_find"}))
async def cb_adm_text_cmds(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    info = {
        "adm_promo": ("🎫 <b>Промокоды</b>\n\n"
                      "<code>/addpromo КОД ЗОЛОТО ГЕМЫ МАКС</code>\n"
                      "Пример: <code>/addpromo NEWYEAR 100 10 50</code>"),
        "adm_broadcast": "📢 <b>Рассылка</b>\n\n<code>/broadcast Текст</code>",
        "adm_give": ("💰 <b>Ресурсы</b>\n\n"
                     "<code>/give USER_ID gold/gems КОЛ-ВО</code>\n"
                     "<code>/givevip USER_ID ДНЕЙ</code>"),
        "adm_ban": "🔨 <b>Бан</b>\n\n<code>/ban USER_ID</code>\n<code>/unban USER_ID</code>",
        "adm_find": "🔍 <b>Поиск</b>\n\n<code>/find USER_ID</code>",
    }
    text = info[callback.data]
    if callback.data == "adm_promo":
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM promo_codes ORDER BY created_at DESC LIMIT 10") as cur:
                promos = await cur.fetchall()
            if promos:
                text += "\n\n<b>Последние:</b>\n"
                for p in promos:
                    text += (f"  <code>{p['code']}</code> — {p['gold']}💰 {p['gems']}💎 "
                             f"({p['used_count']}/{p['max_uses']})\n")
    kb = make_kb([[("🔙 Панель", "adm_panel")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "adm_system")
async def cb_adm_system(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    hiviews_status = "✅ Ключ задан" if HIVIEWS_API_KEY else "❌ Не настроен"
    crypto_status = "✅" if CRYPTO_PAY_TOKEN else "❌"
    text = (
        f"⚙️ <b>Система</b>\n\n"
        f"🐍 Python: {sys.version.split()[0]}\n"
        f"🗄️ БД: {db_size / 1024:.1f} KB\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📢 HiViews: {hiviews_status}\n"
        f"🔑 Crypto Pay: {crypto_status}\n"
    )
    kb = make_kb([[("🔙 Панель", "adm_panel")]])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


# Текстовые админ-команды
@router.message(Command("addpromo"))
async def cmd_addpromo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    fire_hiviews_message(message)
    args = message.text.split()
    if len(args) < 5:
        return await message.answer("Формат: /addpromo КОД ЗОЛОТО ГЕМЫ МАКС")
    try:
        code, gold, gems, mx = args[1].upper(), int(args[2]), int(args[3]), int(args[4])
    except ValueError:
        return await message.answer("❌ Неверные параметры. Используй числа.")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO promo_codes VALUES (?,?,?,?,0,?)",
                         (code, gold, gems, mx, datetime.now().isoformat()))
        await db.commit()
    await message.answer(f"✅ <b>{code}</b>: {gold}💰 {gems}💎 (макс:{mx})")


@router.message(Command("give"))
async def cmd_give(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    fire_hiviews_message(message)
    args = message.text.split()
    if len(args) < 4:
        return await message.answer("/give USER_ID gold/gems КОЛ-ВО")
    try:
        tid, cur_type, amt = int(args[1]), args[2], int(args[3])
    except ValueError:
        return await message.answer("❌ Неверные параметры.")
    user = await get_user(tid)
    if not user:
        return await message.answer("❌ Не найден")
    if cur_type == "gold":
        await update_user(tid, gold=user["gold"] + amt)
    elif cur_type == "gems":
        await update_user(tid, gems=user["gems"] + amt,
                          total_gems_earned=user["total_gems_earned"] + amt)
    else:
        return await message.answer("gold или gems")
    await message.answer(f"✅ +{amt} {cur_type} → {user['username']}")
    try:
        await bot.send_message(tid, f"🎁 +{amt} {'💰' if cur_type == 'gold' else '💎'}!")
    except Exception:
        pass


@router.message(Command("givevip"))
async def cmd_givevip(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    fire_hiviews_message(message)
    args = message.text.split()
    if len(args) < 3:
        return await message.answer("/givevip USER_ID ДНЕЙ")
    try:
        tid, days = int(args[1]), int(args[2])
    except ValueError:
        return await message.answer("❌ Неверные параметры.")
    user = await get_user(tid)
    if not user:
        return await message.answer("❌ Не найден")
    vip_end = get_vip_end(user) + timedelta(days=days)
    await update_user(tid, vip_until=vip_end.isoformat())
    await message.answer(f"✅ VIP {days}д → {user['username']}")
    try:
        await bot.send_message(tid, f"👑 VIP на {days} дней!")
    except Exception:
        pass


@router.message(Command("ban"))
async def cmd_ban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    fire_hiviews_message(message)
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("/ban USER_ID")
    try:
        await update_user(int(args[1]), is_banned=1)
        await message.answer(f"🔨 Забанен: {args[1]}")
    except ValueError:
        await message.answer("❌ Неверный ID")


@router.message(Command("unban"))
async def cmd_unban(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    fire_hiviews_message(message)
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("/unban USER_ID")
    try:
        await update_user(int(args[1]), is_banned=0)
        await message.answer(f"✅ Разбанен: {args[1]}")
    except ValueError:
        await message.answer("❌ Неверный ID")


@router.message(Command("find"))
async def cmd_find(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    fire_hiviews_message(message)
    args = message.text.split()
    if len(args) < 2:
        return await message.answer("/find USER_ID")
    try:
        user = await get_user(int(args[1]))
    except ValueError:
        return await message.answer("❌ Неверный ID")
    if not user:
        return await message.answer("❌ Не найден")
    cls = CLASSES.get(user["class"], {})
    vip_label = "👑VIP" if is_vip(user) else ""
    ban_label = "🚫БАН" if user["is_banned"] else ""
    text = (
        f"🔍 <b>{user['username']}</b> {cls.get('emoji', '')} {vip_label} {ban_label}\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Ур.{user['level']} XP:{user['xp']}/{user['xp_needed']}\n"
        f"HP:{user['hp']}/{user['max_hp']} ⚔️{user['atk']} 🛡️{user['def']} 🎯{user['crit']}%\n"
        f"💰{user['gold']} 💎{user['gems']} ⚡{user['energy']}/{user['max_energy']}\n"
        f"PvP:{user['wins']}W/{user['losses']}L "
        f"Данжи:{user['dungeon_wins']} Боссы:{user['boss_kills']}\n"
        f"Заработано: {user['total_gold_earned']}💰 {user['total_gems_earned']}💎\n"
        f"Потрачено: ${user['total_spent_usd']:.2f} "
        f"Рефов:{user['referral_count']} Стрик:{user['streak']}"
    )
    await message.answer(text)


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return
    fire_hiviews_message(message)
    text = message.text.replace("/broadcast ", "", 1)
    if not text or text == "/broadcast":
        return await message.answer("/broadcast ТЕКСТ")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users WHERE is_banned = 0") as cur:
            users = await cur.fetchall()
    sent, failed = 0, 0
    for (uid,) in users:
        try:
            await bot.send_message(uid, f"📢 <b>Объявление</b>\n\n{text}")
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await message.answer(f"📢 ✅{sent} ❌{failed}")


# Обработка неизвестных сообщений
@router.message()
async def fallback_handler(message: Message):
    fire_hiviews_message(message)
    user = await get_user(message.from_user.id)
    if user and user.get("is_banned"):
        return await message.answer("🚫 Вы заблокированы.")
    if message.text and not message.text.startswith("/"):
        await message.answer("🐉 Используй /start чтобы начать!")


# ======================== ЗАПУСК ========================
async def main():
    logger.info("🐉 Dungeon Master Bot v3.0 запускается...")
    await init_db()
    await bot.delete_webhook(drop_pending_updates=True)

    if HIVIEWS_API_KEY:
        logger.info(f"📢 HiViews: активирован (прямые вызовы из хендлеров)")
    else:
        logger.info("📢 HiViews: не настроен (HIVIEWS_API_KEY не задан)")

    logger.info("✅ База готова. 🚀 Бот запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
