import base64
import json
from datetime import datetime
from email.utils import parsedate_to_datetime, getaddresses

def decode_base64url(data):
    """
    Decodes a base64url encoded string.
    """
    if not data:
        return None
    padding = '=' * (4 - len(data) % 4)
    data += padding
    # return base64.urlsafe_b64decode(data).decode('utf-8')
    try:
        return base64.urlsafe_b64decode(data).decode('utf-8', 'ignore')
    except Exception as e:
        print(f"Error decoding base64url data: {e}")
        return None

def get_header_value(headers, name):
    """Extracts a specific header value from a list of headers."""
    for header in headers:
        if header['name'].lower() == name.lower():
            return header['value']
    return None

def parse_addresses(address_string):
    """
    Parses a string containing one or more email addresses.
    Returns a list of full 'Name <email@example.com>' strings.
    If simple email like 'email@example.com' is in the string, it returns that.
    """
    if not address_string:
        return []
    # getaddresses returns a list of (realname, email_address) tuples
    parsed_addresses = getaddresses([address_string])
    formatted_addresses = []
    for realname, email_address in parsed_addresses:
        if realname:
            formatted_addresses.append(f"{realname} <{email_address}>")
        else:
            formatted_addresses.append(email_address)
    return formatted_addresses

def find_email_parts(parts_data):
    """
    Recursively searches for text/plain and text/html parts and decodes their content.
    Handles nested multipart messages.
    """
    plain_body = None
    html_body = None
    attachments = [] # Placeholder for future attachment handling

    if not parts_data:
        return plain_body, html_body, attachments

    for part in parts_data:
        mime_type = part.get('mimeType', '').lower()
        
        if 'parts' in part: # This is a multipart/* sub-message
            sub_plain, sub_html, sub_attachments = find_email_parts(part['parts'])
            if sub_plain and not plain_body: # Take the first one found
                plain_body = sub_plain
            if sub_html and not html_body: # Take the first one found
                html_body = sub_html
            attachments.extend(sub_attachments)
        else: # Not a multipart/* itself, could be a direct body part
            body_data = part.get('body', {}).get('data')
            if body_data:
                decoded_content = decode_base64url(body_data)
                if mime_type == 'text/plain' and not plain_body:
                    plain_body = decoded_content
                elif mime_type == 'text/html' and not html_body:
                    html_body = decoded_content
                # TODO Future: Handle attachments based on Content-Disposition etc.
                # filename = part.get('filename')
                # if filename and decoded_content:
                #     attachments.append({'filename': filename, 'mime_type': mime_type, 'data': decoded_content})

    return plain_body, html_body, attachments

def parse_email_data(api_response):
    """
    Parses the raw Gmail API response for a single message.
    Returns a dictionary suitable for storing in the database.
    """
    if not api_response:
        return None

    parsed_data = {}
    payload = api_response.get('payload', {})
    headers = payload.get('headers', [])

    # Basic metadata
    parsed_data['message_id'] = api_response.get('id')
    parsed_data['thread_id'] = api_response.get('threadId')
    parsed_data['snippet'] = api_response.get('snippet')
    parsed_data['labels'] = json.dumps(api_response.get('labelIds', [])) # Store as JSON string

    # Extract headers
    parsed_data['from_address'] = get_header_value(headers, 'From')
    
    # For To, Cc, Bcc, they can be multiple. We'll store them as JSON lists of strings.
    to_header = get_header_value(headers, 'To')
    parsed_data['to_addresses'] = json.dumps(parse_addresses(to_header)) if to_header else json.dumps([])
    
    cc_header = get_header_value(headers, 'Cc')
    parsed_data['cc_addresses'] = json.dumps(parse_addresses(cc_header)) if cc_header else json.dumps([])
    
    bcc_header = get_header_value(headers, 'Bcc')
    parsed_data['bcc_addresses'] = json.dumps(parse_addresses(bcc_header)) if bcc_header else json.dumps([])
    
    parsed_data['subject'] = get_header_value(headers, 'Subject')

    # Date parsing
    date_str = get_header_value(headers, 'Date')
    if date_str:
        try:
            parsed_data['received_datetime'] = parsedate_to_datetime(date_str)
        except Exception as e:
            print(f"Could not parse date string '{date_str}': {e}. Falling back to internalDate.")
            # Fallback to internalDate if Date header is problematic or missing
            internal_date_ms = api_response.get('internalDate')
            if internal_date_ms:
                parsed_data['received_datetime'] = datetime.fromtimestamp(int(internal_date_ms) / 1000.0)
            else:
                parsed_data['received_datetime'] = datetime.utcnow() # Last resort
    else:
        internal_date_ms = api_response.get('internalDate')
        if internal_date_ms:
            parsed_data['received_datetime'] = datetime.fromtimestamp(int(internal_date_ms) / 1000.0)
        else:
            # Last resort
            parsed_data['received_datetime'] = datetime.utcnow()


    # Store all headers as a JSON string
    raw_headers_dict = {header['name']: header['value'] for header in headers}
    parsed_data['raw_headers'] = json.dumps(raw_headers_dict)

    # Body content
    mime_type = payload.get('mimeType', '').lower()
    plain_body = None
    html_body = None

    if mime_type.startswith('multipart/'):
        parts = payload.get('parts', [])
        plain_body, html_body, _ = find_email_parts(parts)
    elif mime_type in ['text/plain', 'text/html']:
        body_data = payload.get('body', {}).get('data')
        if body_data:
            decoded_content = decode_base64url(body_data)
            if mime_type == 'text/plain':
                plain_body = decoded_content
            elif mime_type == 'text/html':
                html_body = decoded_content
    
    parsed_data['body_plain'] = plain_body
    parsed_data['body_html'] = html_body

    # Ensure all fields required by DB model are present, even if None
    db_fields = [
        'message_id', 'thread_id', 'from_address', 'to_addresses', 
        'cc_addresses', 'bcc_addresses', 'subject', 'body_plain', 
        'body_html', 'snippet', 'received_datetime', 'labels', 'raw_headers'
    ]
    for field in db_fields:
        if field not in parsed_data:
            # Set appropriate default, e.g., None for text, [] for JSON lists, now() for datetime
            if field.endswith('_addresses') or field == 'labels':
                 parsed_data[field] = json.dumps([])
            elif field == 'received_datetime':
                parsed_data[field] = datetime.utcnow()
            else:
                parsed_data[field] = None

    return parsed_data

if __name__ == '__main__':
    # Example of a raw API response (simplified and truncated)
    sample_api_response = {
        "id": "17exampleMessageId",
        "threadId": "17exampleThreadId",
        "labelIds": ["INBOX", "UNREAD", "IMPORTANT"],
        "snippet": "This is a test email snippet.",
        "internalDate": str(int(datetime.now().timestamp() * 1000)), # milliseconds string
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "Date", "value": "Mon, 03 Jun 2024 10:00:00 +0530"},
                {"name": "From", "value": "Sender Name <sender@example.com>"},
                {"name": "To", "value": "Recipient 1 <recipient1@example.com>, recipient2@example.com"},
                {"name": "Cc", "value": "Copy Recipient <cc@example.com>"},
                {"name": "Subject", "value": "Test Email Subject"},
                {"name": "Message-ID", "value": "<testmessage@id.com>"}
            ],
            "parts": [
                {
                    "partId": "0",
                    "mimeType": "text/plain",
                    "body": {"size": 25, "data": base64.urlsafe_b64encode("Hello, this is plain text.".encode()).decode()}
                },
                {
                    "partId": "1",
                    "mimeType": "text/html",
                    "body": {"size": 45, "data": base64.urlsafe_b64encode("<html><body><p>Hello, this is HTML.</p></body></html>".encode()).decode()}
                }
            ]
        }
    }

    parsed = parse_email_data(sample_api_response)
    if parsed:
        print("Successfully parsed email data:")
        for key, value in parsed.items():
            if key == 'received_datetime':
                print(f"  {key}: {value.isoformat() if value else 'N/A'}")
            else:
                print(f"  {key}: {value}")
    else:
        print("Failed to parse email data.")

    # Test with minimal data
    minimal_response = {
        "id": "minimalId", "threadId": "minimalThread", "snippet": "Minimal snippet.",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "minimal@example.com"},
                {"name": "Subject", "value": "Minimal Subject"},
                {"name": "Date", "value": datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')} # RFC 2822
            ],
            "body": {"size": 10, "data": base64.urlsafe_b64encode("Minimal body".encode()).decode()}
        }
    }
    print("\n--- Parsing minimal email ---")
    parsed_minimal = parse_email_data(minimal_response)
    if parsed_minimal:
        print("Successfully parsed minimal email data:")
        for key, value in parsed_minimal.items():
            if key == 'received_datetime':
                print(f"  {key}: {value.isoformat() if value else 'N/A'}")
            else:
                print(f"  {key}: {value}")
