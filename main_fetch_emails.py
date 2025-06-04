import time
from config import DATABASE_NAME # For informational print
from mailman_components.gmail_auth import get_gmail_service
from mailman_components.gmail_client import list_message_ids, get_message_detail
from mailman_components.email_parser import parse_email_data
from mailman_components.database_handler import SessionLocal, create_tables, store_email, Email

def main():
    """
    Main function to fetch emails from Gmail and store them in the database.
    """
    print("Starting email fetching process...")

    # 1. Initialize Database (create tables if they don't exist)
    try:
        create_tables()
        print(f"Database tables ensured in '{DATABASE_NAME}'.")
    except Exception as e:
        print(f"Error initializing database tables: {e}")
        return # Critical error, cannot proceed

    # 2. Authenticate and get Gmail API Service
    print("Authenticating with Gmail...")
    service = get_gmail_service()
    if not service:
        print("Failed to authenticate with Gmail. Exiting.")
        return

    print("Successfully authenticated with Gmail.")

    # 3. Get a database session
    db_session = SessionLocal()

    try:
        # 4. Fetch list of message IDs
        # For now, let's fetch recent emails from the inbox.
        # You can customize the query and max_results.
        # query = 'in:inbox is:unread' # Example: only unread from inbox
        query = 'in:inbox' # All from inbox
        num_emails_to_fetch = 25 # Fetch a manageable number for testing
        
        print(f"Fetching up to {num_emails_to_fetch} message IDs from Gmail with query: '{query}'...")
        message_ids = list_message_ids(service, query=query, max_results=num_emails_to_fetch)

        if not message_ids:
            print("No new messages found matching the criteria.")
            return

        print(f"Found {len(message_ids)} messages to process.")
        
        processed_count = 0
        newly_stored_count = 0
        already_exists_count = 0

        for i, msg_id in enumerate(message_ids):
            print(f"\nProcessing message {i+1}/{len(message_ids)}: ID {msg_id}")

            # Check if email already exists in DB to avoid re-fetching and re-parsing if not needed
            # This is a simple check; more sophisticated logic might involve checking update timestamps.
            existing_email = db_session.query(Email).filter_by(message_id=msg_id).first()
            if existing_email:
                print(f"Message ID {msg_id} already exists in the database. Skipping fetch and parse.")
                already_exists_count += 1
                processed_count +=1
                continue # Skip to the next message

            # 5. Fetch full message detail
            print(f"Fetching details for message ID {msg_id}...")
            message_detail_json = get_message_detail(service, msg_id=msg_id)

            if not message_detail_json:
                print(f"Could not retrieve details for message ID {msg_id}. Skipping.")
                continue

            # 6. Parse the message detail
            print(f"Parsing details for message ID {msg_id}...")
            parsed_email_dict = parse_email_data(message_detail_json)

            if not parsed_email_dict:
                print(f"Could not parse email data for message ID {msg_id}. Skipping.")
                continue
            
            # Ensure received_datetime is a datetime object (parser should handle this)
            # if isinstance(parsed_email_dict.get('received_datetime'), str):
            #     from dateutil import parser as date_parser
            #     try:
            #         parsed_email_dict['received_datetime'] = date_parser.isoparse(parsed_email_dict['received_datetime'])
            #     except ValueError:
            #         print(f"Warning: Could not parse date string for {msg_id}, using current UTC time.")
            #         from datetime import datetime, timezone
            #         parsed_email_dict['received_datetime'] = datetime.now(timezone.utc)


            # 7. Store the parsed email in the database
            print(f"Storing parsed email for message ID {msg_id}...")
            stored_email_obj = store_email(db_session, parsed_email_dict)
            if stored_email_obj:
                newly_stored_count +=1
            
            processed_count += 1
            
            # Optional: Add a small delay to avoid hitting API rate limits too quickly if fetching many emails
            if (i + 1) % 10 == 0: # Every 10 emails
                print("Pausing for 1 second to respect API rate limits...")
                time.sleep(1)
        
        print("\n--- Fetching Summary ---")
        print(f"Total messages checked: {len(message_ids)}")
        print(f"Messages processed (fetched/parsed/stored or skipped if existing): {processed_count}")
        print(f"Messages newly stored in database: {newly_stored_count}")
        print(f"Messages already existing in database: {already_exists_count}")


    except Exception as e:
        print(f"An error occurred during the email fetching process: {e}")
        db_session.rollback() # Rollback in case of error during a transaction
    finally:
        # 8. Close the database session
        print("Closing database session.")
        db_session.close()

    print("Email fetching process completed.")

if __name__ == '__main__':
    main()
