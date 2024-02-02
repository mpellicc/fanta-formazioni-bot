import pickle
from datetime import datetime, time, timedelta

import config
from constants.notifications_interval import NOTIFICATIONS_INTERVAL
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from utils.expiry_message import get_expiry_message
from src.fantaformazionireminder.utils.default_dates import write_default_dates


# Load active chat IDs from a file or initialize an empty list
try:
    with open(config.CHAT_IDS_FILEPATH, "rb") as file:
        print(f"[CHAT_ID][FILE_OPEN] File {file.name} opened!")
        active_chat_ids = pickle.load(file)
except FileNotFoundError:
    print("[CHAT_ID][FILE_NOT_FOUND] File not found")
    active_chat_ids = []


# Load saved dates from a file or initialize an empty list
try:
    with open(config.SAVED_DATES_FILEPATH, "rb") as file:
        print(f"[DATE][FILE_OPEN] File {file.name} opened!")
        saved_dates = pickle.load(file)
except FileNotFoundError:
    print(
        "[DATE][FILE_NOT_FOUND] saved_dates file not found, running write_default_dates.py..."
    )
    write_default_dates()
    try:
        with open(config.SAVED_DATES_FILEPATH, "rb") as file:
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
        with open(config.CHAT_IDS_FILEPATH, "wb") as file:
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
\- /aggiungi\_data: Inizio una conversazione per aggiungere una data al calendario da notificare\. Capirò in automatico la chat da cui il comando proviene e ti avviserò lì\.
Puoi anche inviare il comando seguito da una data formattata in questo modo `dd/MM/yyyy,HH:mm`\.
\- /prossima\_scadenza: Invierò un messaggio che indica quando scade la prossima formazione da inserire\.
\- /annulla: Permette di uscire da una conversazione con il bot\.\n
Se hai bisogno di ulteriori informazioni o aiuto, scrivi a @pelliccm\.
    """
    await update.message.reply_text(
        message,
        parse_mode="MarkdownV2",
    )


CONV_DATE, CONV_TIME = range(2)


# Helper function to start the conversation
async def start_add_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        print(
            "[DATE][CONVERSATION] Missing argument for save_date_command. Starting conversation..."
        )
        await update.message.reply_text(
            "Inserisci la data nel formato `dd/MM/yyyy`:",
            parse_mode="MarkdownV2",
        )
        return CONV_DATE
    else:
        # If an argument is provided, proceed with the existing behavior
        await save_date(update, context.args[0])
        return ConversationHandler.END


# Function to handle date input
async def date_convo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text

    try:
        # Attempt to parse the date string
        date_obj = datetime.strptime(user_input, "%d/%m/%Y")

        # Check if the parsed date is in the future
        if date_obj.date() < datetime.now().date():
            await update.message.reply_text(
                "La data inserita è nel passato\. Inserisci una data futura nel formato `dd/MM/yyyy`:",
                parse_mode="MarkdownV2",
            )
            return CONV_DATE

        # Store the valid date in user_data
        context.user_data["date"] = date_obj.strftime("%d/%m/%Y")
        print(f'[DATE][CONVERSATION] Date input: {context.user_data["date"]}')

        await update.message.reply_text(
            "Ora inserisci l'orario nel formato `HH:mm`:",
            parse_mode="MarkdownV2",
        )
        return CONV_TIME

    except ValueError:
        # Handle invalid date format
        await update.message.reply_text(
            "Formato data non valido\. Per favore, usa `dd/MM/yyyy`\.\n"
            "Riprova o invia /annulla per uscire\.",
            parse_mode="MarkdownV2",
        )
        return CONV_DATE


# Function to handle time input and save the complete date
async def time_convo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    print(f"[DATE][CONVERSATION] Time input: {user_input}")

    try:
        date_str = context.user_data.get("date", "")
        complete_datetime_str = f"{date_str},{user_input}"
        print(f"[DATE][CONVERSATION] Complete datetime string: {complete_datetime_str}")

        return (
            ConversationHandler.END
            if await save_date(update, complete_datetime_str)
            else CONV_DATE
        )
    except ValueError:
        # Handle invalid date format
        await update.message.reply_text(
            "Formato ora non valido\. Per favore, usa `HH:mm`\.\n"
            "Riprova o invia /annulla per uscire\.",
            parse_mode="MarkdownV2",
        )
        return CONV_TIME


async def save_date(update, date_str: str):
    chat_id = update.message.chat_id

    try:
        # Parse the date string to a datetime object
        date_obj = datetime.strptime(date_str, "%d/%m/%Y,%H:%M")
        saved_date_obj = date_obj - timedelta(minutes=5)

        if date_obj < datetime.now():
            await update.message.reply_text(
                "La data inserita è nel passato. Inserisci una data futura."
            )
        # Check if the date is already saved for the chat_id
        elif is_date_already_saved(chat_id, saved_date_obj):
            await update.message.reply_text(
                "Questa data è già stata salvata per questa chat. Riprova."
            )
        else:
            # Append the new date to the existing list
            saved_dates.append((chat_id, saved_date_obj))

            # Save the updated list to the file
            with open(config.SAVED_DATES_FILEPATH, "wb") as file:
                pickle.dump(saved_dates, file)
                print(
                    f"[DATE][FILE_UPDATE] {saved_dates[-1]} saved in file {file.name}"
                )

            # Respond with a confirmation message
            await update.message.reply_text(
                "Data salvata: {}".format(date_obj.strftime("%d/%m/%Y, %H:%M"))
            )
            return True
    except ValueError:
        # Handle invalid date format
        await update.message.reply_text(
            "Qualcosa è andato storto con la data inserita\.\n"
            "Riprova o invia /help per maggiori informazioni\.",
            parse_mode="MarkdownV2",
        )

    return False


def is_date_already_saved(chat_id, date_obj):
    return any(chat_id == entry[0] and date_obj == entry[1] for entry in saved_dates)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    print("User canceled the conversation.")
    await update.message.reply_text("Inserimento data annullato. Ci vediamo!")

    context.user_data.clear()
    return ConversationHandler.END


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
        if config.BOT_USERNAME in text:
            new_text: str = text.replace(config.BOT_USERNAME, "").strip()
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
    with open(config.SAVED_DATES_FILEPATH, "wb") as file:
        pickle.dump(updated_saved_dates, file)

    saved_dates = updated_saved_dates


# Application
if __name__ == "__main__":
    print("[SELF] Starting bot...")
    app = Application.builder().token(config.TOKEN).build()
    job_queue = app.job_queue

    # Cleanup
    remove_expired_dates()

    # Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("prossima_scadenza", nearest_date_command))

    # Conversations
    app.add_handler(
        ConversationHandler(
            entry_points=[CommandHandler("aggiungi_data", start_add_date)],
            states={
                CONV_DATE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, date_convo)
                ],
                CONV_TIME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, time_convo)
                ],
            },
            fallbacks=[CommandHandler("annulla", cancel)],
        )
    )

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
