import json
import os
from typing import Dict, Optional
from utils.default_config import CURRENT_MODEL, ERROR_MODEL, MAIN_PROMPT, ERROR_PROMPT

class ChannelConfig:
    def __init__(self):
        self.config_file = "channel_config.json"
        self.default_config = {
            "main_model": CURRENT_MODEL,
            "error_model": ERROR_MODEL,
            "main_prompt": MAIN_PROMPT,
            "error_prompt": ERROR_PROMPT
        }
        self.channel_configs: Dict[str, dict] = {}
        self.load_configs()

    def load_configs(self):
        """Load channel configurations from file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.channel_configs = json.load(f)
            except Exception as e:
                print(f"Error loading channel configs: {str(e)}")
                self.channel_configs = {}

    def save_configs(self):
        """Save channel configurations to file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.channel_configs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving channel configs: {str(e)}")

    def get_channel_config(self, channel_id: str) -> dict:
        """Get configuration for a specific channel."""
        return self.channel_configs.get(str(channel_id), self.default_config)

    def update_channel_config(self, channel_id: str, config_type: str, value: str) -> bool:
        """Update a specific configuration for a channel."""
        channel_id = str(channel_id)
        if channel_id not in self.channel_configs:
            self.channel_configs[channel_id] = self.default_config.copy()

        if config_type in ["main_model", "error_model", "main_prompt", "error_prompt"]:
            self.channel_configs[channel_id][config_type] = value
            self.save_configs()
            return True
        return False

    def reset_channel_config(self, channel_id: str, config_type: Optional[str] = None) -> bool:
        """Reset configuration for a channel to default values."""
        channel_id = str(channel_id)
        if config_type:
            if channel_id in self.channel_configs:
                if config_type in self.channel_configs[channel_id]:
                    self.channel_configs[channel_id][config_type] = self.default_config[config_type]
                    self.save_configs()
                    return True
        else:
            if channel_id in self.channel_configs:
                del self.channel_configs[channel_id]
                self.save_configs()
                return True
        return False

# Create a global instance
channel_config = ChannelConfig() 