"""
Unified Gmail Authentication Module

This module consolidates all authentication-related functionality including:
- OAuth2 flow management
- Gmail IMAP client
- Gmail API client  
- Credential management
"""

import os
import json
import warnings
import imaplib
import email
import base64
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

# Google API imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Email processing imports
from email.header import decode_header
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup

# Local imports
from config import Config

# Configure OAuth to be more lenient with scope validation
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

# Suppress OAuth scope warnings - Google often adds extra scopes automatically
warnings.filterwarnings('ignore', message='Scope has changed')


class GmailAuthenticator:
    """
    Unified Gmail authentication and client management.
    
    This class handles:
    - OAuth2 authentication flow
    - Credential storage and refresh
    - Gmail IMAP and API connections
    - Email fetching and management
    """
    
    def __init__(self, db_manager):
        """Initialize the authenticator with database manager."""
        self.db_manager = db_manager
        self.credentials = None
        self.imap_client = None
        self.api_service = None
        self.user_email = None
        
        # Load existing credentials if available
        self._load_credentials_from_db()
    
    # =============================================================================
    # OAuth2 Credential Management
    # =============================================================================
    
    def _load_credentials_from_db(self):
        """Load existing credentials from database."""
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
        """Get client ID from credentials file."""
        try:
            with open(Config.GOOGLE_CLIENT_SECRETS_FILE, 'r') as f:
                secrets = json.load(f)
                return secrets['installed']['client_id']
        except (FileNotFoundError, KeyError):
            raise Exception("credentials.json file not found or invalid")
    
    def _get_client_secret(self) -> str:
        """Get client secret from credentials file."""
        try:
            with open(Config.GOOGLE_CLIENT_SECRETS_FILE, 'r') as f:
                secrets = json.load(f)
                return secrets['installed']['client_secret']
        except (FileNotFoundError, KeyError):
            raise Exception("credentials.json file not found or invalid")
    
    def get_authorization_url(self) -> tuple[str, str]:
        """Generate OAuth2 authorization URL."""
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
        """Exchange authorization code for access tokens."""
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
        """Refresh expired credentials."""
        if not self.credentials or not self.credentials.refresh_token:
            return False
        
        try:
            self.credentials.refresh(Request())
            
            # Save refreshed tokens to database
            expires_at = None
            if self.credentials.expiry:
                expires_at = self.credentials.expiry.isoformat()
            
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
        """Check if user is authenticated with valid credentials."""
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
        """Get valid credentials for API calls."""
        if self.is_authenticated():
            return self.credentials
        return None
    
    def logout(self):
        """Clear stored credentials."""
        self.credentials = None
        self.user_email = None
        
        # Disconnect clients
        self._disconnect_imap()
        self.api_service = None
        
        # Clear from database
        self.db_manager.get_connection().execute('DELETE FROM user_sessions')
        self.db_manager.get_connection().commit()
    
    def get_oauth2_string(self, email: str) -> str:
        """Generate OAuth2 string for IMAP authentication."""
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
    
    # =============================================================================
    # IMAP Client Methods
    # =============================================================================
    
    def connect_imap(self, user_email: str) -> bool:
        """Establish IMAP connection using OAuth2."""
        try:
            self.user_email = user_email
            
            # Create IMAP connection
            self.imap_client = imaplib.IMAP4_SSL(Config.GMAIL_IMAP_HOST, Config.GMAIL_IMAP_PORT)
            
            # Get OAuth2 authentication string
            oauth2_string = self.get_oauth2_string(user_email)
            print(f"Authenticating with Gmail IMAP for user: {user_email}")
            print(f"OAuth2 string length: {len(oauth2_string)}")
            
            # Authenticate using OAuth2
            self.imap_client.authenticate('XOAUTH2', lambda x: oauth2_string.encode('ascii'))
            
            return True
            
        except Exception as e:
            print(f"Error connecting to Gmail IMAP: {e}")
            self._disconnect_imap()
            return False
    
    def _disconnect_imap(self):
        """Close IMAP connection."""
        if self.imap_client:
            try:
                self.imap_client.close()
                self.imap_client.logout()
            except:
                pass
            self.imap_client = None
    
    def fetch_emails_via_imap(self, count: int = 200) -> List[Dict]:
        """Fetch recent emails from inbox using IMAP."""
        if not self.imap_client:
            raise Exception("Not connected to Gmail IMAP")
        
        try:
            # Select inbox
            self.imap_client.select('INBOX')
            
            # Search for all emails in inbox
            status, messages = self.imap_client.search(None, 'ALL')
            if status != 'OK':
                raise Exception("Failed to search emails")
            
            # Get message IDs
            message_ids = messages[0].split()
            
            # Get the most recent emails (last N messages)
            recent_ids = message_ids[-count:] if len(message_ids) > count else message_ids
            recent_ids.reverse()  # Most recent first
            
            emails = []
            for msg_id in recent_ids:
                try:
                    email_data = self._fetch_email_by_id_imap(msg_id)
                    if email_data:
                        emails.append(email_data)
                except Exception as e:
                    print(f"Error fetching email {msg_id}: {e}")
                    continue
            
            return emails
            
        except Exception as e:
            print(f"Error fetching emails via IMAP: {e}")
            return []
    
    def _fetch_email_by_id_imap(self, msg_id: bytes) -> Optional[Dict]:
        """Fetch a single email by ID using IMAP."""
        try:
            # Fetch email data
            status, msg_data = self.imap_client.fetch(msg_id, '(RFC822)')
            if status != 'OK':
                return None
            
            # Parse email
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            # Extract email data
            subject = self._decode_header(email_message.get('Subject', ''))
            sender = self._decode_header(email_message.get('From', ''))
            date_str = email_message.get('Date', '')
            
            # Parse date
            date_received = self._parse_date(date_str)
            
            # Extract body
            body = self._extract_body_imap(email_message)
            
            # Get Gmail message ID
            gmail_id = email_message.get('Message-ID', str(msg_id.decode()))
            
            return {
                'gmail_id': gmail_id,
                'subject': subject,
                'sender': sender,
                'body': body,
                'date_received': date_received
            }
            
        except Exception as e:
            print(f"Error parsing email: {e}")
            return None
    
    def _extract_body_imap(self, email_message) -> str:
        """Extract email body text from IMAP message."""
        body = ''
        
        try:
            if email_message.is_multipart():
                # Handle multipart messages
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get('Content-Disposition', ''))
                    
                    # Skip attachments
                    if 'attachment' in content_disposition:
                        continue
                    
                    if content_type == 'text/plain':
                        charset = part.get_content_charset() or 'utf-8'
                        part_body = part.get_payload(decode=True)
                        if part_body:
                            body += part_body.decode(charset, errors='ignore')
                    elif content_type == 'text/html':
                        charset = part.get_content_charset() or 'utf-8'
                        part_body = part.get_payload(decode=True)
                        if part_body:
                            html_body = part_body.decode(charset, errors='ignore')
                            # Convert HTML to text
                            body += self._html_to_text(html_body)
            else:
                # Handle single part messages
                content_type = email_message.get_content_type()
                charset = email_message.get_content_charset() or 'utf-8'
                
                payload = email_message.get_payload(decode=True)
                if payload:
                    if content_type == 'text/html':
                        body = self._html_to_text(payload.decode(charset, errors='ignore'))
                    else:
                        body = payload.decode(charset, errors='ignore')
            
            # Clean up body text
            body = self._clean_body_text(body)
            
        except Exception as e:
            print(f"Error extracting body: {e}")
            body = ''
        
        return body
    
    def archive_emails_via_imap(self, gmail_ids: List[str]) -> bool:
        """Archive emails by moving them from inbox to all mail using IMAP."""
        if not self.imap_client:
            raise Exception("Not connected to Gmail IMAP")
        
        try:
            # Select inbox
            self.imap_client.select('INBOX')
            
            success_count = 0
            for gmail_id in gmail_ids:
                try:
                    # Search for email by Message-ID
                    status, messages = self.imap_client.search(None, f'HEADER Message-ID "{gmail_id}"')
                    if status != 'OK' or not messages[0]:
                        continue
                    
                    msg_ids = messages[0].split()
                    for msg_id in msg_ids:
                        # Add to All Mail and remove from Inbox
                        self.imap_client.store(msg_id, '+X-GM-LABELS', '\\All')
                        self.imap_client.store(msg_id, '-X-GM-LABELS', '\\Inbox')
                        success_count += 1
                        
                except Exception as e:
                    print(f"Error archiving email {gmail_id}: {e}")
                    continue
            
            # Expunge to apply changes
            self.imap_client.expunge()
            
            print(f"Successfully archived {success_count} out of {len(gmail_ids)} emails")
            return success_count > 0
            
        except Exception as e:
            print(f"Error archiving emails: {e}")
            return False
    
    # =============================================================================
    # Gmail API Client Methods
    # =============================================================================
    
    def connect_api(self, user_email: str) -> bool:
        """Establish Gmail API connection using OAuth2."""
        try:
            self.user_email = user_email
            
            # Get valid credentials
            credentials = self.get_credentials()
            if not credentials:
                print("No valid credentials available for Gmail API")
                return False
            
            # Build Gmail API service
            self.api_service = build('gmail', 'v1', credentials=credentials)
            print(f"Successfully connected to Gmail API for user: {user_email}")
            
            return True
            
        except Exception as e:
            print(f"Error connecting to Gmail API: {e}")
            return False
    
    def fetch_emails_via_api(self, count: int = 200) -> List[Dict]:
        """Fetch recent emails using Gmail API."""
        if not self.api_service:
            raise Exception("Not connected to Gmail API")
        
        try:
            print(f"Fetching {count} recent emails from Gmail...")
            
            # List messages from inbox
            results = self.api_service.users().messages().list(
                userId='me',
                labelIds=['INBOX'],
                maxResults=count
            ).execute()
            
            messages = results.get('messages', [])
            print(f"Found {len(messages)} messages in inbox")
            
            emails = []
            for i, message in enumerate(messages):
                try:
                    print(f"Fetching email {i+1}/{len(messages)}")
                    email_data = self._fetch_email_by_id_api(message['id'])
                    if email_data:
                        emails.append(email_data)
                except Exception as e:
                    print(f"Error fetching email {message['id']}: {e}")
                    continue
            
            print(f"Successfully fetched {len(emails)} emails")
            return emails
            
        except HttpError as e:
            print(f"Gmail API error: {e}")
            return []
        except Exception as e:
            print(f"Error fetching emails: {e}")
            return []
    
    def _fetch_email_by_id_api(self, message_id: str) -> Optional[Dict]:
        """Fetch a single email by ID using Gmail API."""
        try:
            # Get message details
            message = self.api_service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Extract email data
            headers = message['payload'].get('headers', [])
            
            # Get basic email info
            subject = self._get_header(headers, 'Subject') or 'No Subject'
            sender = self._get_header(headers, 'From') or 'Unknown Sender'
            date_str = self._get_header(headers, 'Date') or ''
            
            # Parse date
            date_received = self._parse_date_api(date_str)
            
            # Get email body
            body = self._extract_body_api(message['payload'])
            
            # Clean and process body text
            clean_body = self._clean_text_api(body)
            
            return {
                'gmail_id': message_id,
                'subject': subject,
                'sender': sender,
                'body': clean_body,
                'date_received': date_received,
                'is_archived': False
            }
            
        except Exception as e:
            print(f"Error processing email {message_id}: {e}")
            return None
    
    def _get_header(self, headers: List[Dict], name: str) -> Optional[str]:
        """Extract header value by name."""
        for header in headers:
            if header['name'] == name:
                return header['value']
        return None
    
    def _extract_body_api(self, payload: Dict) -> str:
        """Extract body text from email payload (API version)."""
        body = ""
        
        if 'parts' in payload:
            # Multi-part message
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data', '')
                    if data:
                        body += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                elif part['mimeType'] == 'text/html' and not body:
                    # Use HTML if no plain text found
                    data = part['body'].get('data', '')
                    if data:
                        html_content = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        body = self._html_to_text(html_content)
        else:
            # Single part message
            if payload['mimeType'] == 'text/plain':
                data = payload['body'].get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
            elif payload['mimeType'] == 'text/html':
                data = payload['body'].get('data', '')
                if data:
                    html_content = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    body = self._html_to_text(html_content)
        
        return body
    
    def _clean_text_api(self, text: str) -> str:
        """Clean and normalize email text (API version)."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        
        # Remove extra punctuation
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remove extra whitespace again
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Limit length
        return text[:2000] if len(text) > 2000 else text
    
    def _parse_date_api(self, date_str: str) -> datetime:
        """Parse email date string (API version)."""
        try:
            return parsedate_to_datetime(date_str)
        except:
            return datetime.now()
    
    def archive_emails_via_api(self, email_ids: List[str]) -> bool:
        """Archive emails by removing from inbox using API."""
        if not self.api_service:
            return False
        
        try:
            for email_id in email_ids:
                # Remove INBOX label (archives the email)
                self.api_service.users().messages().modify(
                    userId='me',
                    id=email_id,
                    body={'removeLabelIds': ['INBOX']}
                ).execute()
            
            print(f"Successfully archived {len(email_ids)} emails")
            return True
            
        except HttpError as e:
            print(f"Error archiving emails: {e}")
            return False
        except Exception as e:
            print(f"Error archiving emails: {e}")
            return False
    
    # =============================================================================
    # Shared Utility Methods
    # =============================================================================
    
    def _decode_header(self, header: str) -> str:
        """Decode email header."""
        if not header:
            return ''
        
        try:
            decoded_parts = decode_header(header)
            decoded_header = ''
            
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_header += part.decode(encoding)
                    else:
                        decoded_header += part.decode('utf-8', errors='ignore')
                else:
                    decoded_header += part
            
            return decoded_header.strip()
            
        except Exception as e:
            print(f"Error decoding header: {e}")
            return header
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse email date string."""
        try:
            # Remove timezone info for simplicity
            date_str = re.sub(r'\s*\([^)]+\)$', '', date_str)
            date_str = re.sub(r'\s*[+-]\d{4}$', '', date_str)
            
            # Try different date formats
            formats = [
                '%a, %d %b %Y %H:%M:%S',
                '%d %b %Y %H:%M:%S',
                '%a, %d %b %Y %H:%M',
                '%d %b %Y %H:%M'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt)
                except ValueError:
                    continue
            
            # If all formats fail, return current time
            return datetime.now()
            
        except Exception as e:
            print(f"Error parsing date: {e}")
            return datetime.now()
    
    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove script and style elements
            for script in soup(['script', 'style']):
                script.decompose()
            
            # Get text
            text = soup.get_text()
            
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception as e:
            print(f"Error converting HTML to text: {e}")
            return html
    
    def _clean_body_text(self, text: str) -> str:
        """Clean up body text."""
        if not text:
            return ''
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove common email artifacts
        text = re.sub(r'On .* wrote:', '', text)
        text = re.sub(r'From:.*?Subject:', '', text, flags=re.DOTALL)
        
        # Limit length for processing efficiency
        if len(text) > 5000:
            text = text[:5000] + '...'
        
        return text.strip()
    
    def get_user_email(self) -> Optional[str]:
        """Get the authenticated user's email address."""
        return self.user_email
    
    # =============================================================================
    # High-level Methods
    # =============================================================================
    
    def fetch_emails(self, count: int = 200, use_api: bool = True) -> List[Dict]:
        """
        Fetch emails using either API or IMAP.
        
        Args:
            count: Number of emails to fetch
            use_api: If True, use Gmail API; if False, use IMAP
            
        Returns:
            List of email dictionaries
        """
        if use_api:
            if not self.api_service and self.user_email:
                self.connect_api(self.user_email)
            return self.fetch_emails_via_api(count)
        else:
            if not self.imap_client and self.user_email:
                self.connect_imap(self.user_email)
            return self.fetch_emails_via_imap(count)
    
    def archive_emails(self, email_ids: List[str], use_api: bool = True) -> bool:
        """
        Archive emails using either API or IMAP.
        
        Args:
            email_ids: List of email IDs to archive
            use_api: If True, use Gmail API; if False, use IMAP
            
        Returns:
            True if successful, False otherwise
        """
        if use_api:
            return self.archive_emails_via_api(email_ids)
        else:
            return self.archive_emails_via_imap(email_ids)


# For backward compatibility, create aliases to the old class names
GmailOAuth = GmailAuthenticator
GmailIMAPClient = GmailAuthenticator  
GmailAPIClient = GmailAuthenticator
