import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.ensure_database_directory()
        self.init_database()
    
    def ensure_database_directory(self):
        """Ensure the database directory exists"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
    
    def get_connection(self):
        """Get a database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
        return conn
    
    def init_database(self):
        """Initialize the database with required tables"""
        conn = self.get_connection()
        try:
            # Create emails table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS emails (
                    id INTEGER PRIMARY KEY,
                    gmail_id TEXT UNIQUE,
                    subject TEXT,
                    sender TEXT,
                    body TEXT,
                    date_received DATETIME,
                    is_archived BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create clusters table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS clusters (
                    id INTEGER PRIMARY KEY,
                    label TEXT,
                    description TEXT,
                    email_count INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create email_clusters junction table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS email_clusters (
                    email_id INTEGER,
                    cluster_id INTEGER,
                    FOREIGN KEY (email_id) REFERENCES emails(id),
                    FOREIGN KEY (cluster_id) REFERENCES clusters(id),
                    PRIMARY KEY (email_id, cluster_id)
                )
            ''')
            
            # Create user_sessions table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY,
                    access_token TEXT,
                    refresh_token TEXT,
                    expires_at DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_emails_gmail_id ON emails(gmail_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_emails_archived ON emails(is_archived)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_email_clusters_email ON email_clusters(email_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_email_clusters_cluster ON email_clusters(cluster_id)')
            
            conn.commit()
        finally:
            conn.close()
    
    def save_emails(self, emails: List[Dict]) -> List[int]:
        """Save emails to database and return their IDs"""
        conn = self.get_connection()
        email_ids = []
        
        try:
            for email in emails:
                cursor = conn.execute('''
                    INSERT OR REPLACE INTO emails 
                    (gmail_id, subject, sender, body, date_received)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    email['gmail_id'],
                    email['subject'],
                    email['sender'],
                    email['body'],
                    email['date_received']
                ))
                email_ids.append(cursor.lastrowid)
            
            conn.commit()
        finally:
            conn.close()
        
        return email_ids
    
    def get_emails(self, include_archived: bool = False) -> List[Dict]:
        """Get emails from database"""
        conn = self.get_connection()
        
        try:
            if include_archived:
                cursor = conn.execute('''
                    SELECT * FROM emails 
                    ORDER BY date_received DESC
                ''')
            else:
                cursor = conn.execute('''
                    SELECT * FROM emails 
                    WHERE is_archived = FALSE
                    ORDER BY date_received DESC
                ''')
            
            emails = [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
        
        return emails
    
    def save_clusters(self, clusters: List[Dict]) -> List[int]:
        """Save clusters to database and return their IDs"""
        conn = self.get_connection()
        cluster_ids = []
        
        try:
            # Clear existing clusters
            conn.execute('DELETE FROM email_clusters')
            conn.execute('DELETE FROM clusters')
            
            for cluster in clusters:
                cursor = conn.execute('''
                    INSERT INTO clusters (label, description, email_count)
                    VALUES (?, ?, ?)
                ''', (
                    cluster['label'],
                    cluster['description'],
                    cluster['email_count']
                ))
                cluster_ids.append(cursor.lastrowid)
            
            conn.commit()
        finally:
            conn.close()
        
        return cluster_ids
    
    def save_email_cluster_assignments(self, assignments: List[Tuple[int, int]]):
        """Save email-cluster assignments"""
        conn = self.get_connection()
        
        try:
            conn.executemany('''
                INSERT INTO email_clusters (email_id, cluster_id)
                VALUES (?, ?)
            ''', assignments)
            conn.commit()
        finally:
            conn.close()
    
    def get_clusters_with_emails(self) -> List[Dict]:
        """Get clusters with their associated emails"""
        conn = self.get_connection()
        
        try:
            # Get clusters
            cursor = conn.execute('''
                SELECT * FROM clusters 
                ORDER BY email_count DESC
            ''')
            clusters = [dict(row) for row in cursor.fetchall()]
            
            # Get emails for each cluster
            for cluster in clusters:
                cursor = conn.execute('''
                    SELECT e.* FROM emails e
                    JOIN email_clusters ec ON e.id = ec.email_id
                    WHERE ec.cluster_id = ? AND e.is_archived = FALSE
                    ORDER BY e.date_received DESC
                ''', (cluster['id'],))
                cluster['emails'] = [dict(row) for row in cursor.fetchall()]
        
        finally:
            conn.close()
        
        return clusters
    
    def archive_cluster_emails(self, cluster_id: int) -> List[str]:
        """Mark all emails in a cluster as archived and return Gmail IDs"""
        conn = self.get_connection()
        
        try:
            # Get Gmail IDs of emails in the cluster
            cursor = conn.execute('''
                SELECT e.gmail_id FROM emails e
                JOIN email_clusters ec ON e.id = ec.email_id
                WHERE ec.cluster_id = ?
            ''', (cluster_id,))
            gmail_ids = [row[0] for row in cursor.fetchall()]
            
            # Mark emails as archived
            conn.execute('''
                UPDATE emails 
                SET is_archived = TRUE 
                WHERE id IN (
                    SELECT e.id FROM emails e
                    JOIN email_clusters ec ON e.id = ec.email_id
                    WHERE ec.cluster_id = ?
                )
            ''', (cluster_id,))
            
            conn.commit()
        finally:
            conn.close()
        
        return gmail_ids
    
    def save_session(self, access_token: str, refresh_token: str, expires_at: datetime):
        """Save OAuth2 session tokens"""
        conn = self.get_connection()
        
        try:
            # Clear existing sessions (simple single-user app)
            conn.execute('DELETE FROM user_sessions')
            
            # Save new session
            conn.execute('''
                INSERT INTO user_sessions (access_token, refresh_token, expires_at)
                VALUES (?, ?, ?)
            ''', (access_token, refresh_token, expires_at))
            
            conn.commit()
        finally:
            conn.close()
    
    def get_session(self) -> Optional[Dict]:
        """Get the current OAuth2 session"""
        conn = self.get_connection()
        
        try:
            cursor = conn.execute('''
                SELECT * FROM user_sessions 
                ORDER BY created_at DESC 
                LIMIT 1
            ''')
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    
    def clear_all_data(self):
        """Clear all data (useful for testing)"""
        conn = self.get_connection()
        
        try:
            conn.execute('DELETE FROM email_clusters')
            conn.execute('DELETE FROM clusters')
            conn.execute('DELETE FROM emails')
            conn.execute('DELETE FROM user_sessions')
            conn.commit()
        finally:
            conn.close()