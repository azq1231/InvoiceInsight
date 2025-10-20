import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from src.utils.config import get_config

class GoogleAuthManager:
    def __init__(self, redirect_uri=None):
        self.config = get_config()
        self.client_secrets_path = self.config.get('oauth.client_secrets_file')
        self.scopes = self.config.get('oauth.scopes', [])
        self.redirect_uri = redirect_uri

    def get_authorization_url(self):
        """Generates a URL for user authorization."""
        flow = Flow.from_client_secrets_file(
            self.client_secrets_path,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        # In a real app, you'd store the state in the session
        return authorization_url, state

    def fetch_token(self, authorization_response, state):
        """Fetches the token and the raw id_token from the authorization response."""
        flow = Flow.from_client_secrets_file(
            self.client_secrets_path,
            scopes=self.scopes,
            state=state,
            redirect_uri=self.redirect_uri
        )
        flow.fetch_token(authorization_response=authorization_response)
        
        credentials = flow.credentials
        credentials_dict = self.credentials_to_dict(credentials)
        
        # The id_token is part of the token response from Google
        id_token = flow.oauth2session.token['id_token']
        
        return credentials_dict, id_token

    def credentials_to_dict(self, credentials):
        """Converts credentials object to a dictionary."""
        return {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }
