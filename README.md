# Fanta Formazioni Reminder

Fanta Formazioni Reminder is a Telegram Bot written in Python that helps users manage and stay updated with their fantasy football (FantaCalcio) team lineups. This bot provides reminders and notifications for important events related to fantasy football, such as upcoming matchdays and deadlines for setting up your team's lineup.

## Table of Contents

- [Features](#features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
- [Usage](#usage)
- [Contributing](#contributing)
- [License](#license)
<!-- - [Configuration](#configuration) -->

## Features

- **Fantasy Football Reminders:** Get timely reminders for setting up your fantasy football lineup before the deadline.  
At the time of writing, the bot provides reminders 24 hours, 1 hour and 10 minute before the lineups deadline, set to 5 minutes before the start of the match-day.
- **User-Friendly Commands:** Interact with the bot using simple and intuitive Telegram commands.
- **Open Source:** This project is open source, allowing you to customize and contribute to its development.

### Upcoming Features

- **Customizable Settings:** Configure the bot to suit your preferences and timezone.

## Getting Started

To get started with Fanta Formazioni Reminder, follow these steps:

### Prerequisites

Before running the bot, you'll need the following:

- Python 3.x installed on your system. The bot is developed in Python 3.11.4.
- A Telegram account and a bot token obtained from the [BotFather](https://core.telegram.org/bots#botfather).

### Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/mpellicc/fanta-formazioni-reminder.git
   ```

2. Navigate to the project directory:

   ```bash
   cd fanta-formazioni-reminder
   ```

3. Install the required Python packages:

   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

4. Create a `.env` file in the project directory.  
   You can copy the configuration and then change the values from the env.example file with:

   ```bash
   cp env.enxample .env
   ```

   Or simply write it on your own.

5. Start the bot:

   ```bash
   python src\fantaformazionireminder\main.py
   ```

Now, your Fanta Formazioni Reminder bot should be up and running.

## Usage

The bot provides various commands to interact with it. You can start a chat with the bot and use the following commands:

- `/start`: Start a chat with the bot and get an introduction.
- `/aggiungi_data`: Save a custom date to be reminded in the chat you used this command.
- `/prossima_scadenza`: Display the next deadline for setting up your team's lineup.
- `/annulla`: Cancel an ongoing conversation with the bot.
- `/help`: Display a help message with available commands.

Feel free to explore and customize the bot's functionality as per your requirements.

<!-- ## Configuration

You can customize the bot's behavior by modifying the configuration settings in the `config.py` file. Here, you can adjust things like default timezone, notification intervals, and more to suit your preferences. -->

## Contributing

Contributions to this project are welcome! If you have ideas for improvements, bug fixes, or new features, please feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Disclaimer:** This project is not affiliated with or endorsed by Telegram or any fantasy football league or platform. It is a personal project created for educational and entertainment purposes.

Make sure to replace `YOUR_BOT_TOKEN` with your actual Telegram bot token and update the README with any additional information specific to your project. You may also want to include a section for troubleshooting or frequently asked questions if applicable.
