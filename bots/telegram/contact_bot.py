import os
import logging
import asyncio

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

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

CHOICE, MESSAGE = range(2)

CATEGORIES = {
    "contact": "📝 Contact",
    "partenariat": "🤝 Partenariat",
    "presse": "📰 Presse",
    "correction": "✏️ Correction",
}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info(f"CHAT_ID: {update.effective_chat.id}")

    keyboard = [
        [InlineKeyboardButton("📝 Contact", callback_data="contact")],
        [InlineKeyboardButton("🤝 Partenariat", callback_data="partenariat")],
        [InlineKeyboardButton("📰 Presse", callback_data="presse")],
        [InlineKeyboardButton("✏️ Correction", callback_data="correction")],
    ]

    text = (
        "Bienvenue sur le bot de contact de Ça va Parlement.\n\n"
        "Choisissez le type de demande :"
    )

    if update.message:
        await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    return CHOICE


async def choose(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    category = query.data
    context.user_data["category"] = category

    await query.edit_message_text(
        f"{CATEGORIES[category]}\n\n"
        "Merci d’envoyer votre message en un seul bloc avec si possible :\n"
        "- nom / organisation\n"
        "- contact\n"
        "- objet de la demande\n"
        "- lien concerné s’il s’agit d’une correction"
    )
    return MESSAGE


async def receive(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    category = context.user_data.get("category", "contact")
    user_message = update.message.text

    user = update.effective_user
    full_name = user.full_name or "Utilisateur inconnu"
    username = f"@{user.username}" if user.username else "sans username"
    user_id = user.id

    if not ADMIN_CHAT_ID:
        await update.message.reply_text(
            "Configuration incomplète : ADMIN_CHAT_ID manquant."
        )
        return ConversationHandler.END

    final_message = (
        f"{CATEGORIES[category]}\n"
        f"#{category}\n\n"
        f"{user_message}\n\n"
        f"👤 Expéditeur : {full_name} ({username})\n"
        f"🆔 Telegram ID : {user_id}"
    )

    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text=final_message,
        disable_web_page_preview=True,
    )

    await update.message.reply_text(
        "Merci, votre message a bien été transmis à l’équipe de Ça va Parlement."
    )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("Demande annulée.")
    return ConversationHandler.END


def main() -> None:
    if not TOKEN:
        raise ValueError("La variable TELEGRAM_BOT_TOKEN est manquante.")

    app = ApplicationBuilder().token(TOKEN).build()

    conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("contact", start),
        ],
        states={
            CHOICE: [CallbackQueryHandler(choose)],
            MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conversation_handler)

    logger.info("Contact bot started")

    async def run() -> None:
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        while True:
            await asyncio.sleep(3600)

    asyncio.run(run())


if __name__ == "__main__":
    main()
