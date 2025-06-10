import json
import logging
from openai import AsyncOpenAI
from utils.config import OPENROUTER_API_KEY, SUPPORTED_MODELS, MODE
from utils.channel_config import channel_config
from utils.default_config import CURRENT_MODEL, ERROR_MODEL, MAIN_PROMPT, ERROR_PROMPT, TEMPERATURE
from utils.stats import request_stats
from typing import Optional
import re

logger = logging.getLogger(__name__)

# Initialize OpenAI client with OpenRouter configuration
client = AsyncOpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    default_headers={
        "HTTP-Referer": "gege",  # Required for OpenRouter
        "X-Title": "Telegram Bot"  # Optional, but recommended
    }
)

def change_prompt(model_type: str, new_prompt: str, channel_id: Optional[str] = None) -> tuple[bool, str]:
    """Change the prompt for a specific model type."""
    if channel_id:
        success = channel_config.update_channel_config(channel_id, f"{model_type}_prompt", new_prompt)
        if success:
            return True, f"{model_type.capitalize()} prompt changed for channel {channel_id}"
        return False, f"Failed to update {model_type} prompt for channel {channel_id}"
    
    global MAIN_PROMPT, ERROR_PROMPT
    if model_type == "main":
        MAIN_PROMPT = new_prompt
        return True, f"Main prompt changed"
    elif model_type == "error":
        ERROR_PROMPT = new_prompt
        return True, f"Error prompt changed"
    else:
        return False, f"Invalid model type: {model_type}. Use 'main' or 'error'"

async def get_chatgpt_summary(messages, model=None, channel_id: Optional[str] = None):
    """Get a summary of messages using OpenRouter API."""
    try:
        # Get channel-specific configuration
        config = channel_config.get_channel_config(channel_id) if channel_id else None
        model = model or (config["main_model"] if config else CURRENT_MODEL)
        prompt = config["main_prompt"] if config else MAIN_PROMPT
        temp = config["temp_model"] if config else TEMPERATURE
        # Track request
        request_stats.increment(channel_id or "default")

        # Prepare messages for ChatGPT
        message_texts = []
        for msg in messages:
            # Get username or full name
            username = ""
            if msg.from_user:
                if msg.from_user.username:
                    username += f"@{msg.from_user.username}"
                elif msg.effective_name:
                    username += msg.effective_name
                else:
                    username += msg.from_user.full_name
            if msg.forward_from_chat:
                username += f" forwarded from chat {msg.forward_from_chat.effective_name}"
            if msg.forward_from:
                username += f" forwarded from user {msg.forward_from.username}"
            # Get message text
            text = ""
            if hasattr(msg, 'text') and msg.text:
                text += msg.text
            if hasattr(msg, 'caption') and msg.caption:
                text += f" Caption: {msg.caption}"
            if hasattr(msg, 'reply_to_message') and msg.reply_to_message:
                text += f" In response to '{msg.reply_to_message.caption} {msg.reply_to_message.text}'"
            if text != "":
                # Format message with username if available
                if username != "":
                    message_texts.append(f"{username}: {text}\n")
                else:
                    message_texts.append(text+"\n")
        
        if not message_texts:
            return "No text messages found to summarize."
        
        # Create the prompt
        prompt_text = f"".join(message_texts)
        
        # Call OpenRouter API
        if MODE == "debug":
            return "Debug mode"
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Use htlm, allowed tags: <b> for bold,<i> for italic,<u> for underline,<s>for strikethrough,<a> for links,<blockquote> for quotes. Every other tag and markdown style are not allowed"},
                {"role": "system", "content": prompt},
                {"role": "user", "content": prompt_text}
            ],
            max_tokens=15000,
            temperature=float(temp)
        )
        
        if hasattr(response, 'error'):
            msg = f"Error code {response.error['code']}, {response.error['message']}"
            logger.error(msg)
            return msg
        return  remove_all_except_specified_tags(response.choices[0].message.content)

    except Exception as e:
        logger.error(f"Error getting AI summary: {str(e)}")
        return "Sorry, I couldn't generate a summary at this time."
def remove_all_except_specified_tags(text):
    """Remove all HTML tags except <b>, <i>, <u>, <s>, <a>, and <blockquote> with all their attributes."""
    # Pattern matches any HTML tag that is NOT in our allowed list
    pattern = re.compile(
        r'''<(?!\/?(b|i|u|s|a|blockquote)\b)[^>]+>''',
        flags=re.IGNORECASE
    )
    clean_text = pattern.sub('', text)
    return clean_text


async def get_chatgpt_ask(question, model=None, channel_id: Optional[str] = None):
    """Get a response for a direct question using OpenRouter API."""
    try:
        # Get channel-specific configuration
        config = channel_config.get_channel_config(channel_id) if channel_id else None
        model = model or (config["main_model"] if config else CURRENT_MODEL)
        
        # Track request
        request_stats.increment(channel_id or "default", is_ask=True)

        # Call OpenRouter API
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Ты полезный ассистент. Дай чистый ответ на русском, используй разметку для telegram - Markdown. bold text for titles **title**, italic simple text for normal text"},
                {"role": "user", "content": question}
            ],
            max_tokens=15000,
            temperature=0.7
        )
        
        if hasattr(response, 'error'):
            msg = f"Error code {response.error['code']}, {response.error['message']}"
            logger.error(msg)
            return msg
        return response.choices[0].message.content
    
    except Exception as e:
        logger.error(f"Error getting AI response: {str(e)}")
        return "Sorry, I couldn't generate a response at this time."

async def get_error_message(error_context: str, channel_id: Optional[str] = None) -> str:
    """Generate an error message using the error model."""
    try:
        # Get channel-specific configuration
        config = channel_config.get_channel_config(channel_id) if channel_id else None
        model = config["error_model"] if config else ERROR_MODEL
        prompt = config["error_prompt"] if config else ERROR_PROMPT

        # Track request
        request_stats.increment(channel_id or "default")

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": 'На вход подается "context" - поле содержит стиль ответа на ошибку в поле "error", ответ должен быть структурированым json файлом. Пример запроса {"context":"ты добрый дедушка", "error":"Number must be positive"}, Ответ должен содержать только 1 поле с фразой пример {"response": "Ну как же так внучок, число должно быть положительным"}. Стиль ответа задан в поле context, ошибка на тексте которой создавать ответ в поле error. Если не знаешь что ответить, отвечай "Не знаю что ответить" и не используй другие фразы'},
                {"role": "user", "content": json.dumps({"context": prompt, "error":error_context})}
            ],
            max_tokens=10000,
        )
        
        try:
            response_text = response.choices[0].message.content
            logger.info(f"Raw model response: {response_text}")
            
            # Handle markdown code block wrapping
            if response_text.startswith('```json'):
                response_text = response_text[7:]  # Remove ```json
                logger.info("Removed ```json prefix")
            elif response_text.startswith('```'):
                response_text = response_text[3:]  # Remove ```
                logger.info("Removed ``` prefix")
            
            if response_text.endswith('```'):
                response_text = response_text[:-3]  # Remove trailing ```
                logger.info("Removed trailing ```")
            
            # Clean up any whitespace
            response_text = response_text.strip()
            logger.info(f"Cleaned response text: {response_text}")
            
            try:
                response_json = json.loads(response_text)
                logger.info(f"Successfully parsed JSON: {response_json}")
                return response_json.get("response", "Произошла ошибка при обработке запроса.")
            except json.JSONDecodeError as json_err:
                logger.error(f"JSON parsing error: {str(json_err)}")
                logger.error(f"Failed to parse text: {response_text}")
                # Try to extract JSON-like content using regex
                import re
                json_match = re.search(r'\{.*\}', response_text)
                if json_match:
                    try:
                        extracted_json = json.loads(json_match.group())
                        logger.info(f"Successfully extracted and parsed JSON: {extracted_json}")
                        return extracted_json.get("response", "Произошла ошибка при обработке запроса.")
                    except json.JSONDecodeError:
                        logger.error("Failed to parse extracted JSON")
                return "Error parsing model response"
        except Exception as e:
            logger.error(f"Error processing response: {str(e)}")
            logger.error(f"Response text: {response_text}")
            return "Error processing model response"
            
    except Exception as e:
        logger.error(f"Error getting error message: {str(e)}")
        return "Error parsing model response"

def change_model(model_type: str, new_model: str, channel_id: Optional[str] = None) -> tuple[bool, str]:
    """Change the model being used by the bot."""
    if channel_id:
        success = channel_config.update_channel_config(channel_id, f"{model_type}_model", new_model)
        if success:
            return True, f"{model_type.capitalize()} model changed to {new_model} for channel {channel_id}"
        return False, f"Failed to update {model_type} model for channel {channel_id}"
    
    global CURRENT_MODEL, ERROR_MODEL
    
    if new_model not in SUPPORTED_MODELS and model_type != "add":
        return False, f"Invalid model: {new_model}"
    
    if model_type == "main":
        CURRENT_MODEL = new_model
        return True, f"Main model changed to: {CURRENT_MODEL}"
    elif model_type == "error":
        ERROR_MODEL = new_model
        return True, f"Error model changed to: {ERROR_MODEL}"
    elif model_type == "add":
        SUPPORTED_MODELS.append(new_model)
        return True, f"Model added to supported models: {new_model}"
    else:
        return False, f"Invalid model type: {model_type}. Use 'main' or 'error'" 