import re
import string
from typing import List, Dict
from bs4 import BeautifulSoup
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer

class EmailPreprocessor:
    """Preprocess emails for clustering analysis"""
    
    def __init__(self):
        self.stemmer = PorterStemmer()
        self.stop_words = set()
        self._download_nltk_data()
        self._load_stop_words()
    
    def _download_nltk_data(self):
        """Download required NLTK data"""
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)
        
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords', quiet=True)
    
    def _load_stop_words(self):
        """Load stop words for text filtering"""
        try:
            self.stop_words = set(stopwords.words('english'))
            
            # Add common email-specific stop words
            email_stop_words = {
                'email', 'mail', 'message', 'sent', 'received', 'reply', 'forward',
                'subject', 'from', 'to', 'cc', 'bcc', 'date', 'time',
                'gmail', 'outlook', 'yahoo', 'hotmail',
                'http', 'https', 'www', 'com', 'org', 'net',
                'unsubscribe', 'click', 'here', 'link',
                'best', 'regards', 'sincerely', 'thanks', 'thank', 'you',
                'please', 'let', 'know', 'get', 'back', 'contact',
                'would', 'could', 'should', 'will', 'can', 'may',
                'one', 'two', 'three', 'first', 'second', 'last',
                'also', 'just', 'now', 'then', 'well', 'good', 'great'
            }
            
            self.stop_words.update(email_stop_words)
            
        except Exception as e:
            print(f"Error loading stop words: {e}")
            # Fallback to basic stop words
            self.stop_words = {
                'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
                'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
                'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these',
                'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him',
                'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their'
            }
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ''
        
        # Remove HTML tags
        text = self._remove_html(text)
        
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
        # Remove email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', text)
        
        # Remove phone numbers
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '', text)
        
        # Remove excessive whitespace and newlines
        text = re.sub(r'\s+', ' ', text)
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation except for important ones
        text = re.sub(r'[^\w\s\-\.]', ' ', text)
        
        # Remove numbers (usually not meaningful for clustering)
        text = re.sub(r'\b\d+\b', '', text)
        
        # Remove extra spaces
        text = ' '.join(text.split())
        
        return text.strip()
    
    def _remove_html(self, text: str) -> str:
        """Remove HTML tags from text"""
        try:
            soup = BeautifulSoup(text, 'html.parser')
            return soup.get_text()
        except Exception:
            # Fallback: simple regex removal
            return re.sub(r'<[^>]+>', '', text)
    
    def extract_features(self, email: Dict) -> Dict:
        """Extract features from email for clustering"""
        features = {}
        
        # Clean subject and body
        subject = self.clean_text(email.get('subject', ''))
        body = self.clean_text(email.get('body', ''))
        sender = email.get('sender', '')
        
        # Extract sender domain
        sender_domain = self._extract_domain(sender)
        
        # Combine text for analysis
        combined_text = f"{subject} {body}"
        
        # Tokenize and filter
        tokens = self._tokenize_and_filter(combined_text)
        
        # Create features
        features = {
            'id': email.get('id'),
            'gmail_id': email.get('gmail_id'),
            'subject': subject,
            'body': body,
            'sender': sender,
            'sender_domain': sender_domain,
            'combined_text': ' '.join(tokens),
            'tokens': tokens,
            'token_count': len(tokens),
            'subject_length': len(subject.split()),
            'body_length': len(body.split()),
            'has_attachments': 'attachment' in body.lower(),
            'is_newsletter': self._is_newsletter(sender, subject, body),
            'is_notification': self._is_notification(subject, body),
            'is_promotional': self._is_promotional(subject, body)
        }
        
        return features
    
    def _extract_domain(self, sender: str) -> str:
        """Extract domain from sender email"""
        try:
            # Extract email from sender string (e.g., "Name <email@domain.com>")
            email_match = re.search(r'<([^>]+)>', sender)
            if email_match:
                email_addr = email_match.group(1)
            else:
                email_addr = sender
            
            # Extract domain
            domain_match = re.search(r'@([^@]+)', email_addr)
            if domain_match:
                domain = domain_match.group(1).lower()
                # Remove common subdomains
                domain = re.sub(r'^(mail|smtp|pop|imap)\.', '', domain)
                return domain
            
        except Exception:
            pass
        
        return 'unknown'
    
    def _tokenize_and_filter(self, text: str) -> List[str]:
        """Tokenize text and filter out stop words and short words"""
        if not text:
            return []
        
        try:
            # Tokenize
            tokens = word_tokenize(text)
            
            # Filter tokens
            filtered_tokens = []
            for token in tokens:
                # Skip if too short, is stop word, or is all punctuation
                if (len(token) < 3 or 
                    token.lower() in self.stop_words or 
                    all(c in string.punctuation for c in token)):
                    continue
                
                # Stem the token
                stemmed = self.stemmer.stem(token.lower())
                filtered_tokens.append(stemmed)
            
            return filtered_tokens
            
        except Exception as e:
            print(f"Error tokenizing text: {e}")
            # Fallback: simple split and filter
            words = text.split()
            return [word for word in words 
                   if len(word) >= 3 and word.lower() not in self.stop_words]
    
    def _is_newsletter(self, sender: str, subject: str, body: str) -> bool:
        """Detect if email is likely a newsletter"""
        newsletter_indicators = [
            'newsletter', 'digest', 'weekly', 'monthly', 'daily',
            'unsubscribe', 'subscription', 'mailing list',
            'noreply', 'no-reply', 'donotreply'
        ]
        
        text = f"{sender} {subject} {body}".lower()
        return any(indicator in text for indicator in newsletter_indicators)
    
    def _is_notification(self, subject: str, body: str) -> bool:
        """Detect if email is likely a notification"""
        notification_indicators = [
            'notification', 'alert', 'reminder', 'confirmation',
            'receipt', 'invoice', 'statement', 'report',
            'update', 'status', 'activity', 'security'
        ]
        
        text = f"{subject} {body}".lower()
        return any(indicator in text for indicator in notification_indicators)
    
    def _is_promotional(self, subject: str, body: str) -> bool:
        """Detect if email is likely promotional"""
        promo_indicators = [
            'sale', 'discount', 'offer', 'deal', 'promotion',
            'coupon', 'save', 'free', 'limited time',
            'special', 'exclusive', 'buy now', 'shop'
        ]
        
        text = f"{subject} {body}".lower()
        return any(indicator in text for indicator in promo_indicators)
    
    def preprocess_emails(self, emails: List[Dict]) -> List[Dict]:
        """Preprocess a list of emails"""
        processed_emails = []
        
        for email in emails:
            try:
                features = self.extract_features(email)
                processed_emails.append(features)
            except Exception as e:
                print(f"Error preprocessing email {email.get('gmail_id', 'unknown')}: {e}")
                continue
        
        return processed_emails