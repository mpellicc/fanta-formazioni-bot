from datetime import timedelta

# TODO better handling of time_difference to let the message be more variable
def get_expiry_message(time_difference: timedelta, saved_date: any):
    processed_time = time_difference.total_seconds()
    
    if processed_time >= 80000:
        time_word = "24 ore"
    elif processed_time >= 59 and processed_time <= 61:
        time_word = "un'ora"
    else:
        time_word = "{} minuti".format(time_difference.seconds // 60)

    return "\U0001F6A8 Circa {} alla scadenza della formazione \U0001F6A8\n{}".format(
        time_word, saved_date.strftime("%d/%m/%Y, %H:%M")
    )
