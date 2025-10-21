# src/auth/firebase_auth.py

import logging
import firebase_admin
from firebase_admin import credentials, auth
from src.utils.config import get_config

logger = logging.getLogger(__name__)

class FirebaseAuthManager:
    """Manages Firebase authentication."""

    _app_initialized = False

    def __init__(self):
        self.config = get_config()
        if not FirebaseAuthManager._app_initialized:
            self._initialize_firebase_app()

    def _initialize_firebase_app(self):
        """Initializes the Firebase app."""
        try:
            service_account_key_path = self.config.get('firebase.service_account_key_path')
            cred = credentials.Certificate(service_account_key_path)
            firebase_admin.initialize_app(cred)
            FirebaseAuthManager._app_initialized = True
            logger.info("Firebase app initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase app: {e}")
            raise

    def verify_id_token(self, id_token: str) -> dict | None:
        """
        Verifies the ID token and returns the decoded token.
        """
        if not id_token:
            return None
        try:
            # Add clock_skew_seconds to tolerate minor clock differences between client and server.
            # This is the robust, server-side solution for "Token used too early" errors.
            decoded_token = auth.verify_id_token(
                id_token, 
                clock_skew_seconds=10
            )
            return decoded_token
        except Exception as e:
            logger.error(f"Failed to verify ID token: {e}")
            return None
