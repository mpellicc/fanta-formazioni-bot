from constant.messages import Messages
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes


async def start_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends an introductory message."""
    await update.message.reply_text(Messages.START, parse_mode=ParseMode.MARKDOWN_V2)


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends explanation on how to use the bot."""
    await update.message.reply_text(Messages.HELP, parse_mode=ParseMode.MARKDOWN_V2)
    

async def next_match_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message indicating when the next match will be."""
    await update.message.reply_text(Messages.NOT_IMPLEMENTED, parse_mode=ParseMode.MARKDOWN_V2)
