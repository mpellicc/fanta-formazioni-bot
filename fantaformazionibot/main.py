import logging

import config
from fantaformazionibot.bot.handler.default_handlers import handle_response
from bot.handler.default_commands import help_command, start_command
from bot.jobs import schedule_jobs
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# set higher logging level for httpx to avoid all GET and POST requests being logged
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def main():
    app = Application.builder().token(config.TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT, handle_response))

    # Jobs
    schedule_jobs(app.job_queue)

    # Polling
    app.run_polling(poll_interval=1)


if __name__ == "__main__":
    main()
