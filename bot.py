import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

CONFIG_PATH = Path("bot_config.json")
STATE_KEY = "admin_state"
TEMP_KEY = "admin_temp"


DEFAULT_CONFIG: Dict[str, Any] = {
    "admin_ids": [],
    "texts": {
        "welcome": "Добро пожаловать в DungeonMasterBot!",
        "donate": "Поддержите проект, выбрав удобный вариант доната:",
    },
    "features": [
        {
            "id": "adventure",
            "label": "⚔️ Приключение",
            "enabled": True,
            "response": "Вы отправились в приключение!",
        },
        {
            "id": "shop",
            "label": "🛒 Магазин",
            "enabled": True,
            "response": "Магазин пока закрыт, но скоро откроется!",
        },
    ],
    "donations": [
        {"name": "Малый пак", "price": 100, "description": "Поддержка на 100₽"},
        {"name": "Средний пак", "price": 500, "description": "Поддержка на 500₽"},
    ],
}


@dataclass
class AdminState:
    mode: str
    payload: Optional[Dict[str, Any]] = None


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        current = json.load(file)

    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    merged.update(current)
    merged["texts"].update(current.get("texts", {}))

    return merged


def save_config(config: Dict[str, Any]) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)


def is_admin(config: Dict[str, Any], user_id: int) -> bool:
    return user_id in config.get("admin_ids", [])


def main_menu_keyboard(config: Dict[str, Any]) -> ReplyKeyboardMarkup:
    buttons: List[List[str]] = []
    row: List[str] = []
    for feature in config.get("features", []):
        if feature.get("enabled", True):
            row.append(feature.get("label", "Функция"))
            if len(row) == 2:
                buttons.append(row)
                row = []

    if row:
        buttons.append(row)

    buttons.append(["💎 Донат"])
    return ReplyKeyboardMarkup(buttons, resize_keyboard=True)


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📝 Тексты", callback_data="admin:texts")],
            [InlineKeyboardButton("⚙️ Функции", callback_data="admin:features")],
            [InlineKeyboardButton("💎 Донат-паки", callback_data="admin:donations")],
            [InlineKeyboardButton("👥 Администраторы", callback_data="admin:admins")],
        ]
    )


def feature_list_keyboard(config: Dict[str, Any]) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for i, feature in enumerate(config.get("features", [])):
        status = "✅" if feature.get("enabled", True) else "❌"
        rows.append(
            [
                InlineKeyboardButton(
                    f"{status} {feature.get('label', feature.get('id', 'feature'))}",
                    callback_data=f"admin:feature:{i}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("➕ Добавить функцию", callback_data="admin:feature:add")])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin:back")])
    return InlineKeyboardMarkup(rows)


def donation_list_keyboard(config: Dict[str, Any]) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for i, pack in enumerate(config.get("donations", [])):
        rows.append(
            [
                InlineKeyboardButton(
                    f"💰 {pack.get('name', 'Пак')} — {pack.get('price', 0)}₽",
                    callback_data=f"admin:donation:{i}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("➕ Добавить пак", callback_data="admin:donation:add")])
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="admin:back")])
    return InlineKeyboardMarkup(rows)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    config = load_config()
    user = update.effective_user
    if not user or not update.message:
        return

    text = config["texts"].get("welcome", DEFAULT_CONFIG["texts"]["welcome"])
    await update.message.reply_text(text, reply_markup=main_menu_keyboard(config))

    if is_admin(config, user.id):
        await update.message.reply_text(
            "Вы администратор. Откройте панель кнопкой ниже.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🛠 Админ-панель", callback_data="admin:open")]]
            ),
        )


async def process_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    config = load_config()
    user = update.effective_user

    if is_admin(config, user.id) and context.user_data.get(STATE_KEY):
        await handle_admin_input(update, context, config)
        return

    text = update.message.text or ""

    if text == "💎 Донат":
        message = config["texts"].get("donate", DEFAULT_CONFIG["texts"]["donate"])
        packs = "\n".join(
            [
                f"• {item.get('name', 'Пак')} — {item.get('price', 0)}₽\n  {item.get('description', '')}"
                for item in config.get("donations", [])
            ]
        )
        await update.message.reply_text(f"{message}\n\n{packs}")
        return

    for feature in config.get("features", []):
        if feature.get("enabled", True) and text == feature.get("label"):
            await update.message.reply_text(feature.get("response", "Готово!"))
            return

    await update.message.reply_text("Не понял запрос. Выберите действие на клавиатуре.")


async def admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not update.effective_user:
        return

    await query.answer()
    config = load_config()

    if not is_admin(config, update.effective_user.id):
        await query.edit_message_text("У вас нет доступа к админ-панели.")
        return

    data = query.data or ""

    if data == "admin:open":
        await query.edit_message_text("Админ-панель", reply_markup=admin_panel_keyboard())
        return

    if data == "admin:back":
        await query.edit_message_text("Админ-панель", reply_markup=admin_panel_keyboard())
        return

    if data == "admin:texts":
        await query.edit_message_text(
            "Что хотите изменить?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("Приветствие", callback_data="admin:text:welcome")],
                    [InlineKeyboardButton("Текст доната", callback_data="admin:text:donate")],
                    [InlineKeyboardButton("⬅️ Назад", callback_data="admin:back")],
                ]
            ),
        )
        return

    if data.startswith("admin:text:"):
        key = data.split(":")[-1]
        context.user_data[STATE_KEY] = AdminState(mode="edit_text", payload={"key": key}).__dict__
        await query.message.reply_text("Введите новый текст одним сообщением.")
        return

    if data == "admin:features":
        await query.edit_message_text("Список функций:", reply_markup=feature_list_keyboard(config))
        return

    if data == "admin:feature:add":
        context.user_data[STATE_KEY] = AdminState(mode="add_feature_label").__dict__
        await query.message.reply_text("Введите название кнопки для новой функции.")
        return

    if data.startswith("admin:feature:"):
        idx = int(data.split(":")[-1])
        feature = config["features"][idx]
        context.user_data[TEMP_KEY] = {"feature_idx": idx}
        await query.edit_message_text(
            f"Функция: {feature.get('label')}\nЧто сделать?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🔁 Вкл/Выкл", callback_data="admin:feature_toggle")],
                    [InlineKeyboardButton("✏️ Изменить текст кнопки", callback_data="admin:feature_label")],
                    [InlineKeyboardButton("💬 Изменить ответ", callback_data="admin:feature_response")],
                    [InlineKeyboardButton("🗑 Удалить", callback_data="admin:feature_delete")],
                    [InlineKeyboardButton("⬅️ К списку", callback_data="admin:features")],
                ]
            ),
        )
        return

    if data == "admin:feature_toggle":
        idx = context.user_data.get(TEMP_KEY, {}).get("feature_idx")
        if idx is None:
            return
        config["features"][idx]["enabled"] = not config["features"][idx].get("enabled", True)
        save_config(config)
        await query.edit_message_text("Статус обновлён.", reply_markup=feature_list_keyboard(config))
        return

    if data == "admin:feature_label":
        idx = context.user_data.get(TEMP_KEY, {}).get("feature_idx")
        context.user_data[STATE_KEY] = AdminState(mode="edit_feature_label", payload={"idx": idx}).__dict__
        await query.message.reply_text("Введите новый текст кнопки.")
        return

    if data == "admin:feature_response":
        idx = context.user_data.get(TEMP_KEY, {}).get("feature_idx")
        context.user_data[STATE_KEY] = AdminState(mode="edit_feature_response", payload={"idx": idx}).__dict__
        await query.message.reply_text("Введите новый текст ответа.")
        return

    if data == "admin:feature_delete":
        idx = context.user_data.get(TEMP_KEY, {}).get("feature_idx")
        if idx is None:
            return
        config["features"].pop(idx)
        save_config(config)
        await query.edit_message_text("Функция удалена.", reply_markup=feature_list_keyboard(config))
        return

    if data == "admin:donations":
        await query.edit_message_text("Донат-паки:", reply_markup=donation_list_keyboard(config))
        return

    if data == "admin:donation:add":
        context.user_data[STATE_KEY] = AdminState(mode="add_donation_name").__dict__
        await query.message.reply_text("Введите название нового донат-пака.")
        return

    if data.startswith("admin:donation:"):
        idx = int(data.split(":")[-1])
        pack = config["donations"][idx]
        context.user_data[TEMP_KEY] = {"donation_idx": idx}
        await query.edit_message_text(
            f"Пак: {pack.get('name')} ({pack.get('price')}₽)",
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("✏️ Название", callback_data="admin:donation_name")],
                    [InlineKeyboardButton("💵 Цена", callback_data="admin:donation_price")],
                    [InlineKeyboardButton("📝 Описание", callback_data="admin:donation_desc")],
                    [InlineKeyboardButton("🗑 Удалить", callback_data="admin:donation_delete")],
                    [InlineKeyboardButton("⬅️ К списку", callback_data="admin:donations")],
                ]
            ),
        )
        return

    if data == "admin:donation_name":
        idx = context.user_data.get(TEMP_KEY, {}).get("donation_idx")
        context.user_data[STATE_KEY] = AdminState(mode="edit_donation_name", payload={"idx": idx}).__dict__
        await query.message.reply_text("Введите новое название пака.")
        return

    if data == "admin:donation_price":
        idx = context.user_data.get(TEMP_KEY, {}).get("donation_idx")
        context.user_data[STATE_KEY] = AdminState(mode="edit_donation_price", payload={"idx": idx}).__dict__
        await query.message.reply_text("Введите новую цену (числом).")
        return

    if data == "admin:donation_desc":
        idx = context.user_data.get(TEMP_KEY, {}).get("donation_idx")
        context.user_data[STATE_KEY] = AdminState(mode="edit_donation_desc", payload={"idx": idx}).__dict__
        await query.message.reply_text("Введите новое описание.")
        return

    if data == "admin:donation_delete":
        idx = context.user_data.get(TEMP_KEY, {}).get("donation_idx")
        if idx is None:
            return
        config["donations"].pop(idx)
        save_config(config)
        await query.edit_message_text("Пак удалён.", reply_markup=donation_list_keyboard(config))
        return

    if data == "admin:admins":
        admins = config.get("admin_ids", [])
        text = "Текущие админы:\n" + ("\n".join(str(a) for a in admins) if admins else "(пусто)")
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("➕ Добавить ID", callback_data="admin:add_admin")],
                    [InlineKeyboardButton("➖ Удалить ID", callback_data="admin:remove_admin")],
                    [InlineKeyboardButton("⬅️ Назад", callback_data="admin:back")],
                ]
            ),
        )
        return

    if data == "admin:add_admin":
        context.user_data[STATE_KEY] = AdminState(mode="add_admin_id").__dict__
        await query.message.reply_text("Введите Telegram ID нового администратора.")
        return

    if data == "admin:remove_admin":
        context.user_data[STATE_KEY] = AdminState(mode="remove_admin_id").__dict__
        await query.message.reply_text("Введите Telegram ID администратора для удаления.")
        return


async def handle_admin_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    config: Dict[str, Any],
) -> None:
    if not update.message:
        return

    state_raw = context.user_data.get(STATE_KEY)
    if not state_raw:
        return

    state = AdminState(**state_raw)
    text = (update.message.text or "").strip()

    try:
        if state.mode == "edit_text":
            key = state.payload["key"]
            config["texts"][key] = text
            save_config(config)
            await update.message.reply_text("Текст обновлён.")

        elif state.mode == "add_feature_label":
            context.user_data[STATE_KEY] = AdminState(mode="add_feature_response", payload={"label": text}).__dict__
            await update.message.reply_text("Теперь введите ответ, который получит пользователь.")
            return

        elif state.mode == "add_feature_response":
            label = state.payload["label"]
            feature_id = label.lower().replace(" ", "_")
            config["features"].append(
                {"id": feature_id, "label": label, "enabled": True, "response": text}
            )
            save_config(config)
            await update.message.reply_text("Функция добавлена.")

        elif state.mode == "edit_feature_label":
            idx = state.payload["idx"]
            config["features"][idx]["label"] = text
            save_config(config)
            await update.message.reply_text("Текст кнопки обновлён.")

        elif state.mode == "edit_feature_response":
            idx = state.payload["idx"]
            config["features"][idx]["response"] = text
            save_config(config)
            await update.message.reply_text("Ответ обновлён.")

        elif state.mode == "add_donation_name":
            context.user_data[STATE_KEY] = AdminState(mode="add_donation_price", payload={"name": text}).__dict__
            await update.message.reply_text("Введите цену в рублях (число).")
            return

        elif state.mode == "add_donation_price":
            price = int(text)
            context.user_data[STATE_KEY] = AdminState(
                mode="add_donation_desc", payload={"name": state.payload["name"], "price": price}
            ).__dict__
            await update.message.reply_text("Введите описание пака.")
            return

        elif state.mode == "add_donation_desc":
            config["donations"].append(
                {
                    "name": state.payload["name"],
                    "price": state.payload["price"],
                    "description": text,
                }
            )
            save_config(config)
            await update.message.reply_text("Донат-пак добавлен.")

        elif state.mode == "edit_donation_name":
            idx = state.payload["idx"]
            config["donations"][idx]["name"] = text
            save_config(config)
            await update.message.reply_text("Название обновлено.")

        elif state.mode == "edit_donation_price":
            idx = state.payload["idx"]
            config["donations"][idx]["price"] = int(text)
            save_config(config)
            await update.message.reply_text("Цена обновлена.")

        elif state.mode == "edit_donation_desc":
            idx = state.payload["idx"]
            config["donations"][idx]["description"] = text
            save_config(config)
            await update.message.reply_text("Описание обновлено.")

        elif state.mode == "add_admin_id":
            admin_id = int(text)
            if admin_id not in config["admin_ids"]:
                config["admin_ids"].append(admin_id)
                save_config(config)
            await update.message.reply_text("Администратор добавлен.")

        elif state.mode == "remove_admin_id":
            admin_id = int(text)
            if admin_id in config["admin_ids"]:
                config["admin_ids"].remove(admin_id)
                save_config(config)
            await update.message.reply_text("Администратор удалён.")

    except ValueError:
        await update.message.reply_text("Неверный формат. Попробуйте снова.")
        return
    except (KeyError, IndexError):
        await update.message.reply_text("Не удалось выполнить действие. Повторите из админ-панели.")
        return
    finally:
        context.user_data.pop(STATE_KEY, None)


def build_application(token: str) -> Application:
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(admin_callbacks, pattern=r"^admin:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_user_message))
    return app


def main() -> None:
    token = Path("token.txt").read_text(encoding="utf-8").strip()
    app = build_application(token)
    app.run_polling(close_loop=False)


if __name__ == "__main__":
    main()
