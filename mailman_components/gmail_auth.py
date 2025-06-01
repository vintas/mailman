import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import CLIENT_SECRET_FILE, TOKEN_FILE, API_SCOPES

def get_gmail_service():
    """Authenticate and return a Gmail API service instance."""
    creds = None
    # Load existing credentials from token file
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, API_SCOPES)
    
    # If no valid credentials, initiate the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, API_SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    
    try:
        # Build the Gmail API service
        service = build('gmail', 'v1', credentials=creds)
        return service
    except HttpError as error:
        print(f'An HttpError occurred: {error}')
        return None
    except Exception as e:
        print(f'An unexpected error occurred: {e}')
        return None



if __name__ == "__main__":
  service = get_gmail_service()
  if service:
        print("Successfully authenticated and created Gmail service.")
        # Example: List labels
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        if not labels:
            print('No labels found.')
        else:
            print('Labels:')
            for label in labels:
                print(f"- {label['name']}")
