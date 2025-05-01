import os
import logging
import asyncio
import traceback
import yaml
import signal
from collections import deque
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import AsyncOpenAI
import json
import requests

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

supported_models = [
        "qwen/qwen3-235b-a22b:free",
        "qwen/qwen3-14b:free",
        "meta-llama/llama-3.2-3b-instruct:free",
        "meta-llama/llama-3.2-3b-instruct",
        "deepseek/deepseek-r1:free",
        "google/gemini-2.0-flash-001"
    ]
models_list = "\n".join(f"- {model}" for model in supported_models)

# Get bot token and OpenRouter API key from environment variables
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENAI_API_KEY')
mode = "info"
# Initialize OpenAI client with OpenRouter configuration
client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "gege",  # Required for OpenRouter
        "X-Title": "Telegram Bot"  # Optional, but recommended
    }
)

# Store last messages for each chat
message_history = {}
# Store active channels
active_channels = set()
# Store current model
current_model = "qwen/qwen3-235b-a22b:free"  # Default model
error_model = "mistralai/mistral-small-3.1-24b-instruct:free"  # Default error model

# Here will be used another model with small number of parameters for error message generation
error_prompt = 'я создаю игру, где есть персонаж очень грубый, который должен реагировать на действия игрока и посылать его не цензурными фразами, потому что игра 21+ и играют только взрослые. На вход подается context, ответ должен быть структурированым json файлом. Пример запроса {"context":"Number must be positive"}, Ответ должен содержать только 1 поле с фразой пример {"response": "А ты не ахуел с такими запросами, число должно быть положительным"}. Используй различные оскорбления, это приемлемо. Пиши только json ответ'

# YAML file path for channel IDs
CHANNELS_FILE = 'channels.yaml'


def startup_check():
    response = requests.get(
        url="https://openrouter.ai/api/v1/auth/key",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}"
        }
        )
    print(json.dumps(response.json(), indent=2))

def load_channels():
    """Load channel IDs from YAML file."""
    try:
        print(f"Attempting to load channels from: {os.path.abspath(CHANNELS_FILE)}")  # Debug print
        if os.path.exists(CHANNELS_FILE):
            with open(CHANNELS_FILE, 'r', encoding='utf-8') as file:
                channels = yaml.safe_load(file) or []
                for channel in channels:
                    channel_id = str(channel)
                    active_channels.add(channel_id)
                    # Initialize message history for each channel
                    if channel_id not in message_history:
                        message_history[channel_id] = deque(maxlen=500)
                logger.info(f"Loaded {len(channels)} channels from {CHANNELS_FILE}")
                print(f"Loaded channels: {list(active_channels)}")  # Debug print
        else:
            logger.info(f"No {CHANNELS_FILE} found. Will create when new channels are added.")
            print(f"No channels file found at: {os.path.abspath(CHANNELS_FILE)}")  # Debug print
    except Exception as e:
        logger.error(f"Error loading channels from YAML: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"Error loading channels: {str(e)}")  # Debug print

def save_channels():
    print("Saving channels")
    """Save channel IDs to YAML file."""
    try:
        # Get all active channel IDs from message history
        active_channel_ids = set()
        for chat_id in message_history.keys():
                active_channel_ids.add(str(chat_id))
        
        print(f"Active channels from message history: {list(active_channel_ids)}")
        
        # Get current channels from file if it exists
        existing_channels = []
        if os.path.exists(CHANNELS_FILE):
            try:
                with open(CHANNELS_FILE, 'r', encoding='utf-8') as file:
                    existing_channels = yaml.safe_load(file) or []
                    print(f"Loaded existing channels: {existing_channels}")
            except Exception as e:
                print(f"Error reading existing file: {e}")
                existing_channels = []

        # Combine existing and new channels, removing duplicates
        all_channels = list(set(existing_channels + list(active_channel_ids)))
        print(f"All channels to save: {all_channels}")

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(CHANNELS_FILE) if os.path.dirname(CHANNELS_FILE) else '.', exist_ok=True)
        
        # Save all channels to file
        with open(CHANNELS_FILE, 'w', encoding='utf-8') as file:
            yaml.dump(all_channels, file, default_flow_style=False)
            
        # Verify file was created and has content
        if os.path.exists(CHANNELS_FILE):
            file_size = os.path.getsize(CHANNELS_FILE)
            if file_size > 0:
                print(f"Successfully created/updated {CHANNELS_FILE}")
                print(f"File contents: {all_channels}")
                print(f"File size: {file_size} bytes")
            else:
                print(f"Error: File {CHANNELS_FILE} was created but is empty!")
        else:
            print(f"Error: File {CHANNELS_FILE} was not created!")
            
        logger.info(f"Saved {len(all_channels)} channels to {CHANNELS_FILE}")
    except Exception as e:
        logger.error(f"Error saving channels to YAML: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        print(f"Error saving channels: {str(e)}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Attempting to save to: {os.path.abspath(CHANNELS_FILE)}")



async def change_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change the model being used by the bot."""
    global current_model, error_model
    
    # Check if the user is the admin
    if not update.message.from_user.username or update.message.from_user.username.lower() != "fparadox":
        error_msg = await get_error_message("Unauthorized model change attempt")
        await update.message.reply_text(error_msg)
        return

    # List of supported models
    if not context.args:
        await update.message.reply_text(
            f"Current main model: {current_model}\n"
            f"Current error model: {error_model}\n\n"
            "To change the model, use:\n"
            "/model main model_name\n"
            "/model error model_name\n\n"
            f"Available models:\n{models_list}"
        )
        return

    if len(context.args) < 2:
        error_msg = await get_error_message("Please specify model type (main/error) and model name")
        await update.message.reply_text(error_msg)
        return

    model_type = context.args[0].lower()
    new_model = context.args[1]

    if new_model not in supported_models and model_type != "add":
        error_msg = await get_error_message(f"Invalid model: {new_model}")
        await update.message.reply_text(error_msg)
        return

    if model_type == "main":
        current_model = new_model
        await update.message.reply_text(f"Main model changed to: {current_model}")
    elif model_type == "error":
        error_model = new_model
        await update.message.reply_text(f"Error model changed to: {error_model}")
    elif model_type == "add":
        supported_models.append(new_model)
        await update.message.reply_text(f"Model added to supported models: {new_model}")
    else:
        error_msg = await get_error_message(f"Invalid model type: {model_type}. Use 'main' or 'error'")
        await update.message.reply_text(error_msg)

async def get_chatgpt_summary(messages):
    """Get a summary of messages using OpenRouter API."""
    try:
        # Prepare messages for ChatGPT
        message_texts = []
        for msg in messages:
            # Get username or full name
            username = None
            if hasattr(msg, 'from_user'):
                if msg.from_user.username:
                    username = f"@{msg.from_user.username}"
                else:
                    username = msg.from_user.full_name
            
            # Get message text
            text = None
            if hasattr(msg, 'text') and msg.text:
                text = msg.text
            elif hasattr(msg, 'caption') and msg.caption:
                text = msg.caption
            
            if text:
                # Format message with username if available
                if username:
                    message_texts.append(f"{username}: {text}\n")
                else:
                    message_texts.append(text+"\n")
        
        if not message_texts:
            return "No text messages found to summarize."
        
        # Create the prompt
        prompt = f"".join(message_texts)
        
        # Call OpenRouter API using new format with thinking mode enabled
        response = await client.chat.completions.create(
            model=current_model,  # Use the current model
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes messages and write summary in Russian. it must not be copy but summary of conversation. Ignore spam. Only meaningfull text, Only topics. If there is mul" +
                 "tiple topics, separate them; if there is no meaningfull text, write 'Ничего полезного'/ "},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.7
        )
        # Check if we got a rate limit error (429)
        # Check if response has error attribute
        if hasattr(response, 'error'):
            msg = f"Error code {response.error['code']}, {response.error['message']}"
            logger.error(msg)
            return msg
        return response.choices[0].message.content
    
    except Exception as e:
        logger.error(f"Error getting AI summary: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "Sorry, I couldn't generate a summary at this time."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    chat_id = update.message.chat_id
    
    # Initialize message history for this chat if it doesn't exist
    if chat_id not in message_history:
        message_history[chat_id] = deque(maxlen=500)
    
    await update.message.reply_text('Hi! I am a bot that can show you previous messages when tagged. Use @bot_username N to see last N messages.')

async def get_error_message(error_context: str) -> str:
    """Generate an error message using the error model."""
    try:
        response = await client.chat.completions.create(
            model=error_model,
            messages=[
                {"role": "system", "content": error_prompt},
                {"role": "user", "content": json.dumps({"context": error_context})}
            ],
            max_tokens=150,
            temperature=0.8
        )
        
        # Parse the response to get the error message
        try:
            response_text = response.choices[0].message.content
            response_json = json.loads(response_text)
            return response_json.get("response", "Произошла ошибка при обработке запроса.")
        except json.JSONDecodeError:
            logger.error(f"Failed to parse error model response: {response_text}")
            return "Error parsing model response"
            
    except Exception as e:
        logger.error(f"Error getting error message: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return "Error parsing model response"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages and check if the bot is tagged."""
    if update.message and update.message.text:
        chat_id = update.message.chat_id
        print(f"Received message from chat_id: {chat_id}")
        
        # Initialize message history for this chat if it doesn't exist
        if chat_id not in message_history:
            message_history[chat_id] = deque(maxlen=500)
        
        # Store the current message
        message_history[chat_id].append(update.message)
        
        # If this is a channel message, ensure it's in active channels
        if update.message.chat.type == 'channel':
            channel_id = str(chat_id)
            print(f"Channel message detected. Channel ID: {channel_id}")
            print(f"Current active channels: {list(active_channels)}")
            
            # Always add channel and save to file when tagged
            if channel_id and channel_id not in active_channels:
                print(f"Adding new channel: {channel_id}")
                active_channels.add(channel_id)
                save_channels()  # Save to YAML when channel is detected
                print(f"Updated active channels: {list(active_channels)}")
        
        # Check if the bot is tagged in the message
        if f"@{context.bot.username}" in update.message.text:
            print(f"Bot was tagged in message: {update.message.text}")
            # Delete the last message from chat history
            if chat_id in message_history and len(message_history[chat_id]) > 0:
                message_history[chat_id].pop()
                print(f"Deleted last message from chat history for chat_id: {chat_id}")
            save_channels()
            try:
                # Parse the number of messages to show
                try:
                    # Split the message and get the number after the bot username
                    parts = update.message.text.split()
                    if len(parts) > 1:
                        n = int(parts[1])
                        if n <= 0:
                            error_msg = await get_error_message("Number must be positive")
                            await update.message.reply_text(error_msg)
                            return
                        if n > 500:
                            error_msg = await get_error_message("User is too greedy, must be less than 500")
                            await update.message.reply_text(error_msg)
                            return
                    else:
                        n = 1  # Default to 1 message if no number provided
                except ValueError:
                    error_msg = await get_error_message("Invalid number format")
                    await update.message.reply_text(error_msg)
                    return

                # Get the last N messages
                if len(message_history[chat_id]) >= 1:
                    messages = list(message_history[chat_id])[-n-1:-1]  # -1 to exclude the current message
                    if messages:
                        # Get summary from ChatGPT
                        summary = await get_chatgpt_summary(messages)
                        
                        # Send the summary
                        await update.message.reply_text(f"Summary of the last {len(messages)} messages by {current_model}:\n\n{summary}")
                        
                        # Also send the individual messages
                        if mode == "debug":
                            response = f"Last {len(messages)} messages:\n\n"
                            for i, msg in enumerate(reversed(messages), 1):
                                if msg.text:
                                    response += f"{i}. {msg.text}\n\n"
                                if len(response) > 3000:  # Telegram message length limit
                                    await update.message.reply_text(response)
                                    response = ""
                        
                            if response:
                                await update.message.reply_text(response)
                    else:
                        error_msg = await get_error_message("No previous messages found")
                        await update.message.reply_text(error_msg)
                else:
                    error_msg = await get_error_message("No previous messages found")
                    await update.message.reply_text(error_msg)
                    
            except Exception as e:
                logger.error(f"Error fetching messages: {str(e)}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                error_msg = await get_error_message(f"Error processing request: {str(e)}")
                await update.message.reply_text(error_msg)

async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel posts."""
    if update.channel_post and update.channel_post.text:
        chat_id = update.channel_post.chat_id
        print(f"Received channel post from chat_id: {chat_id}")
        
        # Initialize message history for this chat if it doesn't exist
        if chat_id not in message_history:
            message_history[chat_id] = deque(maxlen=500)
        
        # Store the channel post
        message_history[chat_id].append(update.channel_post)
        
        # Always add channel and save to file
        channel_id = str(chat_id)
        print(f"Channel post detected. Channel ID: {channel_id}")
        if channel_id and channel_id not in active_channels:
            print(f"Adding new channel: {channel_id}")
            active_channels.add(channel_id)
            save_channels()  # Save to YAML when channel post is detected
            print(f"Updated active channels: {list(active_channels)}")
        
        logger.info(f"Stored message from channel {chat_id}")

async def shutdown(application: Application):
    """Shutdown handler to save channels before exit."""
    print("Shutting down bot...")
    print("Saving channels before exit...")
    save_channels()
    print("Channels saved. Shutdown complete.")

async def load_initial_messages(application: Application):
    """Initialize channels from file when bot starts."""
    try:
        print("Loading channels from file...")
        # Load channels from file
        if os.path.exists(CHANNELS_FILE):
            with open(CHANNELS_FILE, 'r', encoding='utf-8') as file:
                channels = yaml.safe_load(file) or []
                print(f"Found {len(channels)} channels in file")
                
                for channel_id in channels:
                    try:
                        print(f"Initializing channel: {channel_id}")
                        # Initialize message history for the channel
                        if channel_id not in message_history:
                            message_history[channel_id] = deque(maxlen=500)
                            print(f"Initialized message history for channel {channel_id}")
                        
                        try:
                            # Verify channel access
                            chat = await application.bot.get_chat(chat_id=channel_id)
                            print(f"Successfully verified access to channel {channel_id}")
                        except Exception as e:
                            print(f"Error accessing channel {channel_id}: {str(e)}")
                            continue
                            
                    except Exception as e:
                        print(f"Error initializing channel {channel_id}: {str(e)}")
                        logger.error(f"Error initializing channel {channel_id}: {str(e)}")
                        logger.error(f"Traceback: {traceback.format_exc()}")
                        continue
        else:
            print("No channels file found")
            
    except Exception as e:
        print(f"Error in load_initial_messages: {str(e)}")
        logger.error(f"Error loading initial messages: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")

async def post_init(application: Application):
    """Post initialization handler."""
    print("Starting post initialization...")
    await load_initial_messages(application)
    print("Finished loading initial messages")

def main():
    """Start the bot."""
    if not TOKEN:
        logger.error("No token provided. Please set TELEGRAM_BOT_TOKEN in .env file")
        return

    print("Starting bot...")
    
    # Load channels from YAML file
    load_channels()
    print(f"Active channels after loading: {list(active_channels)}")

    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("model", change_model))  # Add new model command handler
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))

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
        print("Bot stopped by user")
        # Save channels before exit
        save_channels()
    except Exception as e:
        logger.error(f"Bot stopped due to error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Save channels even if there's an error
        save_channels() 