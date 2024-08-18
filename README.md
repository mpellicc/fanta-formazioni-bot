
# FantaFormazioni Bot

FantaFormazioni Bot is a Telegram bot written in Python designed to help users stay updated with their Fantacalcio team lineups. The bot provides reminder notifications about the deadlines for setting up your team's lineup.

## Table of Contents

- [FantaFormazioni Bot](#fantaformazioni-bot)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
    - [Important](#important)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
  - [Usage](#usage)
  - [Contributing](#contributing)
  - [License](#license)

## Features

- **Fantacalcio Reminders:** Receive reminders to set up your fantasy football lineup before the deadline.  
  - Reminders are sent 24 hours, 1 hour, and 5 minutes before the lineup deadline, which is set to 5 minutes before the start of the matchday.
- **User-Friendly Commands:** Interact with the bot using simple and intuitive Telegram commands.
- **Open Source:** This project is open source, allowing you to customize and contribute to its development.

### Important

Currently, the bot sends standard reminders in a dedicated channel [@fantaformazionireminders](t.me/fantaformazionireminders). This approach allows ongoing development while still providing users with notifications to set their Fantacalcio lineups.

**Note:** Telegram imposes a flood limit of 30 messages per second. Initially, the bot was intended to work in private and group chats, but this limitation might necessitate restricting the bot to channel-only operation, which could limit current and upcoming features.

## Getting Started

To get started with FantaFormazioni Bot, follow these steps:

### Prerequisites

Before running the bot, ensure you have the following:

- Python 3.9+ installed on your system (the bot is developed in Python 3.12.4).
- A Telegram account and a bot token obtained from the [BotFather](https://core.telegram.org/bots#botfather).

### Installation

> **Note:** This guide uses [Poetry](https://python-poetry.org/), but you can use [pip](https://pip.pypa.io/en/stable/getting-started/) as well. A `requirements.txt` file is provided for pip users.

1. **Install Poetry** by following [the official guide](https://python-poetry.org/docs/#installation).

2. **Clone the repository:**

   ```bash
   git clone https://github.com/mpellicc/fanta-formazioni-bot.git
   ```

3. **Navigate to the project directory:**

   ```bash
   cd fanta-formazioni-bot
   ```

4. **Install the required Python packages:**

   ```bash
   poetry install
   ```

5. **Activate the virtual environment:**

   ```bash
   poetry shell
   ```

6. **Set up the environment variables:**
   - Create a `.env` file in the project directory.
   - You can copy the template from `env.example`:

     ```bash
     cp env.example .env
     ```

   - Update the `.env` file with your specific configuration values.

7. **Start the bot:**

   ```bash
   python fantaformazionibot/main.py
   ```

Your FantaFormazioni Bot should now be up and running.

## Usage

The bot provides various commands for interacting with it. Start a chat with the bot and use the following commands:

- `/start`: Start a chat with the bot and receive an introduction.
- `/prossima_scadenza`: Display the next deadline for setting up your team's lineup.
- `/help`: Display a help message with available commands.

Feel free to explore and customize the bot's functionality to suit your needs.

## Contributing

Contributions are welcome! If you have ideas for improvements, bug fixes, or new features, please open an issue or submit a pull request.

## License

This project is licensed under the GNU GPLv3 License. See the [COPYING](COPYING) file for details.

---

**Disclaimer:** This project is not affiliated with or endorsed by Telegram or any Fantacalcio league or platform. It is a personal project created for educational and entertainment purposes.
