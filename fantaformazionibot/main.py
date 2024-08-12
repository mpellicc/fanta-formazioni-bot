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

from config import Config
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from fantaformazionibot.bot.handler.commands import help_command, start_command
from fantaformazionibot.bot.handler.errors import default_error_handler
from fantaformazionibot.bot.handler.handlers import default_response_handler
from fantaformazionibot.bot.jobs import schedule_jobs
from fantaformazionibot.utils.logging import setup_logging

# Enable logging
logger = setup_logging()


def main():
    config: Config = Config()

    app = Application.builder().token(config.token).build()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT, default_response_handler))

    # Errors
    app.add_error_handler(default_error_handler)

    # Jobs
    schedule_jobs(app.job_queue)

    # Polling
    app.run_polling(poll_interval=1)


if __name__ == "__main__":
    main()
