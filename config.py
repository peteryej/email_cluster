import os
from datetime import timedelta

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Database configuration
    DATABASE_PATH = os.path.join(os.getcwd(), 'data', 'cache', 'emails.db')
    
    # Google OAuth2 configuration
    GOOGLE_CLIENT_SECRETS_FILE = "credentials.json"
    GOOGLE_SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/gmail.modify'
    ]
    
    # OAuth2 redirect URI for desktop app (must match credentials.json)
    REDIRECT_URI = 'http://localhost'  # Match the credentials file
    
    # Email processing configuration
    MAX_EMAILS = 200
    DEFAULT_CLUSTERS = 3
    
    # TF-IDF configuration
    TFIDF_MAX_FEATURES = 1000
    TFIDF_MIN_DF = 2
    TFIDF_MAX_DF = 0.8
    TFIDF_NGRAM_RANGE = (1, 2)
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    
    # Gmail IMAP configuration
    GMAIL_IMAP_HOST = 'imap.gmail.com'
    GMAIL_IMAP_PORT = 993