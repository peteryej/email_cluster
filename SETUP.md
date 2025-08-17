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

#### Step 3: Configure OAuth Consent Screen
1. Go to "APIs & Services" → "OAuth consent screen"
2. Choose "External" user type and click "Create"
3. Fill in the OAuth consent screen details:
   - **App name**: `Gmail Email Clustering`
   - **User support email**: Your email address
   - **App logo**: (Optional) Upload a logo
   - **App domain**: Leave blank for now
   - **Authorized domains**: Leave blank for desktop app
   - **Developer contact information**: Your email address
4. Click "Save and Continue"
5. On the "Scopes" page, click "Add or Remove Scopes":
   - Search for and add: `https://www.googleapis.com/auth/gmail.readonly`
   - Search for and add: `https://www.googleapis.com/auth/gmail.modify`
   - Click "Update" then "Save and Continue"
6. On the "Test users" page, click "Add Users":
   - Add your Gmail address that you'll use to test the app
   - Click "Save and Continue"
7. Review the summary and click "Back to Dashboard"

#### Step 4: Create OAuth2 Desktop App Credentials
1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Select **Application type**: "Desktop application"
4. **Name**: `Gmail Clustering Desktop Client`
5. Click "Create"
6. **Important**: Download the credentials JSON file immediately
7. **Rename** the downloaded file to `credentials.json`
8. **Copy** this file to the root directory of your project (same folder as this SETUP.md)

**Note**: For desktop applications, you don't need to configure redirect URIs - Google handles this automatically with a local redirect mechanism.

#### Understanding Desktop App Authentication Flow

With desktop app credentials, the authentication process works as follows:

1. **User clicks "Login with Gmail"** in the web interface
2. **App generates authorization URL** that opens in user's browser
3. **User authorizes the app** in Google's consent screen
4. **Google shows authorization code** to the user (instead of redirecting)
5. **User copies the code** and pastes it back into the app
6. **App exchanges the code** for access tokens

This is more secure than web app flow for server-based applications and doesn't require configuring redirect URIs.

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
source venv/bin/activate && python3 backend/app.py
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
1. Ensure `credentials.json` is in the project root directory
2. Run: `source venv/bin/activate && python3 backend/app.py`
3. Visit: `http://localhost:5000`
4. Click "Login with Gmail" and follow the desktop app authentication flow

#### Production Testing
1. Ensure `credentials.json` is in the project root directory
2. Deploy with: `sudo ./deploy.sh`
3. Visit: `http://your-server-ip`
4. Click "Login with Gmail" and follow the desktop app authentication flow

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

#### 2. "OAuth2 authentication failed" 
- Ensure you're using **Desktop application** credentials from Google Cloud Console
- Verify the OAuth consent screen is properly configured with correct scopes
- Make sure your Gmail address is added as a test user
- Check that you're copying the full authorization code (no extra spaces)

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
source venv/bin/activate && python3 backend/app.py  # Check console output
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