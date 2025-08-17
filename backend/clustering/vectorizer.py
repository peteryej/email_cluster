import numpy as np
from typing import List, Dict, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from config import Config

class EmailVectorizer:
    """Convert emails to TF-IDF vectors for clustering"""
    
    def __init__(self):
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=Config.TFIDF_MAX_FEATURES,
            stop_words='english',
            ngram_range=Config.TFIDF_NGRAM_RANGE,
            min_df=Config.TFIDF_MIN_DF,
            max_df=Config.TFIDF_MAX_DF,
            lowercase=True,
            strip_accents='unicode',
            token_pattern=r'\b[a-zA-Z][a-zA-Z0-9]{2,}\b'  # Words with at least 3 chars, starting with letter
        )
        
        self.scaler = StandardScaler()
        self.feature_names = []
        self.is_fitted = False
    
    def fit_transform(self, processed_emails: List[Dict]) -> Tuple[np.ndarray, List[str]]:
        """Fit vectorizer and transform emails to feature vectors"""
        if not processed_emails:
            return np.array([]), []
        
        # Extract text data
        texts = []
        email_ids = []
        
        for email in processed_emails:
            # Combine different text features
            combined_text = self._combine_text_features(email)
            texts.append(combined_text)
            email_ids.append(email.get('gmail_id', ''))
        
        # Fit and transform with TF-IDF
        try:
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(texts)
            self.feature_names = self.tfidf_vectorizer.get_feature_names_out()
            
            # Convert to dense array for additional features
            tfidf_dense = tfidf_matrix.toarray()
            
            # Add additional numerical features
            additional_features = self._extract_additional_features(processed_emails)
            
            # Combine TF-IDF with additional features
            if additional_features.size > 0:
                # Scale additional features
                additional_features_scaled = self.scaler.fit_transform(additional_features)
                
                # Combine features
                combined_features = np.hstack([tfidf_dense, additional_features_scaled])
            else:
                combined_features = tfidf_dense
            
            self.is_fitted = True
            return combined_features, email_ids
            
        except Exception as e:
            print(f"Error in vectorization: {e}")
            return np.array([]), email_ids
    
    def transform(self, processed_emails: List[Dict]) -> Tuple[np.ndarray, List[str]]:
        """Transform new emails using fitted vectorizer"""
        if not self.is_fitted:
            raise ValueError("Vectorizer must be fitted before transform")
        
        if not processed_emails:
            return np.array([]), []
        
        # Extract text data
        texts = []
        email_ids = []
        
        for email in processed_emails:
            combined_text = self._combine_text_features(email)
            texts.append(combined_text)
            email_ids.append(email.get('gmail_id', ''))
        
        try:
            # Transform with TF-IDF
            tfidf_matrix = self.tfidf_vectorizer.transform(texts)
            tfidf_dense = tfidf_matrix.toarray()
            
            # Add additional numerical features
            additional_features = self._extract_additional_features(processed_emails)
            
            # Combine features
            if additional_features.size > 0:
                additional_features_scaled = self.scaler.transform(additional_features)
                combined_features = np.hstack([tfidf_dense, additional_features_scaled])
            else:
                combined_features = tfidf_dense
            
            return combined_features, email_ids
            
        except Exception as e:
            print(f"Error in transformation: {e}")
            return np.array([]), email_ids
    
    def _combine_text_features(self, email: Dict) -> str:
        """Combine different text features from email"""
        # Get text components
        subject = email.get('subject', '')
        body = email.get('combined_text', '') or email.get('body', '')
        sender_domain = email.get('sender_domain', '')
        
        # Weight subject more heavily (appears 3 times)
        # Weight sender domain moderately (appears 2 times)
        combined_text = f"{subject} {subject} {subject} {sender_domain} {sender_domain} {body}"
        
        # Add categorical indicators as text
        if email.get('is_newsletter', False):
            combined_text += " newsletter_type"
        if email.get('is_notification', False):
            combined_text += " notification_type"
        if email.get('is_promotional', False):
            combined_text += " promotional_type"
        
        return combined_text.strip()
    
    def _extract_additional_features(self, processed_emails: List[Dict]) -> np.ndarray:
        """Extract additional numerical features"""
        features = []
        
        for email in processed_emails:
            email_features = [
                # Text length features
                email.get('subject_length', 0),
                email.get('body_length', 0),
                email.get('token_count', 0),
                
                # Boolean features (converted to 0/1)
                int(email.get('has_attachments', False)),
                int(email.get('is_newsletter', False)),
                int(email.get('is_notification', False)),
                int(email.get('is_promotional', False)),
                
                # Sender domain features
                self._encode_sender_domain(email.get('sender_domain', '')),
            ]
            
            features.append(email_features)
        
        return np.array(features) if features else np.array([])
    
    def _encode_sender_domain(self, domain: str) -> float:
        """Encode sender domain as numerical feature"""
        # Common domain categories
        if not domain or domain == 'unknown':
            return 0.0
        
        # Social media and communication
        social_domains = ['facebook', 'twitter', 'linkedin', 'instagram', 'whatsapp', 'telegram']
        if any(social in domain for social in social_domains):
            return 1.0
        
        # E-commerce and shopping
        shopping_domains = ['amazon', 'ebay', 'shopify', 'etsy', 'alibaba', 'walmart']
        if any(shop in domain for shop in shopping_domains):
            return 2.0
        
        # Financial services
        finance_domains = ['bank', 'paypal', 'stripe', 'visa', 'mastercard', 'finance']
        if any(fin in domain for fin in finance_domains):
            return 3.0
        
        # News and media
        news_domains = ['news', 'media', 'times', 'post', 'reuters', 'cnn', 'bbc']
        if any(news in domain for news in news_domains):
            return 4.0
        
        # Technology companies
        tech_domains = ['google', 'microsoft', 'apple', 'github', 'stackoverflow', 'tech']
        if any(tech in domain for tech in tech_domains):
            return 5.0
        
        # Government and organizations
        if domain.endswith('.gov') or domain.endswith('.org'):
            return 6.0
        
        # Educational institutions
        if domain.endswith('.edu'):
            return 7.0
        
        # Generic/other
        return 8.0
    
    def get_feature_names(self) -> List[str]:
        """Get names of all features"""
        feature_names = list(self.feature_names) if len(self.feature_names) > 0 else []
        
        # Add additional feature names
        additional_names = [
            'subject_length',
            'body_length', 
            'token_count',
            'has_attachments',
            'is_newsletter',
            'is_notification',
            'is_promotional',
            'sender_domain_category'
        ]
        
        return feature_names + additional_names
    
    def get_top_features_for_cluster(self, cluster_vectors: np.ndarray, top_n: int = 10) -> List[str]:
        """Get top features that characterize a cluster"""
        if not self.is_fitted or cluster_vectors.size == 0:
            return []
        
        try:
            # Calculate mean feature values for the cluster
            mean_features = np.mean(cluster_vectors, axis=0)
            
            # Get indices of top features
            top_indices = np.argsort(mean_features)[-top_n:][::-1]
            
            # Get feature names
            all_feature_names = self.get_feature_names()
            
            # Return top feature names
            top_features = []
            for idx in top_indices:
                if idx < len(all_feature_names):
                    feature_name = all_feature_names[idx]
                    feature_value = mean_features[idx]
                    if feature_value > 0.01:  # Only include meaningful features
                        top_features.append(feature_name)
            
            return top_features
            
        except Exception as e:
            print(f"Error getting top features: {e}")
            return []
    
    def get_vectorizer_info(self) -> Dict:
        """Get information about the fitted vectorizer"""
        if not self.is_fitted:
            return {}
        
        return {
            'vocabulary_size': len(self.tfidf_vectorizer.vocabulary_),
            'feature_count': len(self.get_feature_names()),
            'max_features': Config.TFIDF_MAX_FEATURES,
            'ngram_range': Config.TFIDF_NGRAM_RANGE,
            'min_df': Config.TFIDF_MIN_DF,
            'max_df': Config.TFIDF_MAX_DF
        }