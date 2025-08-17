#!/usr/bin/env python3
"""
Gmail Email Clustering Application
Main Flask application entry point
"""

import os
import sys
from flask import Flask, render_template, send_from_directory
from flask_cors import CORS

# Add the parent directory to Python path for config.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import our modules
from config import Config
from database.models import DatabaseManager
from auth.authentication import GmailAuthenticator
from api.routes import api, init_api

def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__, 
                template_folder='../frontend',
                static_folder='../frontend/static')
    
    # Configure app
    app.config.from_object(Config)
    
    # Enable CORS for development
    CORS(app)
    
    # Initialize database
    db_manager = DatabaseManager(Config.DATABASE_PATH)
    
    # Initialize authentication handler
    oauth_handler = GmailAuthenticator(db_manager)
    
    # Initialize API routes
    init_api(db_manager, oauth_handler)
    
    # Register blueprints
    app.register_blueprint(api)
    
    # Main route - serve the frontend
    @app.route('/')
    def index():
        """Serve the main application page"""
        return render_template('index.html')
    
    # Static file routes
    @app.route('/static/<path:filename>')
    def static_files(filename):
        """Serve static files"""
        return send_from_directory(app.static_folder, filename)
    
    # Health check
    @app.route('/health')
    def health():
        """Health check endpoint"""
        return {
            'status': 'healthy',
            'app': 'Gmail Email Clustering',
            'version': '1.0.0'
        }
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        """Handle 404 errors"""
        return render_template('index.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        """Handle 500 errors"""
        return {
            'error': 'Internal server error',
            'message': 'Something went wrong. Please try again.'
        }, 500
    
    return app

# Create the Flask app
app = create_app()

if __name__ == '__main__':
    # Development server
    print("Starting Gmail Email Clustering Application...")
    print("Make sure you have placed your credentials.json file in the project root.")
    print("Visit http://localhost:5000 to access the application.")
    
    # Check if credentials file exists
    if not os.path.exists('credentials.json'):
        print("\nWARNING: credentials.json not found!")
        print("Please download your OAuth2 credentials from Google Cloud Console")
        print("and save them as 'credentials.json' in the project root directory.")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )