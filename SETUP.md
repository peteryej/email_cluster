# Gmail Email Clustering - Setup Guide

This guide will help you set up and deploy the Gmail Email Clustering application.

## Prerequisites

- Ubuntu/Linux server with root access
- Python 3.8 or higher
- Internet connection
- Gmail account with API access

## Quick Start

1. **Clone or download this project** to your server
2. **Set up Google OAuth2 credentials** (see detailed steps below)
3. **Run the deployment script**:
   ```bash
   sudo ./deploy.sh
   ```
4. **Access the application** at `http://your-server-ip`

## Detailed Setup Instructions

### 1. Google Cloud Console Setup

#### Step 1: Create a Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Enter project name: `gmail-email-clustering`
4. Click "Create"

#### Step 2: Enable Gmail API
1. In your project, go to "APIs & Services" → "Library"
2. Search for "Gmail API"
3. Click on "Gmail API" and click "Enable"

#### Step 3: Create OAuth2 Credentials
1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. If prompted, configure the OAuth consent screen:
   - Choose "External" user type
   - Fill in required fields:
     - App name: `Gmail Email Clustering`
     - User support email: your email
     - Developer contact: your email
   - Add scopes: `../auth/gmail.readonly` and `../auth/gmail.modify`
   - Add test users: your Gmail address
4. For OAuth client ID:
   - Application type: "Desktop application"
   - Name: `Gmail Clustering Client`
5. Click "Create"
6. Download the JSON file and save it as `credentials.json` in the project root

#### Step 4: Configure Redirect URI
1. Edit your OAuth2 client
2. Add authorized redirect URI: `http://your-server-ip/api/auth/callback`
3. For local testing: `http://localhost:5000/api/auth/callback`

### 2. Server Setup

#### Option A: Automatic Deployment (Recommended)
```bash
# Make deploy script executable
chmod +x deploy.sh

# Run deployment (requires sudo)
sudo ./deploy.sh
```

#### Option B: Manual Setup
```bash
# Install system dependencies
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-dev build-essential

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Initialize database
python backend/database/init_db.py

# Download NLTK data
python -c "
import nltk
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
"

# Run development server
python backend/app.py
```

### 3. Configuration

#### Environment Variables
The application uses these environment variables:

```bash
FLASK_ENV=production          # Set to 'development' for local testing
FLASK_DEBUG=False            # Set to 'True' for debugging
SECRET_KEY=your-secret-key   # Auto-generated in production
```

#### Configuration Files
- `config.py` - Main application configuration
- `credentials.json` - Google OAuth2 credentials (you must provide this)

### 4. Testing the Application

#### Local Testing
1. Set up credentials with redirect URI: `http://localhost:5000/api/auth/callback`
2. Run: `python backend/app.py`
3. Visit: `http://localhost:5000`

#### Production Testing
1. Set up credentials with redirect URI: `http://your-server-ip/api/auth/callback`
2. Deploy with: `sudo ./deploy.sh`
3. Visit: `http://your-server-ip`

### 5. Usage Instructions

1. **Login**: Click "Login with Gmail" and authorize the application
2. **Enter Email**: Provide your Gmail address
3. **Fetch Emails**: Click "Fetch & Cluster Emails" to analyze your last 200 emails
4. **View Clusters**: Browse the automatically generated email clusters
5. **Archive**: Click "Archive Cluster" to move entire groups to Gmail's All Mail

## Project Structure

```
gmail-email-clustering/
├── backend/                 # Python Flask backend
│   ├── app.py              # Main Flask application
│   ├── config.py           # Configuration settings
│   ├── auth/               # OAuth2 and Gmail IMAP
│   ├── clustering/         # ML clustering algorithms
│   ├── database/           # SQLite database models
│   └── api/                # REST API endpoints
├── frontend/               # HTML/CSS/JS frontend
│   ├── index.html          # Main application page
│   └── static/             # CSS and JavaScript files
├── data/                   # SQLite database storage
├── deploy.sh               # Production deployment script
├── requirements.txt        # Python dependencies
└── credentials.json        # Google OAuth2 credentials (you provide)
```

## Troubleshooting

### Common Issues

#### 1. "credentials.json not found"
- Download OAuth2 credentials from Google Cloud Console
- Save as `credentials.json` in project root
- Ensure file has correct JSON format

#### 2. "OAuth2 redirect URI mismatch"
- Check redirect URI in Google Cloud Console matches your server
- For local: `http://localhost:5000/api/auth/callback`
- For production: `http://your-server-ip/api/auth/callback`

#### 3. "Failed to connect to Gmail IMAP"
- Ensure Gmail API is enabled in Google Cloud Console
- Check OAuth2 scopes include Gmail access
- Verify credentials are valid and not expired

#### 4. "Permission denied" during deployment
- Run deployment script with sudo: `sudo ./deploy.sh`
- Ensure script is executable: `chmod +x deploy.sh`

#### 5. "No emails found"
- Check Gmail account has emails in inbox
- Verify OAuth2 permissions include Gmail read access
- Try with a different Gmail account

### Logs and Debugging

#### Check Application Logs
```bash
# For systemd service (production)
sudo journalctl -u gmail-clustering.service -f

# For development
python backend/app.py  # Check console output
```

#### Check Service Status
```bash
# Service status
sudo systemctl status gmail-clustering.service

# Restart service
sudo systemctl restart gmail-clustering.service

# Stop service
sudo systemctl stop gmail-clustering.service
```

### Performance Optimization

#### For Large Email Volumes
- Increase clustering timeout in `config.py`
- Adjust TF-IDF parameters for better performance
- Consider reducing `MAX_EMAILS` from 200 to smaller number

#### For Better Clustering
- Modify clustering parameters in `backend/clustering/`
- Adjust number of clusters based on email patterns
- Fine-tune text preprocessing for your email types

## Security Considerations

1. **Credentials Security**
   - Keep `credentials.json` secure and private
   - Don't commit credentials to version control
   - Use environment variables for sensitive data

2. **Network Security**
   - Use HTTPS in production (configure reverse proxy)
   - Implement rate limiting for API endpoints
   - Monitor for unusual access patterns

3. **Data Privacy**
   - Email data is stored locally in SQLite
   - No data is sent to external services except Google
   - Consider encryption for sensitive email content

## Support

For issues and questions:
1. Check this setup guide
2. Review the troubleshooting section
3. Check application logs
4. Verify Google Cloud Console configuration

## License

This project is for educational and personal use. Ensure compliance with Gmail API terms of service.