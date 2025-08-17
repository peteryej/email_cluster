# Claude Agent Implementation Guide - Gmail Email Clustering Application

## Project Summary

This is a web application that clusters a user's last 200 emails into actionable groups using TF-IDF and K-means clustering, with OAuth2 Gmail authentication and one-click archive functionality.

## Key Implementation Requirements

### Authentication & Email Access
- **OAuth2 Flow**: Use Google OAuth2 with `google-auth` and `google-auth-oauthlib` libraries
- **Gmail IMAP**: Connect using Python's `imaplib` with OAuth2 credentials
- **Credentials Setup**: User must provide `credentials.json` from Google Cloud Console
- **Token Management**: Store and refresh OAuth2 tokens in SQLite database

### Clustering Algorithm
- **Method**: TF-IDF vectorization + K-means clustering (user selected this over simple keyword-based)
- **Libraries**: Use `scikit-learn` for both TF-IDF and K-means
- **Parameters**: 
  - Max 1000 TF-IDF features
  - 3 clusters minimum (requirement: "at least three descriptive clusters")
  - Include bigrams (ngram_range=(1, 2))
- **Text Preprocessing**: Remove HTML, normalize text, remove stop words

### Archive Functionality
- **Behavior**: Archive all emails in cluster and remove from inbox view (user specified)
- **Implementation**: Use Gmail IMAP to move emails to "All Mail" label and remove "INBOX" label
- **UI Update**: Remove archived cluster from frontend display

## Critical Technical Details

### Project Structure (Must Follow)
```
gmail-email-clustering/
├── backend/
│   ├── app.py                 # Main Flask app
│   ├── auth/
│   │   ├── oauth.py          # OAuth2 implementation
│   │   └── gmail_client.py   # IMAP client
│   ├── clustering/
│   │   ├── preprocessor.py   # Text preprocessing
│   │   ├── vectorizer.py     # TF-IDF
│   │   └── clusterer.py      # K-means
│   ├── database/
│   │   ├── models.py         # SQLite models
│   │   └── init_db.py        # DB initialization
│   └── api/
│       └── routes.py         # API endpoints
├── frontend/
│   ├── index.html
│   └── static/
│       ├── css/style.css
│       └── js/app.js
├── requirements.txt
├── deploy.sh                 # Based on ref_deploy.sh
└── config.py
```

### Required Dependencies
```
Flask==2.3.3
google-auth==2.23.3
google-auth-oauthlib==1.1.0
scikit-learn==1.3.0
nltk==3.8.1
gunicorn==21.2.0
```

### Database Schema (SQLite)
```sql
CREATE TABLE emails (
    id INTEGER PRIMARY KEY,
    gmail_id TEXT UNIQUE,
    subject TEXT,
    sender TEXT,
    body TEXT,
    date_received DATETIME,
    is_archived BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE clusters (
    id INTEGER PRIMARY KEY,
    label TEXT,
    description TEXT,
    email_count INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE email_clusters (
    email_id INTEGER,
    cluster_id INTEGER,
    FOREIGN KEY (email_id) REFERENCES emails(id),
    FOREIGN KEY (cluster_id) REFERENCES clusters(id)
);

CREATE TABLE user_sessions (
    id INTEGER PRIMARY KEY,
    access_token TEXT,
    refresh_token TEXT,
    expires_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Essential API Endpoints
```python
@app.route('/api/auth/login')           # Start OAuth2 flow
@app.route('/api/auth/callback')        # OAuth2 callback
@app.route('/api/emails/fetch')         # Fetch & cluster emails
@app.route('/api/clusters')             # Get clustered emails
@app.route('/api/clusters/<id>/archive', methods=['POST'])  # Archive cluster
```

### Frontend Requirements
- **Technology**: Pure HTML/CSS/JavaScript (no frameworks)
- **Features**: 
  - OAuth2 login button
  - Display 3+ clusters with descriptive names
  - Show email previews in each cluster
  - One-click archive button per cluster
  - Loading states and error handling
- **Responsive**: Must work on desktop and mobile

### Deployment Configuration
- **Server**: Gunicorn with 4 workers on port 80
- **Environment**: Production Flask settings
- **Database**: SQLite in `data/cache/` directory
- **Python Path**: Include backend directory
- **Working Directory**: Project root for correct paths

## Implementation Sequence (Todo List)

1. **Project Setup**: Create directory structure and requirements.txt
2. **OAuth2 Setup**: Implement Google OAuth2 flow with credential handling
3. **Gmail IMAP**: Build IMAP client for fetching and archiving emails
4. **Text Processing**: Create preprocessing pipeline for email content
5. **Clustering**: Implement TF-IDF + K-means clustering
6. **Frontend**: Build simple HTML/CSS/JS interface
7. **API Layer**: Create Flask routes for all functionality
8. **Database**: Set up SQLite with caching logic
9. **Deployment**: Create deploy.sh based on ref_deploy.sh template
10. **Testing**: Test OAuth2, clustering, and archiving end-to-end

## Critical Implementation Notes

### OAuth2 Flow
```python
# Key OAuth2 scopes needed:
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify'
]
```

### Gmail IMAP Connection
```python
# Use OAuth2 for IMAP authentication:
import imaplib
mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.authenticate('XOAUTH2', lambda x: oauth2_string)
```

### Clustering Pipeline
```python
# TF-IDF Configuration:
TfidfVectorizer(
    max_features=1000,
    stop_words='english',
    ngram_range=(1, 2),
    min_df=2,
    max_df=0.8
)

# K-means Configuration:
KMeans(n_clusters=3, random_state=42, n_init=10)
```

### Archive Implementation
```python
# Gmail IMAP archive command:
mail.store(email_id, '+X-GM-LABELS', '\\All')
mail.store(email_id, '-X-GM-LABELS', '\\Inbox')
```

## User Setup Requirements

1. **Google Cloud Console**:
   - Create new project
   - Enable Gmail API
   - Create OAuth2 credentials (Desktop application)
   - Download credentials.json

2. **Local Setup**:
   - Place credentials.json in project root
   - Run deploy.sh script
   - Access application at http://localhost or server IP

## Success Criteria

- ✅ OAuth2 authentication with Gmail works
- ✅ Fetches exactly 200 most recent emails
- ✅ Generates at least 3 meaningful clusters
- ✅ Cluster names are descriptive (not just "Cluster 1, 2, 3")
- ✅ One-click archive removes entire cluster from view
- ✅ Simple, clean frontend interface
- ✅ Runs locally without external dependencies
- ✅ Deploy script works on Ubuntu/Linux systems

## Common Pitfalls to Avoid

1. **OAuth2 Errors**: Ensure redirect URI matches Google Console settings
2. **IMAP Authentication**: Use proper OAuth2 string format for IMAP
3. **Clustering Quality**: Preprocess email text properly (remove HTML, normalize)
4. **Archive Functionality**: Test that emails actually disappear from Gmail inbox
5. **Frontend UX**: Handle loading states and error messages properly
6. **Deployment**: Ensure all paths are relative to project root
7. **Database**: Initialize SQLite database before first use

## Testing Checklist

- [ ] OAuth2 login redirects to Google and back successfully
- [ ] Application fetches exactly 200 emails from Gmail
- [ ] Emails are clustered into meaningful groups (not random)
- [ ] Cluster names describe the content (e.g., "Newsletters", "Work Emails")
- [ ] Archive button removes cluster from UI and Gmail inbox
- [ ] Application works after server restart (persistent data)
- [ ] Deploy script runs without errors on clean system
- [ ] Frontend is responsive and user-friendly

## Reference Files

- **readme.md**: Original project requirements
- **ref_deploy.sh**: Deployment script template to adapt
- **architecture_plan.md**: Detailed technical architecture and design

This guide provides all the essential information needed to implement the Gmail email clustering application according to the specified requirements and user preferences.