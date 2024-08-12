from telegram import Update
from telegram.ext import ContextTypes


async def default_response_handler(update: Update, _: ContextTypes.DEFAULT_TYPE) -> str:
    """Utility method to test the bot activeness."""
    text: str = update.message.text

    if "ciao" in text.lower():
        await update.message.reply_text("Ciao!")
        return

    await update.message.reply_text("Non capisco...")
