import os
import sys
import time
from googleapiclient.errors import HttpError

# A simple cache for label IDs to minimize API calls
_label_cache = {}

def list_message_ids(service, user_id='me', query='in:inbox', max_results=20):
    """
    Lists message IDs matching the query.
    Args:
        service: Authorized Gmail API service instance.
        user_id: User's email address. The special value 'me' can be used to indicate the authenticated user.
        query: String used to filter messages returned. Eg.- 'from:user@some_domain.com'
        max_results: Maximum number of messages to return.
    Returns:
        List of message IDs.
    """
    message_ids = []
    try:
        response = service.users().messages().list(userId=user_id, q=query, maxResults=max_results).execute()
        if 'messages' in response:
            message_ids.extend(m['id'] for m in response['messages'])

        # TODO nextPageToken

        print(f"Found {len(message_ids)} message IDs matching query '{query}'.")
        return message_ids
    except HttpError as error:
        print(f'An API error occurred while listing messages: {error}')
        return []
    except Exception as e:
        print(f'An unexpected error occurred while listing messages: {e}')
        return []

def get_message_detail(service, msg_id, user_id='me'):
    """
    Get a Message and its payload.
    Args:
        service: Authorized Gmail API service instance.
        msg_id: The ID of the Message required.
        user_id: User's email address. The special value 'me' can be used to indicate the authenticated user.
    Returns:
        Message resource, including payload, or None if an error occurs.
    """
    try:
        # 'full' format gets parsed payload, headers, and body
        # 'metadata' gets only headers and basic info
        # 'raw' gets the full RFC 2822 message
        message = service.users().messages().get(userId=user_id, id=msg_id, format='full').execute()
        return message
    except HttpError as error:
        print(f'An API error occurred while getting message {msg_id}: {error}')
        return None
    except Exception as e:
        print(f'An unexpected error occurred while getting message {msg_id}: {e}')
        return None

if __name__ == '__main__':
    # This block is for testing this module directly.
    print("Testing gmail_client.py...")
    
    # Add project root to sys.path to allow importing config and other components
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir) 
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    try:
        from mailman_components.gmail_auth import get_gmail_service
        
        gmail_service = get_gmail_service()
        if gmail_service:
            print("Successfully obtained Gmail service.")

            # 1. Test list_message_ids
            print("\n--- Testing list_message_ids ---")
            # Fetch top 5 messages from inbox
            message_ids = list_message_ids(gmail_service, query='in:inbox', max_results=5)
            if message_ids:
                print(f"First 5 message IDs from inbox: {message_ids}")

                # 2. Test get_message_detail (on the first message found)
                print("\n--- Testing get_message_detail ---")
                test_msg_id = message_ids[0]
                message_detail = get_message_detail(gmail_service, msg_id=test_msg_id)
                if message_detail:
                    print(f"Details for message {test_msg_id}:")
                    print(f"  Snippet: {message_detail.get('snippet')}")
                    print(f"  Labels: {message_detail.get('labelIds')}")
                else:
                    print(f"Could not fetch details for message {test_msg_id}.")

            else:
                print("No messages found in inbox to test with.")
        else:
            print("Failed to obtain Gmail service. Cannot run tests.")

    except ImportError as e:
        print(f"ImportError: {e}. Make sure you are in the project root directory and run as 'python -m mailman_components.gmail_client'")
    except Exception as e:
        print(f"An error occurred during testing: {e}")
