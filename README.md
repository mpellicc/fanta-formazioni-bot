# Fanta Formazioni Reminder

Fanta Formazioni Reminder is a Telegram Bot written in Python that helps users stay updated with their fantasy football (FantaCalcio) team lineups. This bot provides reminders and notifications for important events related to fantasy football, such as upcoming matchdays and deadlines for setting up your team's lineup.

## Table of Contents

- [Fanta Formazioni Reminder](#fanta-formazioni-reminder)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
    - [Notes](#notes)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
  - [Usage](#usage)
  - [Contributing](#contributing)
  - [License](#license)

## Features

- **FantaCalcio Reminders:** Get timely reminders for setting up your fantasy football lineup before the deadline.  
At the time of writing, the bot provides reminders 24 hours, 1 hour and 10 minute before the lineups deadline, set to 5 minutes before the start of the match-day.
- **User-Friendly Commands:** Interact with the bot using simple and intuitive Telegram commands.
- **Open Source:** This project is open source, allowing you to customize and contribute to its development.

### Notes

At the moment, the bot is developed in a way that lets it send the standard reminders in a channel ([@fantaformazionireminders](t.me/fantaformazionireminders)). This permits me to keep working on the development, while the users can have the notifications to set their FantaCalcio lineups.

Also consider that Telegram has a flood limit of 30 messages per second. My initial plan was to let the bot work in private and group chats, but this limitation could force me to change the behavior and just let the bot run in the channel, limiting its current and upcoming features.

The only command (other than `/start` and `/help`) that will probably be kept is `prossima_scadenza`, since it can be useful.

## Getting Started

To get started with Fanta Formazioni Reminder, follow these steps:

### Prerequisites

Before running the bot, you'll need the following:

- Python 3.x installed on your system. The bot is developed in Python 3.12.4.
- A Telegram account and a bot token obtained from the [BotFather](https://core.telegram.org/bots#botfather).

### Installation

1. Install Poetry by following [the official guide](https://python-poetry.org/docs/#installation).

2. Clone the repository:

   ```bash
   git clone https://github.com/mpellicc/fanta-formazioni-bot.git
   ```

3. Navigate to the project directory:

   ```bash
   cd fanta-formazioni-bot
   ```

4. Install the required Python packages:

   ```bash
   poetry install
   ```

5. Activate the virtual environment:

   ```bash
   poetry shell
   ```

6. Create a `.env` file in the project directory.  
   You can copy the configuration and then change the values from the env.example file with:

   ```bash
   cp env.example .env
   ```

   Or simply write it on your own.

7. Start the bot:

   ```bash
   python fantaformazionibot\main.py
   ```

Now, your Fanta Formazioni Reminder bot should be up and running.

Make sure to replace `YOUR_BOT_TOKEN` with your actual Telegram bot token and update the README with any additional information specific to your project. You may also want to include a section for troubleshooting or frequently asked questions if applicable.

## Usage

The bot provides various commands to interact with it. You can start a chat with the bot and use the following commands:

- `/start`: Start a chat with the bot and get an introduction.
- `/prossima_scadenza`: Display the next deadline for setting up your team's lineup.
- `/help`: Display a help message with available commands.

Feel free to explore and customize the bot's functionality as per your requirements.

## Contributing

Contributions to this project are welcome! If you have ideas for improvements, bug fixes, or new features, please feel free to open an issue or submit a pull request.

## License

This project is licensed under the GNU GPLv3 License - see the [COPYING](COPYING) file for details.

---

**Disclaimer:** This project is not affiliated with or endorsed by Telegram or any FantaCalcio league or platform. It is a personal project created for educational and entertainment purposes.
