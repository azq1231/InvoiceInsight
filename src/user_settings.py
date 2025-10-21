import json
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SETTINGS_FILE_PATH = os.path.join('data', 'user_settings.json')

class UserSettingsManager:
    """Manages user-specific settings, like expense keywords, stored in a JSON file."""

    def __init__(self, file_path: str = SETTINGS_FILE_PATH):
        self.file_path = file_path

    def _load_settings(self) -> Dict:
        """Loads settings from the JSON file."""
        try:
            if os.path.exists(self.file_path):
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading user settings from {self.file_path}: {e}")
            # If the file is corrupted, start with empty settings
            return {}

    def _save_settings(self, settings_data: Dict):
        """Saves the current settings to the JSON file."""
        try:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(settings_data, f, ensure_ascii=False, indent=4)
        except IOError as e:
            logger.error(f"Error saving user settings to {self.file_path}: {e}")

    def get_expense_keywords(self, user_id: str) -> Optional[List[str]]:
        """Gets the expense keywords for a specific user, reading fresh from the file."""
        current_settings = self._load_settings()
        return current_settings.get(user_id, {}).get('expense_keywords')

    def save_expense_keywords(self, user_id: str, keywords: List[str]):
        """Saves the expense keywords for a specific user by reading, modifying, and writing the file."""
        if not user_id:
            logger.warning("Attempted to save settings for an invalid user_id.")
            return
        
        # Read-modify-write to ensure atomicity at the operation level
        current_settings = self._load_settings()
        if user_id not in current_settings:
            current_settings[user_id] = {}
        current_settings[user_id]['expense_keywords'] = keywords
        self._save_settings(current_settings)
        logger.info(f"Saved expense keywords for user_id: {user_id[:8]}...")