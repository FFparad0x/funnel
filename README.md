# Telegram Channel Message Reader Bot

This bot reads messages from a specified Telegram channel and responds with the last 100 messages when tagged.

## Setup

1. Create a new bot using [@BotFather](https://t.me/botfather) on Telegram and get your bot token.

2. Create a `.env` file in the project root with the following content:
```
TELEGRAM_BOT_TOKEN=your_bot_token_here
CHANNEL_ID=your_channel_id_here
```

3. Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Important Notes

1. The bot must be an admin of the channel to read messages.
2. To get the channel ID:
   - Forward a message from your channel to [@username_to_id_bot](https://t.me/username_to_id_bot)
   - The bot will show you the channel ID (it will be in the format `-100xxxxxxxxxx`)

## Running the Bot

Run the bot using:
```bash
python bot.py
```

## Usage

1. Add the bot to your channel as an admin
2. Tag the bot in any chat with `@your_bot_username`
3. The bot will respond with the last 100 messages from the specified channel

## Features

- Reads last 100 messages from the specified channel
- Responds when tagged
- Handles message length limits by splitting responses
- Error handling and logging "# funnel" 
