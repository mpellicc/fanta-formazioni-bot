from datetime import datetime, timedelta, time
import os
import pickle
from typing import Final

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import NOTIFICATIONS_INTERVAL
from utils import get_expiry_message
from write_default_dates import write_default_dates

# Env
# Load environment variables from .env file
load_dotenv()

# Access constants from environment variables
TOKEN: Final[str] = os.getenv("TOKEN")
BOT_USERNAME: Final[str] = os.getenv("BOT_USERNAME")

SAVED_DATES_FILEPATH: Final[str] = os.getenv("SAVED_DATES_FILEPATH")
CHAT_IDS_FILEPATH: Final[str] = os.getenv("CHAT_IDS_FILEPATH")

# Load active chat IDs from a file or initialize an empty list
try:
    with open(CHAT_IDS_FILEPATH, "rb") as file:
        print(f"[CHAT_ID][FILE_OPEN] File {file.name} opened!")
        active_chat_ids = pickle.load(file)
except FileNotFoundError:
    print("[CHAT_ID][FILE_NOT_FOUND] File not found")
    active_chat_ids = []

# Load saved dates from a file or initialize an empty list
try:
    with open(SAVED_DATES_FILEPATH, "rb") as file:
        print(f"[DATE][FILE_OPEN] File {file.name} opened!")
        saved_dates = pickle.load(file)
except FileNotFoundError:
    print(
        "[DATE][FILE_NOT_FOUND] saved_dates file not found, running write_default_dates.py..."
    )
    write_default_dates()
    try:
        with open(SAVED_DATES_FILEPATH, "rb") as file:
            print(f"[DATE][FILE_OPEN] File {file.name} opened!")
            saved_dates = pickle.load(file)
    except FileNotFoundError:
        print("[DATE][FILE_NOT_FOUND] File still not found, using an empty list.")
        saved_dates = []


# Commands
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    if chat_id not in active_chat_ids:
        active_chat_ids.append(chat_id)
        with open(CHAT_IDS_FILEPATH, "wb") as file:
            pickle.dump(active_chat_ids, file)
            print(
                f"[CHAT_ID][FILE_UPDATE] {active_chat_ids[-1]} saved in file {file.name}"
            )

        message = """
Grazie per avermi avviato\!\n
Ti notificherò quando l'inserimento della formazione starà per scadere\.
La notifica sarà un giorno, un'ora e dieci minuti prima della scadenza \(impostata a 5 minuti dall'inizio della giornata\)\.\n
Invia /help per ulteriori informazioni\.
        """

        await update.message.reply_text(message, parse_mode="MarkdownV2")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = """
Ecco la lista dei comandi:
\- /start: Avvia il bot\.
\- /help: Questo messaggio\.
\- /aggiungi\_data: Manda questo comando, seguito da una data formattata in questo modo `dd/MM/yyyy,HH:mm` per aggiungere una data al calendario da notificare\. Capirò in automatico la chat da cui il comando proviene e ti avviserò lì\.
\- /prossima\_scadenza: Invierò un messaggio che indica quando scade la prossima formazione da inserire\.\n
Se hai bisogno di ulteriori informazioni o aiuto, scrivi a @pelliccm\.
    """
    await update.message.reply_text(
        message,
        parse_mode="MarkdownV2",
    )


async def save_date_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id

    # Assumes the date is the first argument
    if not context.args:
        await update.message.reply_text(
            "Per favore, usa il comando inserendo una data: `/aggiungi_data dd/MM/yyyy,HH:MM`\.",
            parse_mode="MarkdownV2",
        )
    else:
        # Get the date string from the user's message
        date_str = context.args[0]

        try:
            # Parse the date string to a datetime object
            date_obj = datetime.strptime(date_str, "%d/%m/%Y,%H:%M")

            # Append the new date to the existing list
            saved_dates.append((chat_id, date_obj))

            # Save the updated list to the file
            with open(SAVED_DATES_FILEPATH, "wb") as file:
                pickle.dump(saved_dates, file)
                print(
                    f"[DATE][FILE_UPDATE] {saved_dates[-1]} saved in file {file.name}"
                )

            # Respond with a confirmation message
            await update.message.reply_text(
                "Data salvata: {}".format(date_obj.strftime("%d-%m-%Y, %H:%M"))
            )
        except ValueError:
            # Handle invalid date format
            await update.message.reply_text(
                "Formato data non valido. Per favore, usa dd/MM/yyyy,HH:MM."
            )


async def nearest_date_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nearest_date = find_nearest_date(update.message.chat_id)

    if nearest_date:
        message = f"La prossima scadenza della formazione sarà: {nearest_date.strftime('%d-%m-%Y, %H:%M')}."
    else:
        message = "Nessuna data trovata."

    await update.message.reply_text(message)


# Responses
def handle_response(text: str) -> str:
    processed: str = text.lower()

    if "ciao" in processed:
        return "Ciao!"

    return "Non capisco..."


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_type: str = update.message.chat.type
    text: str = update.message.text

    print(
        f'[UPDATE][MESSAGE] User [{update.message.chat.id}] in {message_type}: "{text}"'
    )

    if message_type == "group" or message_type == "supergroup":
        if BOT_USERNAME in text:
            new_text: str = text.replace(BOT_USERNAME, "").strip()
            response: str = handle_response(new_text)
        else:
            return
    else:
        response: str = handle_response(text)

    print("[UPDATE][SELF] Bot:", response)
    await update.message.reply_text(response)


# Errors
async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[UPDATE][ERROR] Update {update} caused error {context.error}")


# Functions
# Define a dictionary to track sent notifications for specific time points per saved date
sent_notifications = {}


# Update the check_and_send_notifications function
async def check_and_send_notifications(context: ContextTypes.DEFAULT_TYPE):
    current_time = datetime.now()
    # print(f"Checking dates @ {current_time}")

    for chat_id, saved_date in saved_dates:
        # Calculate the time difference
        time_difference = saved_date - current_time

        # Initialize sent_notifications for this saved_date if not present
        if saved_date not in sent_notifications:
            sent_notifications[saved_date] = []

        for seconds_from_expiry in NOTIFICATIONS_INTERVAL:
            if (
                timedelta(seconds=(seconds_from_expiry - 60))
                <= time_difference
                < timedelta(seconds=(seconds_from_expiry + 60))
            ):
                if seconds_from_expiry not in sent_notifications[saved_date]:
                    await notify_expiry(
                        context=context,
                        message=get_expiry_message(time_difference, saved_date),
                        chat_id=chat_id,
                    )
                    add_notification_to_sent(saved_date, seconds_from_expiry)

        prune_old_notifications(saved_date)


# Notify date
async def notify_expiry(
    context: ContextTypes.DEFAULT_TYPE, message: str, chat_id: int = 0
):
    if chat_id != 0:
        await context.bot.send_message(chat_id=chat_id, text=message)
    else:
        for saved_chat_id in active_chat_ids:
            await context.bot.send_message(chat_id=saved_chat_id, text=message)


def find_nearest_date(chat_id):
    current_time = datetime.now()

    nearest_date = None
    min_time_difference = None

    for saved_chat_id, saved_date in saved_dates:
        if saved_chat_id == 0 or saved_chat_id == chat_id:
            time_difference = saved_date - current_time

            if nearest_date is None or time_difference < min_time_difference:
                nearest_date = saved_date
                min_time_difference = time_difference

    return nearest_date


# Keep in memory which notification of a saved_date has already been sent
def add_notification_to_sent(saved_date, seconds_from_expiry):
    print(
        f"[DATE][SENT_NOTIFICATION] Notification sent. saved_date [{saved_date}]; seconds_from_expiry: [{seconds_from_expiry}]"
    )
    sent_notifications[saved_date].append(seconds_from_expiry)


# Prune old notifications from sent_notifications
def prune_old_notifications(saved_date):
    is_date_past = saved_date < datetime.now()
    all_notifications_sent = all(
        interval in sent_notifications[saved_date]
        for interval in NOTIFICATIONS_INTERVAL
    )

    # Remove the saved_date if it's in the past
    if (is_date_past or all_notifications_sent) and sent_notifications[saved_date]:
        print(
            f"[DATE][PRUNE_NOTIFICATION] Pruning notification of date {saved_date}..."
        )
        del sent_notifications[saved_date]


# Clean file from expired dates
def remove_expired_dates():
    print("[DATE][FILE_CLEANING] Cleaning file from expired dates")
    global saved_dates
    current_time = datetime.now()

    # Filter the list to keep only dates that are greater than the current time
    updated_saved_dates = [
        (chat_id, date) for chat_id, date in saved_dates if date > current_time
    ]

    # Save the updated list to the file
    with open(SAVED_DATES_FILEPATH, "wb") as file:
        pickle.dump(updated_saved_dates, file)

    saved_dates = updated_saved_dates


# Application
if __name__ == "__main__":
    print("[SELF] Starting bot...")
    app = Application.builder().token(TOKEN).build()
    job_queue = app.job_queue

    # Cleanup
    remove_expired_dates()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("aggiungi_data", save_date_command))
    app.add_handler(CommandHandler("prossima_scadenza", nearest_date_command))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT, handle_message))

    # Errors
    app.add_error_handler(error)

    # JobQueue
    job_queue.run_repeating(check_and_send_notifications, interval=5, first=0)
    job_queue.run_daily(remove_expired_dates, time=time(1, 0, 0))

    # Polling
    print("[SELF] Polling...")
    app.run_polling(poll_interval=1)
