from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import base64
import email
from datetime import datetime
from typing import List, Dict, Optional
from email.header import decode_header
from bs4 import BeautifulSoup
import re

class GmailAPIClient:
    """Gmail API client for fetching and managing emails"""
    
    def __init__(self, oauth_handler):
        self.oauth_handler = oauth_handler
        self.service = None
        self.user_email = None
    
    def connect(self, user_email: str) -> bool:
        """Establish Gmail API connection using OAuth2"""
        try:
            self.user_email = user_email
            
            # Get valid credentials
            credentials = self.oauth_handler.get_credentials()
            if not credentials:
                print("No valid credentials available for Gmail API")
                return False
            
            # Build Gmail API service
            self.service = build('gmail', 'v1', credentials=credentials)
            print(f"Successfully connected to Gmail API for user: {user_email}")
            
            return True
            
        except Exception as e:
            print(f"Error connecting to Gmail API: {e}")
            return False
    
    def fetch_recent_emails(self, count: int = 200) -> List[Dict]:
        """Fetch recent emails using Gmail API"""
        if not self.service:
            raise Exception("Not connected to Gmail API")
        
        try:
            print(f"Fetching {count} recent emails from Gmail...")
            
            # List messages from inbox
            results = self.service.users().messages().list(
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
                    email_data = self._fetch_email_by_id(message['id'])
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
    
    def _fetch_email_by_id(self, message_id: str) -> Optional[Dict]:
        """Fetch a single email by ID using Gmail API"""
        try:
            # Get message details
            message = self.service.users().messages().get(
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
            date_received = self._parse_date(date_str)
            
            # Get email body
            body = self._extract_body(message['payload'])
            
            # Clean and process body text
            clean_body = self._clean_text(body)
            
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
        """Extract header value by name"""
        for header in headers:
            if header['name'] == name:
                return header['value']
        return None
    
    def _extract_body(self, payload: Dict) -> str:
        """Extract body text from email payload"""
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
    
    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML to plain text"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            return soup.get_text()
        except:
            return html_content
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize email text"""
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
    
    def _parse_date(self, date_str: str) -> datetime:
        """Parse email date string"""
        try:
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except:
            return datetime.now()
    
    def archive_emails(self, email_ids: List[str]) -> bool:
        """Archive emails by removing from inbox"""
        if not self.service:
            return False
        
        try:
            for email_id in email_ids:
                # Remove INBOX label (archives the email)
                self.service.users().messages().modify(
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
