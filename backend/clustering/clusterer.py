import numpy as np
from typing import List, Dict, Tuple
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from collections import Counter
import re
from config import Config

class EmailClusterer:
    """Cluster emails using K-means algorithm"""
    
    def __init__(self, n_clusters: int = None):
        self.n_clusters = n_clusters or Config.DEFAULT_CLUSTERS
        self.kmeans = None
        self.cluster_labels = None
        self.cluster_centers = None
        self.silhouette_score = None
        self.is_fitted = False
    
    def cluster_emails(self, feature_vectors: np.ndarray, email_ids: List[str], 
                      processed_emails: List[Dict], vectorizer) -> List[Dict]:
        """Perform K-means clustering on email feature vectors"""
        
        if feature_vectors.size == 0 or len(email_ids) == 0:
            return []
        
        # Determine optimal number of clusters if not specified
        if self.n_clusters is None:
            self.n_clusters = self._determine_optimal_clusters(feature_vectors)
        
        # Ensure we don't have more clusters than emails
        n_emails = feature_vectors.shape[0]
        self.n_clusters = min(self.n_clusters, n_emails)
        
        if self.n_clusters < 2:
            # If we have very few emails, create a single cluster
            return self._create_single_cluster(processed_emails, email_ids)
        
        try:
            # Perform K-means clustering
            self.kmeans = KMeans(
                n_clusters=self.n_clusters,
                random_state=42,
                n_init=10,
                max_iter=300
            )
            
            self.cluster_labels = self.kmeans.fit_predict(feature_vectors)
            self.cluster_centers = self.kmeans.cluster_centers_
            self.is_fitted = True
            
            # Calculate silhouette score for cluster quality
            if n_emails > 1:
                try:
                    self.silhouette_score = silhouette_score(feature_vectors, self.cluster_labels)
                except:
                    self.silhouette_score = 0.0
            else:
                self.silhouette_score = 0.0
            
            # Generate cluster information
            clusters = self._generate_cluster_info(
                processed_emails, email_ids, vectorizer, feature_vectors
            )
            
            return clusters
            
        except Exception as e:
            print(f"Error in clustering: {e}")
            return self._create_single_cluster(processed_emails, email_ids)
    
    def _determine_optimal_clusters(self, feature_vectors: np.ndarray) -> int:
        """Determine optimal number of clusters using elbow method"""
        n_emails = feature_vectors.shape[0]
        
        # For small datasets, use fewer clusters
        if n_emails < 10:
            return 2
        elif n_emails < 30:
            return 3
        elif n_emails < 100:
            return min(4, n_emails // 10)
        else:
            return min(5, n_emails // 20)
    
    def _create_single_cluster(self, processed_emails: List[Dict], email_ids: List[str]) -> List[Dict]:
        """Create a single cluster containing all emails"""
        cluster = {
            'id': 1,
            'label': 'All Emails',
            'description': 'All your recent emails',
            'email_count': len(processed_emails),
            'emails': processed_emails,
            'email_ids': email_ids
        }
        return [cluster]
    
    def _generate_cluster_info(self, processed_emails: List[Dict], email_ids: List[str], 
                              vectorizer, feature_vectors: np.ndarray) -> List[Dict]:
        """Generate descriptive information for each cluster"""
        clusters = []
        
        # Group emails by cluster
        for cluster_id in range(self.n_clusters):
            # Get emails in this cluster
            cluster_mask = self.cluster_labels == cluster_id
            cluster_emails = [processed_emails[i] for i in range(len(processed_emails)) if cluster_mask[i]]
            cluster_email_ids = [email_ids[i] for i in range(len(email_ids)) if cluster_mask[i]]
            cluster_vectors = feature_vectors[cluster_mask]
            
            if len(cluster_emails) == 0:
                continue
            
            # Generate cluster label and description
            label, description = self._generate_cluster_label_and_description(
                cluster_emails, vectorizer, cluster_vectors
            )
            
            cluster_info = {
                'id': cluster_id + 1,  # 1-based indexing for display
                'label': label,
                'description': description,
                'email_count': len(cluster_emails),
                'emails': cluster_emails,
                'email_ids': cluster_email_ids
            }
            
            clusters.append(cluster_info)
        
        # Sort clusters by size (largest first)
        clusters.sort(key=lambda x: x['email_count'], reverse=True)
        
        # Reassign IDs after sorting
        for i, cluster in enumerate(clusters):
            cluster['id'] = i + 1
        
        return clusters
    
    def _generate_cluster_label_and_description(self, cluster_emails: List[Dict], 
                                               vectorizer, cluster_vectors: np.ndarray) -> Tuple[str, str]:
        """Generate descriptive label and description for a cluster"""
        
        # Analyze email characteristics
        senders = [email.get('sender', '') for email in cluster_emails]
        subjects = [email.get('subject', '') for email in cluster_emails]
        sender_domains = [email.get('sender_domain', '') for email in cluster_emails]
        
        # Count characteristics
        newsletter_count = sum(1 for email in cluster_emails if email.get('is_newsletter', False))
        notification_count = sum(1 for email in cluster_emails if email.get('is_notification', False))
        promotional_count = sum(1 for email in cluster_emails if email.get('is_promotional', False))
        
        total_emails = len(cluster_emails)
        
        # Determine cluster type based on characteristics
        if newsletter_count / total_emails > 0.6:
            label = "Newsletters & Subscriptions"
            description = f"Newsletter and subscription emails ({total_emails} emails)"
        elif notification_count / total_emails > 0.6:
            label = "Notifications & Alerts"
            description = f"System notifications and alerts ({total_emails} emails)"
        elif promotional_count / total_emails > 0.6:
            label = "Promotions & Marketing"
            description = f"Promotional and marketing emails ({total_emails} emails)"
        else:
            # Use domain-based or content-based clustering
            label, description = self._generate_content_based_label(
                cluster_emails, sender_domains, subjects, vectorizer, cluster_vectors
            )
        
        return label, description
    
    def _generate_content_based_label(self, cluster_emails: List[Dict], sender_domains: List[str], 
                                     subjects: List[str], vectorizer, cluster_vectors: np.ndarray) -> Tuple[str, str]:
        """Generate label based on content analysis"""
        
        total_emails = len(cluster_emails)
        
        # Analyze sender domains
        domain_counts = Counter(sender_domains)
        most_common_domains = domain_counts.most_common(3)
        
        # Check if dominated by a single domain
        if most_common_domains and most_common_domains[0][1] / total_emails > 0.5:
            dominant_domain = most_common_domains[0][0]
            if dominant_domain != 'unknown':
                label = self._domain_to_label(dominant_domain)
                description = f"Emails from {dominant_domain} and related services ({total_emails} emails)"
                return label, description
        
        # Use TF-IDF features to determine content themes
        if hasattr(vectorizer, 'get_top_features_for_cluster'):
            top_features = vectorizer.get_top_features_for_cluster(cluster_vectors, top_n=5)
            if top_features:
                # Create label from top features
                label = self._features_to_label(top_features)
                description = f"Emails about {', '.join(top_features[:3])} ({total_emails} emails)"
                return label, description
        
        # Analyze subject patterns
        subject_words = []
        for subject in subjects:
            words = re.findall(r'\b[a-zA-Z]{3,}\b', subject.lower())
            subject_words.extend(words)
        
        if subject_words:
            word_counts = Counter(subject_words)
            common_words = [word for word, count in word_counts.most_common(3) 
                           if count > 1 and word not in ['the', 'and', 'for', 'you', 'your']]
            
            if common_words:
                label = self._words_to_label(common_words)
                description = f"Emails containing {', '.join(common_words[:2])} ({total_emails} emails)"
                return label, description
        
        # Fallback labels
        if total_emails > 20:
            return "Large Email Group", f"Large group of related emails ({total_emails} emails)"
        elif total_emails > 10:
            return "Medium Email Group", f"Medium group of related emails ({total_emails} emails)"
        else:
            return "Small Email Group", f"Small group of related emails ({total_emails} emails)"
    
    def _domain_to_label(self, domain: str) -> str:
        """Convert domain to readable label"""
        domain = domain.lower()
        
        # Social media
        if any(social in domain for social in ['facebook', 'twitter', 'linkedin', 'instagram']):
            return "Social Media"
        
        # Shopping
        if any(shop in domain for shop in ['amazon', 'ebay', 'shopify', 'etsy', 'shop']):
            return "Shopping & E-commerce"
        
        # Financial
        if any(fin in domain for fin in ['bank', 'paypal', 'stripe', 'finance', 'credit']):
            return "Financial Services"
        
        # News
        if any(news in domain for news in ['news', 'times', 'post', 'reuters', 'cnn', 'bbc']):
            return "News & Media"
        
        # Technology
        if any(tech in domain for tech in ['github', 'stackoverflow', 'google', 'microsoft']):
            return "Technology & Development"
        
        # Work/Business
        if any(work in domain for work in ['slack', 'teams', 'zoom', 'office', 'business']):
            return "Work & Business"
        
        # Clean up domain name for display
        clean_domain = domain.replace('.com', '').replace('.org', '').replace('.net', '')
        return f"{clean_domain.title()} Emails"
    
    def _features_to_label(self, features: List[str]) -> str:
        """Convert TF-IDF features to readable label"""
        # Map common features to categories
        feature_categories = {
            'work': 'Work & Business',
            'business': 'Work & Business',
            'meeting': 'Work & Business',
            'project': 'Work & Business',
            'team': 'Work & Business',
            'newsletter': 'Newsletters',
            'news': 'News & Updates',
            'update': 'News & Updates',
            'notification': 'Notifications',
            'alert': 'Notifications',
            'sale': 'Shopping & Deals',
            'deal': 'Shopping & Deals',
            'offer': 'Shopping & Deals',
            'discount': 'Shopping & Deals',
            'order': 'Shopping & Orders',
            'receipt': 'Receipts & Invoices',
            'invoice': 'Receipts & Invoices',
            'payment': 'Financial',
            'account': 'Account Management',
            'security': 'Security & Privacy',
            'social': 'Social Media',
            'event': 'Events & Calendar'
        }
        
        for feature in features:
            for keyword, category in feature_categories.items():
                if keyword in feature.lower():
                    return category
        
        # Fallback: use first feature as label
        if features:
            return f"{features[0].title()} Related"
        
        return "Mixed Content"
    
    def _words_to_label(self, words: List[str]) -> str:
        """Convert common words to readable label"""
        word_categories = {
            'order': 'Orders & Shopping',
            'receipt': 'Receipts',
            'invoice': 'Invoices',
            'payment': 'Payments',
            'account': 'Account Updates',
            'security': 'Security Alerts',
            'newsletter': 'Newsletters',
            'update': 'Updates',
            'notification': 'Notifications',
            'meeting': 'Meetings',
            'event': 'Events',
            'reminder': 'Reminders',
            'confirmation': 'Confirmations'
        }
        
        for word in words:
            if word.lower() in word_categories:
                return word_categories[word.lower()]
        
        # Create label from words
        return f"{' & '.join(word.title() for word in words[:2])}"
    
    def get_cluster_stats(self) -> Dict:
        """Get clustering statistics"""
        if not self.is_fitted:
            return {}
        
        return {
            'n_clusters': self.n_clusters,
            'silhouette_score': self.silhouette_score,
            'cluster_sizes': [np.sum(self.cluster_labels == i) for i in range(self.n_clusters)]
        }