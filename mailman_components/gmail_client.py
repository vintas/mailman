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

def get_label_id_by_name(service, label_name, user_id='me'):
    """
    Fetches the ID of a label given its name. Caches results.
    Standard labels like INBOX, SPAM, TRASH, UNREAD, IMPORTANT, DRAFT, SENT can often be used directly
    as IDs in modify requests or have well-known names.
    This is more for custom user-created labels.
    """
    if not label_name:
        return None

    # Check cache first
    if label_name in _label_cache:
        return _label_cache[label_name]

    # Standard system labels (case-insensitive for matching, but API uses uppercase)
    standard_labels = {
        "inbox": "INBOX",
        "spam": "SPAM",
        "trash": "TRASH",
        "unread": "UNREAD",
        "important": "IMPORTANT",
        "draft": "DRAFT", # Actually DRAFTS
        "sent": "SENT",
        "starred": "STARRED",
        "category_personal": "CATEGORY_PERSONAL",
        "category_social": "CATEGORY_SOCIAL",
        "category_promotions": "CATEGORY_PROMOTIONS",
        "category_updates": "CATEGORY_UPDATES",
        "category_forums": "CATEGORY_FORUMS",
    }
    if label_name.lower() in standard_labels:
        _label_cache[label_name] = standard_labels[label_name.lower()]
        return standard_labels[label_name.lower()]

    try:
        results = service.users().labels().list(userId=user_id).execute()
        labels = results.get('labels', [])
        for label in labels:
            # Cache all fetched labels for future use
            _label_cache[label['name']] = label['id']
            if label['name'].lower() == label_name.lower():
                return label['id']
        print(f"Label '{label_name}' not found among user labels.")
        _label_cache[label_name] = None # Cache miss
        return None
    except HttpError as error:
        print(f"An API error occurred while fetching labels: {error}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while fetching labels: {e}")
        return None


def modify_message_labels(service, msg_id, add_label_ids=None, remove_label_ids=None, user_id='me'):
    """
    Modifies the labels on a message.
    Args:
        service: Authorized Gmail API service instance.
        msg_id: The ID of the message to modify.
        add_label_ids: List of Label IDs to add.
        remove_label_ids: List of Label IDs to remove.
        user_id: User's email address. 'me' for authenticated user.
    Returns:
        The modified message resource or None if an error occurs.
    """
    if not add_label_ids and not remove_label_ids:
        print("No labels to add or remove.")
        return None

    body = {}
    if add_label_ids:
        body['addLabelIds'] = add_label_ids
    if remove_label_ids:
        body['removeLabelIds'] = remove_label_ids
    
    try:
        message = service.users().messages().modify(userId=user_id, id=msg_id, body=body).execute()
        print(f"Modified labels for message {msg_id}. Added: {add_label_ids}, Removed: {remove_label_ids}")
        return message
    except HttpError as error:
        print(f'An API error occurred while modifying message {msg_id}: {error}')
        return None
    except Exception as e:
        print(f'An unexpected error occurred while modifying message {msg_id}: {e}')
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

                # 3. Test get_label_id_by_name
                print("\n--- Testing get_label_id_by_name ---")
                inbox_label_id = get_label_id_by_name(gmail_service, "INBOX")
                print(f"ID for 'INBOX': {inbox_label_id}")
                
                custom_label_name = "MyTestLabelMailman" # Replace if you have a specific custom label
                custom_label_id = get_label_id_by_name(gmail_service, custom_label_name)
                if custom_label_id:
                    print(f"ID for '{custom_label_name}': {custom_label_id}")
                else:
                    print(f"Custom label '{custom_label_name}' not found or no ID retrieved.")
                
                # 4. Test modify_message_labels (Example: add 'IMPORTANT', remove 'UNREAD' if present)
                # Be careful with this test as it modifies your actual email.
                # print("\n--- Testing modify_message_labels (Conceptual) ---")
                # if message_detail and 'UNREAD' in message_detail.get('labelIds', []):
                #     print(f"Attempting to mark message {test_msg_id} as read and important.")
                #     modified_msg = modify_message_labels(
                #         gmail_service,
                #         msg_id=test_msg_id,
                #         add_label_ids=['IMPORTANT'],
                #         remove_label_ids=['UNREAD']
                #     )
                #     if modified_msg:
                #         print(f"Message {test_msg_id} modified. New labels: {modified_msg.get('labelIds')}")
                # else:
                # print(f"Skipping modify test for message {test_msg_id} (not unread or no details).")
            else:
                print("No messages found in inbox to test with.")
        else:
            print("Failed to obtain Gmail service. Cannot run tests.")

    except ImportError as e:
        print(f"ImportError: {e}. Make sure you are in the project root directory and run as 'python -m mailman_components.gmail_client'")
    except Exception as e:
        print(f"An error occurred during testing: {e}")
