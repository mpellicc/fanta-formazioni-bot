"""Fanta Formazioni Bot - The Telegram Bot to remind you to set up your FantaCalcio team lineup.
Copyright (C) 2024 Matteo Pelliccione <mat.pelliccione@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import locale
from typing import List

from bot.handler.commands import help_command, next_match_command, start_command
from bot.handler.errors import default_error_handler
from bot.handler.handlers import default_response_handler
from bot.jobs import schedule_jobs
from config import Config
from db import database
from db.model.match import Match
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from utils.dates import get_clean_dates
from utils.logging import get_logger, setup_logging

# Enable logging
setup_logging()
logger = get_logger("fantaformazionibot")


# Instantiate the config
config: Config = Config()
locale.setlocale(locale.LC_TIME, "it_IT.UTF-8")


def main():
    init(config)

    app = Application.builder().token(config.token).post_init(post_init).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("prossima_scadenza", next_match_command))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT, default_response_handler))

    # Errors
    app.add_error_handler(default_error_handler)

    # Jobs
    schedule_jobs(config, app.job_queue)

    # Polling
    app.run_polling(poll_interval=1)


async def post_init(application: Application) -> None:
    application.bot_data["config"] = config


def init(config: Config) -> None:
    """
    Initialize the bot.
    """

    # Initialize the database
    logger.info("Initializing database...")
    database.create_tables(config.database_file)

    # Initialize the calendar (otherwise the CSV will only be downloaded with the daily job at 1 AM)
    logger.info("Initializing calendar...")
    matches: List[Match] = get_clean_dates(config)
    database.save_matches(config.database_file, matches)


if __name__ == "__main__":
    main()
