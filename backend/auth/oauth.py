import os
import json
import warnings
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from config import Config

# Configure OAuth to be more lenient with scope validation
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# Suppress OAuth scope warnings - Google often adds extra scopes automatically
warnings.filterwarnings('ignore', message='Scope has changed')

class GmailOAuth:
    """Handle Gmail OAuth2 authentication flow"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.credentials = None
        self._load_credentials_from_db()
    
    def _load_credentials_from_db(self):
        """Load existing credentials from database"""
        session = self.db_manager.get_session()
        if session:
            self.credentials = Credentials(
                token=session['access_token'],
                refresh_token=session['refresh_token'],
                token_uri='https://oauth2.googleapis.com/token',
                client_id=self._get_client_id(),
                client_secret=self._get_client_secret(),
                scopes=Config.GOOGLE_SCOPES
            )
            
            # Check if token is expired
            if session['expires_at']:
                expires_at = datetime.fromisoformat(session['expires_at'])
                if datetime.now() < expires_at:
                    return
            
            # Try to refresh if expired
            self._refresh_credentials()
    
    def _get_client_id(self) -> str:
        """Get client ID from credentials file"""
        try:
            with open(Config.GOOGLE_CLIENT_SECRETS_FILE, 'r') as f:
                secrets = json.load(f)
                return secrets['installed']['client_id']
        except (FileNotFoundError, KeyError):
            raise Exception("credentials.json file not found or invalid")
    
    def _get_client_secret(self) -> str:
        """Get client secret from credentials file"""
        try:
            with open(Config.GOOGLE_CLIENT_SECRETS_FILE, 'r') as f:
                secrets = json.load(f)
                return secrets['installed']['client_secret']
        except (FileNotFoundError, KeyError):
            raise Exception("credentials.json file not found or invalid")
    
    def get_authorization_url(self) -> str:
        """Generate OAuth2 authorization URL"""
        if not os.path.exists(Config.GOOGLE_CLIENT_SECRETS_FILE):
            raise Exception(
                "credentials.json file not found. Please download it from Google Cloud Console."
            )
        
        flow = Flow.from_client_secrets_file(
            Config.GOOGLE_CLIENT_SECRETS_FILE,
            scopes=Config.GOOGLE_SCOPES
        )
        flow.redirect_uri = Config.REDIRECT_URI
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        return authorization_url, state
    
    def exchange_code_for_tokens(self, authorization_code: str, state: str) -> bool:
        """Exchange authorization code for access tokens"""
        try:
            # Create a fresh flow for token exchange
            flow = Flow.from_client_secrets_file(
                Config.GOOGLE_CLIENT_SECRETS_FILE,
                scopes=Config.GOOGLE_SCOPES
            )
            flow.redirect_uri = Config.REDIRECT_URI
            
            print(f"Attempting to exchange code: {authorization_code[:10]}...")
            print(f"Using redirect URI: {Config.REDIRECT_URI}")
            print(f"Using scopes: {Config.GOOGLE_SCOPES}")
            
            # Fetch tokens - use a custom approach to handle scope changes
            import os
            os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
            flow.fetch_token(code=authorization_code)
            
            self.credentials = flow.credentials
            print("Successfully obtained credentials")
            
            # Save to database
            expires_at = None
            if self.credentials.expiry:
                expires_at = self.credentials.expiry.isoformat()
            
            self.db_manager.save_session(
                access_token=self.credentials.token,
                refresh_token=self.credentials.refresh_token,
                expires_at=expires_at
            )
            
            print("Successfully saved session to database")
            return True
            
        except Exception as e:
            print(f"Detailed error exchanging code for tokens: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _refresh_credentials(self) -> bool:
        """Refresh expired credentials"""
        if not self.credentials or not self.credentials.refresh_token:
            return False
        
        try:
            self.credentials.refresh(Request())
            
            # Save refreshed tokens to database
            expires_at = None
            if self.credentials.expiry:
                expires_at = self.credentials.expiry
            
            self.db_manager.save_session(
                access_token=self.credentials.token,
                refresh_token=self.credentials.refresh_token,
                expires_at=expires_at
            )
            
            return True
            
        except Exception as e:
            print(f"Error refreshing credentials: {e}")
            self.credentials = None
            return False
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated with valid credentials"""
        if not self.credentials:
            return False
        
        # Check if credentials are valid
        if not self.credentials.valid:
            # Try to refresh
            if self.credentials.expired and self.credentials.refresh_token:
                return self._refresh_credentials()
            return False
        
        return True
    
    def get_credentials(self) -> Optional[Credentials]:
        """Get valid credentials for API calls"""
        if self.is_authenticated():
            return self.credentials
        return None
    
    def logout(self):
        """Clear stored credentials"""
        self.credentials = None
        # Clear from database
        self.db_manager.get_connection().execute('DELETE FROM user_sessions')
        self.db_manager.get_connection().commit()
    
    def get_oauth2_string(self, email: str) -> str:
        """Generate OAuth2 string for IMAP authentication"""
        if not self.credentials or not self.credentials.token:
            raise Exception("No valid credentials available")
        
        # Refresh token if needed
        if self.credentials.expired and self.credentials.refresh_token:
            print("Access token expired, refreshing...")
            self._refresh_credentials()
        
        # Format for Gmail IMAP OAuth2: user=email\x01auth=Bearer token\x01\x01
        auth_string = f"user={email}\x01auth=Bearer {self.credentials.token}\x01\x01"
        print(f"OAuth2 string created for user: {email}")
        print(f"Token starts with: {self.credentials.token[:20]}...")
        return auth_string