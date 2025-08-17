from flask import Blueprint, request, jsonify, session, redirect, url_for
import traceback
from datetime import datetime
from typing import Dict, List

# Import our modules
from database.models import DatabaseManager
from auth.oauth import GmailOAuth
from auth.gmail_api_client import GmailAPIClient
from clustering.preprocessor import EmailPreprocessor
from clustering.vectorizer import EmailVectorizer
from clustering.clusterer import EmailClusterer
from config import Config

# Create blueprint
api = Blueprint('api', __name__, url_prefix='/api')

# Global instances (will be initialized in app.py)
db_manager = None
oauth_handler = None

def init_api(database_manager, oauth_handler_instance):
    """Initialize API with database manager and OAuth handler"""
    global db_manager, oauth_handler
    db_manager = database_manager
    oauth_handler = oauth_handler_instance

@api.route('/auth/login', methods=['GET'])
def login():
    """Initiate OAuth2 login flow"""
    try:
        authorization_url, state = oauth_handler.get_authorization_url()
        session['oauth_state'] = state
        return jsonify({
            'success': True,
            'authorization_url': authorization_url
        })
    except Exception as e:
        print(f"Error in login: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api.route('/auth/callback', methods=['GET', 'POST'])
def oauth_callback():
    """Handle OAuth2 callback"""
    try:
        if request.method == 'GET':
            # Traditional OAuth callback (for web flow)
            code = request.args.get('code')
            state = request.args.get('state')
            error = request.args.get('error')
        else:
            # Manual code submission (for desktop flow)
            data = request.get_json()
            code = data.get('code') if data else None
            state = session.get('oauth_state')  # Use stored state
            error = None
        
        if error:
            return jsonify({
                'success': False,
                'error': f'OAuth error: {error}'
            }), 400
        
        if not code:
            return jsonify({
                'success': False,
                'error': 'No authorization code received'
            }), 400
        
        # For desktop apps, we don't need strict state verification
        # since the user manually enters the code
        stored_state = session.get('oauth_state')
        if not stored_state:
            return jsonify({
                'success': False,
                'error': 'No OAuth session found'
            }), 400
        
        # Exchange code for tokens
        print(f"Attempting to exchange authorization code with state: {stored_state}")
        success = oauth_handler.exchange_code_for_tokens(code, stored_state)
        
        if success:
            session['authenticated'] = True
            print("OAuth exchange successful, setting session")
            if request.method == 'GET':
                # Redirect to main page
                return redirect('/')
            else:
                # Return JSON response for AJAX
                return jsonify({
                    'success': True,
                    'message': 'Authentication successful'
                })
        else:
            print("OAuth exchange failed")
            return jsonify({
                'success': False,
                'error': 'Failed to exchange authorization code. Check server logs for details.'
            }), 500
            
    except Exception as e:
        print(f"Error in OAuth callback: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status"""
    try:
        is_authenticated = oauth_handler.is_authenticated()
        return jsonify({
            'authenticated': is_authenticated
        })
    except Exception as e:
        print(f"Error checking auth status: {e}")
        return jsonify({
            'authenticated': False,
            'error': str(e)
        }), 500

@api.route('/auth/logout', methods=['POST'])
def logout():
    """Logout user"""
    try:
        oauth_handler.logout()
        session.clear()
        return jsonify({
            'success': True,
            'message': 'Logged out successfully'
        })
    except Exception as e:
        print(f"Error in logout: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api.route('/emails/fetch', methods=['POST'])
def fetch_emails():
    """Fetch and cluster emails"""
    try:
        # Check authentication
        if not oauth_handler.is_authenticated():
            return jsonify({
                'success': False,
                'error': 'Not authenticated'
            }), 401
        
        # Get user email from request
        data = request.get_json() or {}
        user_email = data.get('email')
        
        if not user_email:
            return jsonify({
                'success': False,
                'error': 'Email address required'
            }), 400
        
        # Create Gmail API client
        gmail_client = GmailAPIClient(oauth_handler)
        
        # Connect to Gmail API
        if not gmail_client.connect(user_email):
            return jsonify({
                'success': False,
                'error': 'Failed to connect to Gmail API'
            }), 500
        
        # Fetch emails using Gmail API
        print("Fetching emails from Gmail API...")
        emails = gmail_client.fetch_recent_emails(Config.MAX_EMAILS)
        
        if not emails:
            return jsonify({
                'success': False,
                'error': 'No emails found'
            }), 404
        
        print(f"Fetched {len(emails)} emails")
        
        # Save emails to database
        db_manager.save_emails(emails)
        
        # Process and cluster emails
        clusters = process_and_cluster_emails(emails)
        
        return jsonify({
            'success': True,
            'email_count': len(emails),
            'cluster_count': len(clusters),
            'clusters': clusters
        })
            
    except Exception as e:
        print(f"Error fetching emails: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def process_and_cluster_emails(emails: List[Dict]) -> List[Dict]:
    """Process and cluster emails"""
    try:
        # Initialize processors
        preprocessor = EmailPreprocessor()
        vectorizer = EmailVectorizer()
        clusterer = EmailClusterer()
        
        print("Preprocessing emails...")
        # Preprocess emails
        processed_emails = preprocessor.preprocess_emails(emails)
        
        if not processed_emails:
            return []
        
        print("Vectorizing emails...")
        # Vectorize emails
        feature_vectors, email_ids = vectorizer.fit_transform(processed_emails)
        
        if feature_vectors.size == 0:
            return []
        
        print("Clustering emails...")
        # Cluster emails
        clusters = clusterer.cluster_emails(
            feature_vectors, email_ids, processed_emails, vectorizer
        )
        
        # Save clusters to database
        if clusters:
            cluster_data = []
            assignments = []
            
            for cluster in clusters:
                cluster_data.append({
                    'label': cluster['label'],
                    'description': cluster['description'],
                    'email_count': cluster['email_count']
                })
            
            # Save clusters
            cluster_ids = db_manager.save_clusters(cluster_data)
            
            # Create email-cluster assignments
            for i, cluster in enumerate(clusters):
                cluster_id = cluster_ids[i]
                for email in cluster['emails']:
                    # Find email ID in database
                    db_emails = db_manager.get_emails()
                    for db_email in db_emails:
                        if db_email['gmail_id'] == email['gmail_id']:
                            assignments.append((db_email['id'], cluster_id))
                            break
            
            # Save assignments
            if assignments:
                db_manager.save_email_cluster_assignments(assignments)
        
        print(f"Created {len(clusters)} clusters")
        return clusters
        
    except Exception as e:
        print(f"Error processing and clustering emails: {e}")
        traceback.print_exc()
        return []

@api.route('/clusters', methods=['GET'])
def get_clusters():
    """Get clustered emails"""
    try:
        # Check authentication
        if not oauth_handler.is_authenticated():
            return jsonify({
                'success': False,
                'error': 'Not authenticated'
            }), 401
        
        # Get clusters from database
        clusters = db_manager.get_clusters_with_emails()
        
        # Filter out archived emails from clusters
        active_clusters = []
        for cluster in clusters:
            active_emails = [email for email in cluster['emails'] if not email['is_archived']]
            if active_emails:  # Only include clusters with active emails
                cluster['emails'] = active_emails
                cluster['email_count'] = len(active_emails)
                active_clusters.append(cluster)
        
        return jsonify({
            'success': True,
            'clusters': active_clusters
        })
        
    except Exception as e:
        print(f"Error getting clusters: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api.route('/clusters/<int:cluster_id>/archive', methods=['POST'])
def archive_cluster(cluster_id):
    """Archive all emails in a cluster"""
    try:
        # Check authentication
        if not oauth_handler.is_authenticated():
            return jsonify({
                'success': False,
                'error': 'Not authenticated'
            }), 401
        
        # Get Gmail IDs of emails to archive
        gmail_ids = db_manager.archive_cluster_emails(cluster_id)
        
        if not gmail_ids:
            return jsonify({
                'success': False,
                'error': 'No emails found in cluster'
            }), 404
        
        # Get user email from session or request
        data = request.get_json() or {}
        user_email = data.get('email')
        
        if not user_email:
            return jsonify({
                'success': False,
                'error': 'Email address required'
            }), 400
        
        # Archive emails in Gmail
        gmail_client = GmailIMAPClient(oauth_handler)
        
        if not gmail_client.connect(user_email):
            return jsonify({
                'success': False,
                'error': 'Failed to connect to Gmail'
            }), 500
        
        try:
            success = gmail_client.archive_emails(gmail_ids)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Archived {len(gmail_ids)} emails',
                    'archived_count': len(gmail_ids)
                })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Failed to archive emails in Gmail'
                }), 500
                
        finally:
            gmail_client.disconnect()
            
    except Exception as e:
        print(f"Error archiving cluster: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api.route('/stats', methods=['GET'])
def get_stats():
    """Get application statistics"""
    try:
        # Check authentication
        if not oauth_handler.is_authenticated():
            return jsonify({
                'success': False,
                'error': 'Not authenticated'
            }), 401
        
        # Get email counts
        all_emails = db_manager.get_emails(include_archived=True)
        active_emails = db_manager.get_emails(include_archived=False)
        
        # Get cluster information
        clusters = db_manager.get_clusters_with_emails()
        
        stats = {
            'total_emails': len(all_emails),
            'active_emails': len(active_emails),
            'archived_emails': len(all_emails) - len(active_emails),
            'total_clusters': len(clusters),
            'active_clusters': len([c for c in clusters if any(not e['is_archived'] for e in c['emails'])])
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        print(f"Error getting stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@api.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0.0'
    })

# Error handlers
@api.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@api.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500