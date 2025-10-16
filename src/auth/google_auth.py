"""Google OAuth 2.0 authentication manager with keyring storage"""

import logging
import os
from pathlib import Path
from typing import Optional
import keyring
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from src.utils.config import get_config

logger = logging.getLogger(__name__)


class GoogleAuthManager:
    """Manages Google OAuth 2.0 authentication with secure token storage"""
    
    SERVICE_NAME = "ocr_expense_tracker"
    USERNAME = "google_oauth_tokens"
    
    def __init__(self):
        self.config = get_config()
        self.scopes = self.config.get('oauth.scopes', [])
        self.creds: Optional[Credentials] = None
        
        self._load_credentials()
    
    def _load_credentials(self):
        """Load credentials from keyring with file fallback"""
        try:
            token_json = keyring.get_password(self.SERVICE_NAME, self.USERNAME)
            if token_json:
                token_dict = json.loads(token_json)
                self.creds = Credentials.from_authorized_user_info(token_dict, self.scopes)
                logger.info("Credentials loaded from keyring")
                return
        except Exception as e:
            logger.warning(f"Keyring unavailable, trying file fallback: {e}")
        
        token_file = Path("data/.token.json")
        if token_file.exists():
            try:
                with open(token_file, 'r') as f:
                    token_dict = json.load(f)
                self.creds = Credentials.from_authorized_user_info(token_dict, self.scopes)
                logger.info("Credentials loaded from file fallback")
            except Exception as e:
                logger.error(f"Failed to load credentials from file: {e}")
    
    def _save_credentials(self):
        """Save credentials to keyring with file fallback"""
        if not self.creds or not self.creds.valid:
            return
        
        token_dict = {
            'token': self.creds.token,
            'refresh_token': self.creds.refresh_token,
            'token_uri': self.creds.token_uri,
            'client_id': self.creds.client_id,
            'client_secret': self.creds.client_secret,
            'scopes': self.creds.scopes
        }
        
        try:
            keyring.set_password(
                self.SERVICE_NAME, 
                self.USERNAME, 
                json.dumps(token_dict)
            )
            logger.info("Credentials saved to keyring")
        except Exception as e:
            logger.warning(f"Keyring unavailable, using file fallback: {e}")
            token_file = Path("data/.token.json")
            token_file.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(token_file, 'w') as f:
                    json.dump(token_dict, f)
                logger.info("Credentials saved to file fallback")
            except Exception as file_error:
                logger.error(f"Failed to save credentials to file: {file_error}")
    
    def authenticate(self) -> bool:
        """Perform OAuth authentication flow"""
        try:
            if self.creds and self.creds.valid:
                return True
            
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logger.info("Refreshing expired token")
                self.creds.refresh(Request())
                self._save_credentials()
                return True
            
            client_secrets_path = self.config.get('oauth.client_secrets_file')
            
            if not client_secrets_path or not Path(client_secrets_path).exists():
                logger.error("Client secrets file not found. Please configure OAuth credentials.")
                return False
            
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_path,
                self.scopes
            )
            
            self.creds = flow.run_local_server(port=0)
            self._save_credentials()
            
            logger.info("Authentication successful")
            return True
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """Check if user is currently authenticated"""
        if not self.creds:
            return False
        
        if self.creds.expired and self.creds.refresh_token:
            try:
                self.creds.refresh(Request())
                self._save_credentials()
                return True
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                return False
        
        return self.creds.valid
    
    def logout(self):
        """Logout and clear stored credentials"""
        try:
            keyring.delete_password(self.SERVICE_NAME, self.USERNAME)
            logger.info("Keyring credentials cleared")
        except Exception as e:
            logger.warning(f"Keyring delete failed: {e}")
        
        token_file = Path("data/.token.json")
        if token_file.exists():
            try:
                token_file.unlink()
                logger.info("File fallback credentials cleared")
            except Exception as e:
                logger.error(f"Failed to delete token file: {e}")
        
        self.creds = None
        logger.info("Logout successful")
    
    def get_credentials(self) -> Optional[Credentials]:
        """Get current credentials"""
        if self.is_authenticated():
            return self.creds
        return None
    
    def build_service(self, service_name: str, version: str):
        """Build Google API service client"""
        if not self.is_authenticated():
            raise Exception("Not authenticated")
        
        return build(service_name, version, credentials=self.creds)
