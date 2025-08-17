import imaplib
import email
import base64
from datetime import datetime
from typing import List, Dict, Optional
from email.header import decode_header
from bs4 import BeautifulSoup
import re
from config import Config

class GmailIMAPClient:
    """Gmail IMAP client for fetching and managing emails"""
    
    def __init__(self, oauth_handler):
        self.oauth_handler = oauth_handler
        self.imap = None
        self.user_email = None
    
    def connect(self, user_email: str) -> bool:
        """Establish IMAP connection using OAuth2"""
        try:
            self.user_email = user_email
            
            # Create IMAP connection
            self.imap = imaplib.IMAP4_SSL(Config.GMAIL_IMAP_HOST, Config.GMAIL_IMAP_PORT)
            
            # Get OAuth2 authentication string
            oauth2_string = self.oauth_handler.get_oauth2_string(user_email)
            print(f"Authenticating with Gmail IMAP for user: {user_email}")
            print(f"OAuth2 string length: {len(oauth2_string)}")
            
            # Authenticate using OAuth2 - use direct method
            # The IMAP authenticate method expects raw bytes response
            self.imap.authenticate('XOAUTH2', lambda x: oauth2_string.encode('ascii'))
            
            return True
            
        except Exception as e:
            print(f"Error connecting to Gmail IMAP: {e}")
            if self.imap:
                try:
                    self.imap.close()
                except:
                    pass
                self.imap = None
            return False
    
    def disconnect(self):
        """Close IMAP connection"""
        if self.imap:
            try:
                self.imap.close()
                self.imap.logout()
            except:
                pass
            self.imap = None
    
    def fetch_recent_emails(self, count: int = 200) -> List[Dict]:
        """Fetch recent emails from inbox"""
        if not self.imap:
            raise Exception("Not connected to Gmail IMAP")
        
        try:
            # Select inbox
            self.imap.select('INBOX')
            
            # Search for all emails in inbox
            status, messages = self.imap.search(None, 'ALL')
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
                    email_data = self._fetch_email_by_id(msg_id)
                    if email_data:
                        emails.append(email_data)
                except Exception as e:
                    print(f"Error fetching email {msg_id}: {e}")
                    continue
            
            return emails
            
        except Exception as e:
            print(f"Error fetching emails: {e}")
            return []
    
    def _fetch_email_by_id(self, msg_id: bytes) -> Optional[Dict]:
        """Fetch a single email by ID"""
        try:
            # Fetch email data
            status, msg_data = self.imap.fetch(msg_id, '(RFC822)')
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
            body = self._extract_body(email_message)
            
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
    
    def _decode_header(self, header: str) -> str:
        """Decode email header"""
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
        """Parse email date string"""
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
    
    def _extract_body(self, email_message) -> str:
        """Extract email body text"""
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
    
    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text"""
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
        """Clean up body text"""
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
    
    def archive_emails(self, gmail_ids: List[str]) -> bool:
        """Archive emails by moving them from inbox to all mail"""
        if not self.imap:
            raise Exception("Not connected to Gmail IMAP")
        
        try:
            # Select inbox
            self.imap.select('INBOX')
            
            success_count = 0
            for gmail_id in gmail_ids:
                try:
                    # Search for email by Message-ID
                    status, messages = self.imap.search(None, f'HEADER Message-ID "{gmail_id}"')
                    if status != 'OK' or not messages[0]:
                        continue
                    
                    msg_ids = messages[0].split()
                    for msg_id in msg_ids:
                        # Add to All Mail and remove from Inbox
                        self.imap.store(msg_id, '+X-GM-LABELS', '\\All')
                        self.imap.store(msg_id, '-X-GM-LABELS', '\\Inbox')
                        success_count += 1
                        
                except Exception as e:
                    print(f"Error archiving email {gmail_id}: {e}")
                    continue
            
            # Expunge to apply changes
            self.imap.expunge()
            
            print(f"Successfully archived {success_count} out of {len(gmail_ids)} emails")
            return success_count > 0
            
        except Exception as e:
            print(f"Error archiving emails: {e}")
            return False
    
    def get_user_email(self) -> Optional[str]:
        """Get the authenticated user's email address"""
        return self.user_email