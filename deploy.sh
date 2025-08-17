#!/bin/bash

# Gmail Email Clustering Application Deployment Script
# Based on ref_deploy.sh template

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "ERROR: This script must be run with sudo"
    echo "Please run: sudo ./deploy.sh"
    exit 1
fi

echo "Starting deployment for Gmail Email Clustering Application..."

# Set production environment variables
export FLASK_ENV=production
export FLASK_DEBUG=False

# Create necessary directories
mkdir -p data/cache

# Get absolute path to current directory
SCRIPT_DIR=$(pwd)
VENV_DIR="$SCRIPT_DIR/venv"

# Check if python3-venv is properly installed
echo "Checking python3-venv installation..."
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
VENV_PACKAGE="python${PYTHON_VERSION}-venv"

echo "Python version: $PYTHON_VERSION"
echo "Required package: $VENV_PACKAGE"

# Install the correct python3-venv package if not available
if ! dpkg -l | grep -q "$VENV_PACKAGE"; then
    echo "Installing $VENV_PACKAGE..."
    apt update
    apt install -y "$VENV_PACKAGE"
fi

# Install additional system dependencies
echo "Installing system dependencies..."
apt install -y python3-pip python3-dev build-essential

# Remove existing virtual environment if it exists but is broken
if [ -d "$VENV_DIR" ]; then
    echo "Removing existing virtual environment..."
    rm -rf "$VENV_DIR"
fi

# Create and setup virtual environment FIRST
echo "Creating virtual environment at $VENV_DIR..."
python3 -m venv "$VENV_DIR"

# Check if creation was successful
if [ $? -ne 0 ]; then
    echo "ERROR: Virtual environment creation failed!"
    echo "Trying to install python3-venv and python3-pip..."
    apt install -y python3-venv python3-pip
    python3 -m venv "$VENV_DIR"
    
    if [ $? -ne 0 ]; then
        echo "ERROR: Virtual environment creation still failed!"
        exit 1
    fi
fi

# Debug: List contents of venv directory
echo "Contents of venv directory:"
ls -la "$VENV_DIR/" || echo "venv directory does not exist"

echo "Contents of venv/bin directory:"
ls -la "$VENV_DIR/bin/" || echo "bin directory does not exist"

# Check if pip and activate are missing (common issue on Ubuntu)
if [ ! -f "$VENV_DIR/bin/pip" ] || [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Virtual environment is incomplete (missing pip or activate)"
    echo "Recreating with --copies and ensuring ensurepip..."
    rm -rf "$VENV_DIR"
    python3 -m venv --copies "$VENV_DIR"
    
    # Manually ensure pip is installed
    "$VENV_DIR/bin/python" -m ensurepip --upgrade
    
    echo "Contents of venv/bin directory after recreation:"
    ls -la "$VENV_DIR/bin/"
fi

# Verify virtual environment was created successfully
if [ ! -f "$VENV_DIR/bin/python" ] && [ ! -f "$VENV_DIR/bin/python3" ]; then
    echo "ERROR: Virtual environment creation failed!"
    echo "Neither $VENV_DIR/bin/python nor $VENV_DIR/bin/python3 exists"
    exit 1
fi

echo "Virtual environment created successfully"

# Determine which python executable to use
if [ -f "$VENV_DIR/bin/python" ]; then
    PYTHON_EXEC="$VENV_DIR/bin/python"
    PIP_EXEC="$VENV_DIR/bin/pip"
elif [ -f "$VENV_DIR/bin/python3" ]; then
    PYTHON_EXEC="$VENV_DIR/bin/python3"
    PIP_EXEC="$VENV_DIR/bin/pip3"
else
    echo "ERROR: No python executable found in virtual environment"
    exit 1
fi

echo "Using Python executable: $PYTHON_EXEC"
echo "Using pip executable: $PIP_EXEC"

echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

echo "Installing/updating dependencies..."
"$PIP_EXEC" install --upgrade pip

# Check if requirements.txt exists
if [ ! -f "requirements.txt" ]; then
    echo "ERROR: requirements.txt not found!"
    exit 1
fi

"$PIP_EXEC" install -r requirements.txt

# Install additional dependencies for production
"$PIP_EXEC" install flask-cors

# Verify dependencies were installed
if [ ! -f "$VENV_DIR/bin/gunicorn" ]; then
    echo "Installing gunicorn..."
    "$PIP_EXEC" install gunicorn
fi

# Check if credentials.json exists
if [ ! -f "credentials.json" ]; then
    echo "WARNING: credentials.json not found!"
    echo "Please download your OAuth2 credentials from Google Cloud Console"
    echo "and save them as 'credentials.json' in the project root directory."
    echo "The application will not work without this file."
fi

# Initialize database AFTER dependencies are installed
echo "Initializing database..."
"$PYTHON_EXEC" backend/database/init_db.py

# Download NLTK data
echo "Downloading NLTK data..."
"$PYTHON_EXEC" -c "
import nltk
import ssl
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
print('NLTK data downloaded successfully')
"

# Start the application
echo "Starting Gmail Email Clustering Application..."

# Try to get public IP (works on AWS)
PUBLIC_IP=$(curl -s --connect-timeout 5 http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "your-server-ip")
echo "Application will be available at: http://$PUBLIC_IP"

# Set Python path to include backend directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)/backend"

# Set working directory for database paths
export WORKING_DIR=$(pwd)

# Create the Flask app instance
export FLASK_APP=backend.app:app

# Set production configuration
export SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Run with gunicorn for production (stay in root directory for correct paths)
echo "Starting with Gunicorn on port 80..."

# Create a simple systemd service file for auto-restart
cat > /etc/systemd/system/gmail-clustering.service << EOF
[Unit]
Description=Gmail Email Clustering Application
After=network.target

[Service]
Type=exec
User=root
WorkingDirectory=$SCRIPT_DIR
Environment=FLASK_ENV=production
Environment=FLASK_DEBUG=False
Environment=PYTHONPATH=$SCRIPT_DIR/backend
Environment=WORKING_DIR=$SCRIPT_DIR
Environment=FLASK_APP=backend.app:app
Environment=SECRET_KEY=$SECRET_KEY
ExecStart=$VENV_DIR/bin/gunicorn -w 4 -b 0.0.0.0:80 --timeout 300 --access-logfile - --error-logfile - --chdir $SCRIPT_DIR backend.app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
systemctl daemon-reload
systemctl enable gmail-clustering.service
systemctl start gmail-clustering.service

echo "Gmail Email Clustering Application deployed successfully!"
echo "Service status:"
systemctl status gmail-clustering.service --no-pager

echo ""
echo "To check logs: sudo journalctl -u gmail-clustering.service -f"
echo "To restart: sudo systemctl restart gmail-clustering.service"
echo "To stop: sudo systemctl stop gmail-clustering.service"
echo ""
echo "Make sure to:"
echo "1. Place your credentials.json file in $SCRIPT_DIR"
echo "2. Configure your Google Cloud Console OAuth2 settings"
echo "3. Set the redirect URI to: http://$PUBLIC_IP/api/auth/callback"