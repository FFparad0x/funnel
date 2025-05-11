import os
import signal
import logging
import requests
from threading import Thread
from fastapi import FastAPI
import uvicorn
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from utils.config import TOKEN, MODE, load_channels, save_channels, OPENROUTER_API_KEY, logger
from handlers.bot_handlers import start, handle_model_command, handle_message, active_channels, handle_prompt_command, help_command, handle_ask_command, status_command

# Create FastAPI app
app = FastAPI()

@app.get("/livez")
async def livez():
    return {"status": "ok"}

def run_web_server():
    uvicorn.run(app, host="0.0.0.0", port=8080)

def startup_check():
    """Check if the OpenRouter API key is valid."""
    response = requests.get(
        url="https://openrouter.ai/api/v1/auth/key",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}"
        }
    )
    print(response.json())

async def load_initial_messages(application: Application):
    """Initialize channels from file when bot starts."""
    try:
        print("Loading channels from file...")
        # Load channels from file
        channels = load_channels()
        print(f"Found {len(channels)} channels in file")
        
        for channel_id in channels:
            try:
                print(f"Initializing channel: {channel_id}")
                try:
                    # Verify channel access
                    chat = await application.bot.get_chat(chat_id=channel_id)
                    print(f"Successfully verified access to channel {channel_id}")
                    active_channels.add(channel_id)
                except Exception as e:
                    print(f"Error accessing channel {channel_id}: {str(e)}")
                    continue
                    
            except Exception as e:
                print(f"Error initializing channel {channel_id}: {str(e)}")
                continue
    except Exception as e:
        print(f"Error in load_initial_messages: {str(e)}")

async def post_init(application: Application):
    """Post initialization handler."""
    print("Starting post initialization...")
    await load_initial_messages(application)
    print("Finished loading initial messages")

def main():

    # a = [1,2,3,4,5,6,7,8,9,10]
    # print(a[:-3:-1])
    # return

    """Start the bot."""
    if not TOKEN:
        logger.error("No token provided. Please set TELEGRAM_BOT_TOKEN in .env file")
        return

    print("Starting bot...")
    
    # Set up signal handlers
    def signal_handler(signum, frame):
        print("stopped")
        # Save channels before exit
        save_channels(active_channels)
        # Exit the program
        os._exit(0)

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Start web server in a separate thread
    web_server_thread = Thread(target=run_web_server, daemon=True)
    web_server_thread.start()
    print("Web server started on port 8080")
    
    # Load channels from YAML file
    channels = load_channels()
    active_channels.update(channels)
    print(f"Active channels after loading: {list(active_channels)}")

    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("model", handle_model_command))
    application.add_handler(CommandHandler("prompt", handle_prompt_command))
    application.add_handler(CommandHandler("ask", handle_ask_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT | ~filters.COMMAND | ~filters.REPLY | ~filters.FORWARDED, handle_message))

    # Add post initialization handler
    application.post_init = post_init

    print("Starting polling...")
    # Start the Bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        startup_check()
        main()
    except KeyboardInterrupt:
        print("stopped")
        # Save channels before exit
        save_channels(active_channels)
    except Exception as e:
        logger.error(f"Bot stopped due to error: {str(e)}")
        # Save channels even if there's an error
        save_channels(active_channels) 