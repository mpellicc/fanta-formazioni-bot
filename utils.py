from datetime import timedelta


# TODO better handling of time_difference to let the message be more variable
def get_expiry_message(time_difference: timedelta, saved_date: any):
    processed_time = time_difference.total_seconds()
    time_word = (
        "24 ore"
        if processed_time >= 80000
        else "un'ora"
        if processed_time >= 59 or processed_time <= 61
        else "{} minuti".format(time_difference.seconds() / 60)
    )

    return "\U0001F6A8 Circa {} alla scadenza della formazione \U0001F6A8\n{}".format(
        time_word, saved_date.strftime("%d/%m/%Y, %H:%M")
    )
