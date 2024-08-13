from telegram import Update
from telegram.ext import ContextTypes

from utils.logging import get_logger

logger = get_logger()


async def default_error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
