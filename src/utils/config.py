"""Configuration management"""

import yaml
from pathlib import Path
from typing import Any, Dict
import os
from dotenv import load_dotenv


class Config:
    """Application configuration singleton"""
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            load_dotenv()  # Load .env file
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self):
        """Load configuration from YAML file"""
        config_path = Path('config/settings.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)

    def reload(self):
        """Force reload of the configuration from YAML file"""
        self._load_config()
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value by dot-separated path.
        It first checks for an environment variable, then falls back to the YAML file.
        """
        # Check environment variable first (e.g., 'firebase.web_app_config.apiKey' -> 'FIREBASE_WEB_APP_CONFIG_APIKEY')
        env_key = key_path.upper().replace('.', '_')
        env_value = os.getenv(env_key)
        if env_value is not None:
            return env_value

        # Fallback to YAML file
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_all(self) -> Dict:
        """Get entire configuration dictionary"""
        return self._config.copy()


def get_config() -> Config:
    """Get configuration singleton instance"""
    return Config()
