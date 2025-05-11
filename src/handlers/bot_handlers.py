import logging
from collections import deque
from telegram import Update
from telegram.ext import ContextTypes
from models.llm import get_chatgpt_summary, get_error_message, change_model, CURRENT_MODEL, ERROR_MODEL, change_prompt, get_chatgpt_ask
from utils.config import MODE, SUPPORTED_MODELS
from utils.channel_config import channel_config

logger = logging.getLogger(__name__)

# Store last messages for each chat
message_history = {}
# Store active channels
active_channels = set()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    chat_id = update.message.chat_id
    
    # Initialize message history for this chat if it doesn't exist
    if chat_id not in message_history:
        message_history[chat_id] = deque(maxlen=500)
    
    await update.message.reply_text(
        'Hi! I am a bot that can show you previous messages when tagged. Use @bot_username N to see last N messages.',
        parse_mode='Markdown'
    )

async def handle_model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /model command to change models."""
    # Check if the user is the admin
    if not update.message.from_user.username or update.message.from_user.username.lower() != "fparadox":
        error_msg = await get_error_message("Unauthorized model change attempt", str(update.message.chat_id))
        await update.message.reply_text(error_msg, parse_mode='Markdown')
        return

    # List of supported models
    if not context.args:
        models_list = "\n".join(f"- `{model}`" for model in SUPPORTED_MODELS)
        channel_id = str(update.message.chat_id)
        config = channel_config.get_channel_config(channel_id)
        await update.message.reply_text(
            f"*Current Settings for Channel {channel_id}:*\n"
            f"Main Model: `{config['main_model']}`\n"
            f"Error Model: `{config['error_model']}`\n\n"
            "*To change the model, use:*\n"
            "/model main model_name\n"
            "/model error model_name\n\n"
            f"*Available models:*\n{models_list}",
            parse_mode='Markdown'
        )
        return

    if len(context.args) < 2:
        error_msg = await get_error_message("Please specify model type (main/error) and model name", str(update.message.chat_id))
        await update.message.reply_text(error_msg, parse_mode='Markdown')
        return

    model_type = context.args[0].lower()
    new_model = context.args[1]
    channel_id = context.args[2] if len(context.args) > 2 else str(update.message.chat_id)

    success, message = change_model(model_type, new_model, channel_id)
    if not success:
        error_msg = await get_error_message(message, str(update.message.chat_id))
        await update.message.reply_text(error_msg, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"`{message}`", parse_mode='Markdown')

async def handle_prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /prompt command to change prompts."""
    # Check if the user is the admin
    if not update.message.from_user.username or update.message.from_user.username.lower() != "fparadox":
        error_msg = await get_error_message("Unauthorized prompt change attempt", str(update.message.chat_id))
        await update.message.reply_text(error_msg, parse_mode='Markdown')
        return

    if not context.args or len(context.args) < 2:
        channel_id = str(update.message.chat_id)
        config = channel_config.get_channel_config(channel_id)
        await update.message.reply_text(
            f"*Current Prompts for Channel {channel_id}:*\n"
            f"Main Prompt: `{config['main_prompt']}`\n"
            f"Error Prompt: `{config['error_prompt']}`\n\n"
            "*To change the prompt, use:*\n"
            "/prompt main your new prompt\n"
            "/prompt error your new prompt\n",
            parse_mode='Markdown'
        )
        return

    model_type = context.args[0].lower()
    # Check if the last argument is a channel ID
    if context.args[-1].isdigit():
        channel_id = context.args[-1]
        new_prompt = " ".join(context.args[1:-1])
    else:
        channel_id = str(update.message.chat_id)
        new_prompt = " ".join(context.args[1:])

    success, message = change_prompt(model_type, new_prompt, channel_id)
    if not success:
        error_msg = await get_error_message(message, str(update.message.chat_id))
        await update.message.reply_text(error_msg, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"`{message}`", parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages and check if the bot is tagged."""
    if update.message:
        chat_id = str(update.message.chat_id)
        if MODE == 'debug' and chat_id not in active_channels:
            return
        logger.info(f"Received message from chat_id: {chat_id}")
        
        # Initialize message history for this chat if it doesn't exist
        if chat_id not in message_history:
            message_history[chat_id] = deque(maxlen=500)
        
        # Store the current message
        message_history[chat_id].append(update.message)
        
        if update.message.text == None: 
            return
        # Check if the bot is tagged in the message
        if f"@{context.bot.username}" in update.message.text:
            logger.info(f"Bot was tagged in message: {update.message.text}")
            # Delete the last message from chat history
            if chat_id in message_history and len(message_history[chat_id]) > 0:
                message_history[chat_id].pop()
                logger.info(f"Deleted last message from chat history for chat_id: {chat_id}")
            
            try:
                # Parse the number of messages to show
                try:
                    # Split the message and get the number after the bot username
                    parts = update.message.text.split()
                    if len(parts) > 1:
                        n = int(parts[1])
                        if n <= 0:
                            error_msg = await get_error_message("Number must be positive", chat_id)
                            await update.message.reply_text(error_msg, parse_mode='Markdown')
                            return
                        if n > 500:
                            error_msg = await get_error_message("User is too greedy, must be less than 500", chat_id)
                            await update.message.reply_text(error_msg, parse_mode='Markdown')
                            return
                    else:
                        if n > len(message_history[chat_id]):
                            n = len(message_history[chat_id])-1
                        n = 1  # Default to 1 message if no number provided
                except ValueError:
                    error_msg = await get_error_message("Invalid number format", chat_id)
                    await update.message.reply_text(error_msg, parse_mode='Markdown')
                    return

                # Get the last N messages
                if len(message_history[chat_id]) > 0:
                    m2 = list(message_history[chat_id])
                    messages = m2[-n:]  # Get the last n messages
                    if messages:
                        # Get summary from ChatGPT using channel-specific configuration
                        summary = await get_chatgpt_summary(messages, channel_id=chat_id)
                        
                        # Send the summary
                        await update.message.reply_text(
                            f"*Summary of the last {len(messages)} messages:*\n\n{summary}",
                            parse_mode='Markdown'
                        )
                        
                        # Also send the individual messages
                        if MODE == "debug":
                            response = f"*Last {len(messages)} messages:*\n\n"
                            for i, msg in enumerate(messages, 1):
                                if msg.text:
                                    response += f"{i}. `{msg.text}`\n\n"
                                if len(response) > 3000:  # Telegram message length limit
                                    await update.message.reply_text(response, parse_mode='Markdown')
                                    response = ""
                        
                            if response:
                                await update.message.reply_text(response, parse_mode='Markdown')
                    else:
                        error_msg = await get_error_message("No previous messages found", chat_id)
                        await update.message.reply_text(error_msg, parse_mode='Markdown')
                else:
                    error_msg = await get_error_message("No previous messages found", chat_id)
                    await update.message.reply_text(error_msg, parse_mode='Markdown')
                    
            except Exception as e:
                logger.error(f"Error fetching messages: {str(e)}")
                error_msg = await get_error_message(f"Error processing request: {str(e)}", chat_id)
                await update.message.reply_text(error_msg, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    help_text = """🤖 *FunnelBot Commands*

*Commands:*
@FunnelReadsBot N \\- Show summary of last N messages \\(default: 1\\)
Example: @FunnelReadsBot 5 \\- shows summary of last 5 messages

/ask \\[question\\] \\- Ask a direct question to the AI
Example: `/ask дай мне рецепт пиццы`

/prompt \\[main/error\\] \\[prompt\\] \\- Change the prompt
Example: `/prompt@FunnelReadsBot error act as a nice guy \\- Заставить отвечать как хороший парень при`

*Admin Commands:*
/model \\[main/error\\] \\[model\\_name\\] \\- Change the model 
Example: `/model@FunnelReadsBot main deepseek/deepseek-r1-distill-llama-70b`
Find available models at: [OpenRouter Models](https://openrouter\\.ai/models)

*Notes:*
• Maximum message history: 500 messages
• Only admin can change models and prompts
• Bot must be added to channels to work
• In debug mode, bot only responds in special debug channel

*Current Settings:*
Main Model: `{main_model}`
Error Model: `{error_model}`

For more information, contact the bot administrator @Fparadox\.""".format(
        main_model=CURRENT_MODEL.replace('.', '\\.'),
        error_model=ERROR_MODEL.replace('.', '\\.')
    )
    
    await update.message.reply_text(help_text, parse_mode='MarkdownV2')

async def handle_ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /ask command to make direct requests to the model."""
    if not context.args:
        await update.message.reply_text(
            "*Usage:*\n"
            "/ask your question here\n"
            "Example: `/ask what is the capital of France?`",
            parse_mode='Markdown'
        )
        return

    # Join all arguments to form the question
    question = " ".join(context.args)
    
    try:
        if question == "":
            error_msg = await get_error_message("Wrong request, no question provided", str(update.message.chat_id))
            await update.message.reply_text(error_msg, parse_mode='Markdown')
            return

        # Get response using channel-specific configuration
        response = await get_chatgpt_ask(question, channel_id=str(update.message.chat_id))
        await update.message.reply_text(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error processing ask command: {str(e)}")
        error_msg = await get_error_message(f"Error processing request: {str(e)}", str(update.message.chat_id))
        await update.message.reply_text(error_msg, parse_mode='Markdown') 