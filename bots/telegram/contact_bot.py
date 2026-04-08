import os
import logging
import asyncio
import random
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

(
    CHOICE,
    STEP,
    CONFIRM,
) = range(3)

CATEGORIES = {
    "contact": "📝 Contact",
    "partenariat": "🤝 Partenariat",
    "presse": "📰 Presse",
    "correction": "✏️ Correction",
}

FLOW = {
    "contact": [
        ("name", "Votre nom / organisation :"),
        ("contact", "Votre contact (email / téléphone) :"),
        ("message", "Votre message :"),
    ],
    "partenariat": [
        ("name", "Organisation :"),
        ("contact", "Contact :"),
        ("type", "Type de partenariat :"),
        ("message", "Votre proposition :"),
    ],
    "presse": [
        ("media", "Nom du média :"),
        ("journalist", "Nom du journaliste :"),
        ("deadline", "Deadline :"),
        ("message", "Votre demande :"),
    ],
    "correction": [
        ("name", "Nom :"),
        ("contact", "Contact :"),
        ("link", "Lien concerné :"),
        ("message", "Correction à apporter :"),
    ],
}


def generate_ticket_id():
    return f"CVP-{random.randint(1000,9999)}"


def generate_tags(category, data):
    tags = [f"#{category}"]

    text = " ".join(str(v).lower() for v in data.values())

    if category == "presse":
        tags += ["#media"]

    if category == "correction":
        tags += ["#data"]

    if "urgent" in text:
        tags.append("#urgent")

    if "erreur" in text or "bug" in text:
        tags.append("#bug")

    return " ".join(tags)


def nav_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Retour", callback_data="back")],
        [InlineKeyboardButton("❌ Annuler", callback_data="cancel")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📝 Contact", callback_data="contact")],
        [InlineKeyboardButton("🤝 Partenariat", callback_data="partenariat")],
        [InlineKeyboardButton("📰 Presse", callback_data="presse")],
        [InlineKeyboardButton("✏️ Correction", callback_data="correction")],
    ]

    await update.message.reply_text(
        "Bienvenue 👋\nChoisissez votre demande :",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return CHOICE


async def choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category = query.data
    context.user_data.clear()
    context.user_data["category"] = category
    context.user_data["step"] = 0

    _, question = FLOW[category][0]
    await query.edit_message_text(question)

    return STEP


async def handle_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    category = data["category"]
    step = data["step"]

    field, _ = FLOW[category][step]
    data[field] = update.message.text

    step += 1
    data["step"] = step

    if step >= len(FLOW[category]):
        return await summary(update, context)

    _, next_question = FLOW[category][step]
    await update.message.reply_text(next_question, reply_markup=nav_keyboard())
    return STEP


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = context.user_data
    category = data["category"]

    text = f"{CATEGORIES[category]}\n\n"

    for field, _ in FLOW[category]:
        text += f"{field.capitalize()} : {data.get(field)}\n"

    keyboard = [
        [InlineKeyboardButton("✅ Envoyer", callback_data="confirm")],
        [InlineKeyboardButton("⬅️ Modifier", callback_data="back")],
    ]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    return CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = context.user_data
    category = data["category"]

    ticket_id = generate_ticket_id()
    tags = generate_tags(category, data)

    text = (
        f"🧾 TICKET #{ticket_id}\n"
        f"{CATEGORIES[category]}\n"
        f"🏷️ {tags}\n\n"
        f"🕒 {datetime.now().strftime('%d/%m %H:%M')}\n\n"
    )

    for field, _ in FLOW[category]:
        text += f"{field.capitalize()} : {data.get(field)}\n"

    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=text)

    await query.edit_message_text(
        f"✅ Message envoyé.\n\n🧾 Référence : {ticket_id}"
    )

    context.user_data.clear()
    return ConversationHandler.END


async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = context.user_data
    step = data.get("step", 0)

    if step > 0:
        step -= 1
        data["step"] = step

    category = data["category"]
    _, question = FLOW[category][step]

    await query.edit_message_text(question)
    return STEP


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Demande annulée.")
    return ConversationHandler.END


async def run_bot():
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN manquant")
    if not ADMIN_CHAT_ID:
        raise ValueError("ADMIN_CHAT_ID manquant")

    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOICE: [CallbackQueryHandler(choose)],
            STEP: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_step),
                CallbackQueryHandler(back, pattern="back"),
                CallbackQueryHandler(cancel, pattern="cancel"),
            ],
            CONFIRM: [
                CallbackQueryHandler(confirm, pattern="confirm"),
                CallbackQueryHandler(back, pattern="back"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)

    logger.info("Contact bot started")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    while True:
        await asyncio.sleep(3600)


def main():
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
