#!/usr/bin/env python3
"""
Database initialization script for Gmail Email Clustering application.
This script creates the SQLite database and all required tables.
"""

import os
import sys

# Add the project root directory to the Python path
project_root = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, project_root)

from config import Config
from backend.database.models import DatabaseManager

def init_database():
    """Initialize the database with all required tables"""
    print("Initializing database...")
    
    # Create database manager
    db_manager = DatabaseManager(Config.DATABASE_PATH)
    
    print(f"Database initialized at: {Config.DATABASE_PATH}")
    print("Tables created:")
    print("  - emails")
    print("  - clusters") 
    print("  - email_clusters")
    print("  - user_sessions")
    print("Database initialization complete!")

if __name__ == "__main__":
    init_database()