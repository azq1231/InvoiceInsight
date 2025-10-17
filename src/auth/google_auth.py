"""Google OAuth 2.0 authentication manager with keyring storage"""

import logging
import os
from pathlib import Path
from typing import Optional, Any, cast
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
    
    def __init__(self, redirect_uri: Optional[str] = None):
        self.config = get_config()
        self.scopes = self.config.get('oauth.scopes', [])
        self.creds: Optional[Credentials] = None
        self.redirect_uri = redirect_uri
        self.last_error: Optional[str] = None
        
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
        """Check if already authenticated with valid credentials"""
        # This method should only check for existing valid credentials or refresh them.
        # It should not trigger a new auth flow.
        # The is_authenticated() method already handles this logic correctly.
        return self.is_authenticated()
    
    def get_auth_url(self) -> Optional[tuple[str, Any, InstalledAppFlow]]:
        """Get authorization URL and flow for manual OAuth"""
        try:
            client_secrets_path = self.config.get('oauth.client_secrets_file')
            
            if not client_secrets_path or not Path(client_secrets_path).exists():
                logger.error("Client secrets file not found")
                return None

            # 提前检查 client_secrets.json 中是否包含当前使用的 redirect_uri，
            # 如果不包含则很可能在后续的 token 交换阶段出现 redirect_uri_mismatch 或 invalid_grant
            try:
                with open(client_secrets_path, 'r', encoding='utf-8') as csf:
                    cs = json.load(csf)
                # 支持 web 或 installed 两种 client 格式
                redirect_list = []
                if 'web' in cs and isinstance(cs['web'], dict):
                    redirect_list = cs['web'].get('redirect_uris', []) or []
                elif 'installed' in cs and isinstance(cs['installed'], dict):
                    redirect_list = cs['installed'].get('redirect_uris', []) or []
                # 如果开发者在构造 GoogleAuthManager 时指定了 redirect_uri，但 client_secrets 中没有列出，提示错误
                if self.redirect_uri and self.redirect_uri not in redirect_list:
                    logger.error(
                        "Configured redirect_uri '%s' not present in client_secrets.json redirect_uris: %s",
                        self.redirect_uri, redirect_list
                    )
                    return None
            except Exception as e:
                # 非致命：如果无法读取/解析 client_secrets.json，则继续让库处理，但记录警告
                logger.warning(f"Unable to pre-validate client_secrets.json: {e}")
            
            # 使用在初始化时传入的 redirect_uri，以确保与 Streamlit 应用的运行地址一致
            # 如果未提供，则退回到 None，让库自行决定（通常用于纯桌面应用）
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_path, 
                self.scopes,
                redirect_uri=self.redirect_uri
            )
            
            auth_url, state = flow.authorization_url(
                prompt='consent',
                access_type='offline',
                include_granted_scopes='true'
            )
            
            return auth_url, state, flow
            
        except Exception as e:
            logger.error(f"Failed to generate auth URL: {e}")
            self.last_error = str(e)
            return None
    
    def authenticate_with_code(self, auth_code: str, state: Optional[str] = None) -> bool:
        """Complete authentication using authorization code"""
        try:
            # Clean the auth code (remove whitespace, newlines)
            cleaned_code = auth_code.strip()
            
            if not cleaned_code:
                logger.error("Empty authorization code")
                return False
            
            # Exchange code for credentials
            # The flow object must be present on the instance
            # --- 关键修复：处理新会话中 flow 丢失的问题 ---
            if not hasattr(self, '_flow') or not self._flow:
                logger.warning("No pre-existing OAuth flow found. Recreating it for token exchange.")
                client_secrets_path = self.config.get('oauth.client_secrets_file')
                if not client_secrets_path or not Path(client_secrets_path).exists():
                    logger.error("Cannot recreate flow: Client secrets file not found.")
                    return False
                self._flow = InstalledAppFlow.from_client_secrets_file(
                    client_secrets_path,
                    self.scopes,
                    redirect_uri=self.redirect_uri
                )

            # 关键修复：手动将从 URL 获取的 state 设置回 flow 对象
            # 这可以防止因 session state 序列化问题导致的 state 不匹配
            if state:
                # 使用 setattr 避免静态类型检查器对 InstalledAppFlow 属性的报错
                setattr(self._flow, 'state', state)

            # 如果 flow 已经包含 redirect_uri，fetch_token 不需要再次传入，
            # 否则某些 oauthlib 版本会在内部造成重复传参错误（multiple values for keyword 'redirect_uri'）
            if getattr(self._flow, 'redirect_uri', None):
                self._flow.fetch_token(code=cleaned_code)
            else:
                # 仅在 flow 中没有 redirect_uri 时传入
                self._flow.fetch_token(code=cleaned_code, redirect_uri=self.redirect_uri)

            # flow.credentials 的具体类型可能与 google.oauth2.credentials.Credentials 的静态类型检查产生差异，
            # 使用 cast 明确告知类型检查器这是可接受的 Credentials 实例
            self.creds = cast(Credentials, self._flow.credentials)

            self._save_credentials()
            
            logger.info("Authentication successful with code")
            return True
            
        except Exception as e:
            logger.error(f"Failed to authenticate with code: {e}")
            # 保存最近一次认证错误，供 UI 展示以便排查
            try:
                self.last_error = str(e)
            except Exception:
                self.last_error = None
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
