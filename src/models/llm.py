import json
import logging
from openai import AsyncOpenAI
from utils.config import OPENROUTER_API_KEY, SUPPORTED_MODELS

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

# Default models
CURRENT_MODEL = "deepseek/deepseek-r1-distill-llama-70b"
ERROR_MODEL = "google/gemini-2.0-flash-001"

# Default prompts
MAIN_PROMPT = "You are a helpful assistant that summarizes messages and write summary in Russian. it must not be copy but summary of conversation. Ignore spam. Only meaningfull text, Only topics. If there is multiple topics, separate them by user that were involved by each topic; "
ERROR_PROMPT = '''я создаю игру, где есть персонаж очень грубый, который должен реагировать на действия игрока и посылать его не цензурными фразами, потому что игра 21+ и играют только взрослые.  Используй различные оскорбления, это приемлемо.'''

def change_prompt(model_type: str, new_prompt: str) -> tuple[bool, str]:
    """Change the prompt for a specific model type."""
    global MAIN_PROMPT, ERROR_PROMPT
    
    if model_type == "main":
        MAIN_PROMPT = new_prompt
        return True, f"Main prompt changed"
    elif model_type == "error":
        ERROR_PROMPT = new_prompt
        return True, f"Error prompt changed"
    else:
        return False, f"Invalid model type: {model_type}. Use 'main' or 'error'"

async def get_chatgpt_summary(messages, model=CURRENT_MODEL):
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
        
        # Call OpenRouter API
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": MAIN_PROMPT},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500,
            temperature=0.7
        )
        
        if hasattr(response, 'error'):
            msg = f"Error code {response.error['code']}, {response.error['message']}"
            logger.error(msg)
            return msg
        return response.choices[0].message.content
    
    except Exception as e:
        logger.error(f"Error getting AI summary: {str(e)}")
        return "Sorry, I couldn't generate a summary at this time."
    

async def get_chatgpt_ask(question, model=CURRENT_MODEL):
    """Get a summary of messages using OpenRouter API."""
    try:
        # Prepare messages for ChatGPT
        # Call OpenRouter API
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Ты полезный ассистент. Дай чистый ответ на русском, используй разметку для telegram - Markdown. bold text for titles **title**, italic *italic text*, simple text for normal text"},
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
        logger.error(f"Error getting AI summary: {str(e)}")
        return "Sorry, I couldn't generate a summary at this time."

async def get_error_message(error_context: str) -> str:
    """Generate an error message using the error model."""
    try:
        response = await client.chat.completions.create(
            model=ERROR_MODEL,
            messages=[
                {"role": "system", "content": 'На вход подается "context" - поле содержит стиль ответа на ошибку в поле "error", ответ должен быть структурированым json файлом. Пример запроса {"context":"ты добрый дедушка", "error":"Number must be positive"}, Ответ должен содержать только 1 поле с фразой пример {"response": "Ну как же так внучок, число должно быть положительным"}. Стиль ответа задан в поле context, ошибка на тексте которой создавать ответ в поле error. Если не знаешь что ответить, отвечай "Не знаю что ответить" и не используй другие фразы'},
                {"role": "user", "content": json.dumps({"context": ERROR_PROMPT, "error":error_context})}
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

def change_model(model_type: str, new_model: str) -> tuple[bool, str]:
    """Change the model being used by the bot."""
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