import logging

from constant.messages import Messages
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)


async def start_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends an introducotry message."""
    await update.message.reply_text(Messages.START, parse_mode=ParseMode.MARKDOWN_V2)


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    await update.message.reply_text(Messages.HELP, parse_mode=ParseMode.MARKDOWN_V2)
