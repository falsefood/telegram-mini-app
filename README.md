# Telegram Bot

A Python-based Telegram bot with menu-based interface and various features.

## Requirements

- Python 3.11.9
- Dependencies listed in `requirements.txt`

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the project root and add your Telegram bot token:
```
TELEGRAM_TOKEN=your_bot_token_here
```

## Running the Bot

1. Make sure your virtual environment is activated
2. Run the bot:
```bash
python main.py
```

## Features

- Interactive menu system with inline buttons
- Products listing
- Subscription management
- User profile viewing
- Help system

## Commands

- `/start` - Start the bot and show the main menu
- `/help` - Show help information

## Project Structure

```
.
├── bot.py              # Main bot implementation
├── requirements.txt    # Python dependencies
└── .env               # Environment configuration (create this)
```

## Security Notes

- Never commit your .env file
- Keep your tokens secure
- Use HTTPS in production
- Validate all payment callbacks 