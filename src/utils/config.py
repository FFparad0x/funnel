import os
import logging
import yaml
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENROUTER_API_KEY = os.getenv('OPENAI_API_KEY')
MODE = "debug"
CHANNELS_FILE = 'channels.yaml'

# Supported models
SUPPORTED_MODELS = [
    "qwen/qwen3-235b-a22b:free",
    "qwen/qwen3-14b:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct",
    "deepseek/deepseek-r1:free",
    "google/gemini-2.0-flash-001"
]

def load_user_mappings():
    """Load user mappings from JSON file."""
    try:
        with open('users.json', 'r', encoding='utf-8') as file:
            return json.load(file)['users']
    except Exception as e:
        logger.error(f"Error loading user mappings: {str(e)}")
        return {}

def load_channels():
    """Load channel IDs from YAML file."""
    active_channels = set()
    try:
        if os.path.exists(CHANNELS_FILE):
            with open(CHANNELS_FILE, 'r', encoding='utf-8') as file:
                channels = yaml.safe_load(file) or []
                for channel in channels:
                    channel_id = str(channel)
                    active_channels.add(channel_id)
                logger.info(f"Loaded {len(channels)} channels from {CHANNELS_FILE}")
        else:
            logger.info(f"No {CHANNELS_FILE} found. Will create when new channels are added.")
    except Exception as e:
        logger.error(f"Error loading channels from YAML: {str(e)}")
    return active_channels

def save_channels(active_channels):
    """Save channel IDs to YAML file."""
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(CHANNELS_FILE) if os.path.dirname(CHANNELS_FILE) else '.', exist_ok=True)
        
        # Save channels to file
        with open(CHANNELS_FILE, 'w', encoding='utf-8') as file:
            yaml.dump(list(active_channels), file, default_flow_style=False)
            
        logger.info(f"Saved {len(active_channels)} channels to {CHANNELS_FILE}")
    except Exception as e:
        logger.error(f"Error saving channels to YAML: {str(e)}") 