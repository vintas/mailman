import os

# Path to the directory where this config.py file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Credentials
CLIENT_SECRET_FILE = os.path.join(BASE_DIR, 'credentials', 'client_secret.json')
TOKEN_FILE = os.path.join(BASE_DIR, 'credentials', 'token.json')

# Gmail API Scopes
# Using 'gmail.modify' as it covers the required minimum: reading, and changing labels (moving, marking as read/unread)
API_SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Database
DATABASE_NAME = 'emails.db'
DATABASE_URI = f'sqlite:///{os.path.join(BASE_DIR, DATABASE_NAME)}'

# Rules file
RULES_FILE = os.path.join(BASE_DIR, 'rules.json')

# Ensure the credentials directory exists
os.makedirs(os.path.dirname(CLIENT_SECRET_FILE), exist_ok=True)

# Ensure the rules file exists
if not os.path.exists(RULES_FILE):
    with open(RULES_FILE, 'w') as f:
        f.write("[]")  # Create an empty JSON array