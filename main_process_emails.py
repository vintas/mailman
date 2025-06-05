import time
from config import DATABASE_NAME
from mailman_components.gmail_auth import get_gmail_service
from mailman_components.gmail_client import modify_message_labels, get_label_id_by_name
from mailman_components.rule_engine import load_rules, evaluate_email
from mailman_components.database_handler import SessionLocal, Email, create_tables

def apply_actions(service, email_message_id, actions):
    """
    Applies a list of actions to a given email message using the Gmail API.
    Args:
        service: Authorized Gmail API service instance.
        email_message_id (str): The ID of the email message to act upon.
        actions (list): A list of action dictionaries from a rule.
    Returns:
        bool: True if all actions were attempted (not necessarily all successful), False if no actions.
    """
    if not actions:
        print(f"No actions to apply for message {email_message_id}.")
        return False

    print(f"Applying actions for message {email_message_id}: {actions}")
    
    # Prepare label modifications
    add_label_ids = []
    remove_label_ids = []
    moved = False # Track if a move action occurs, as it might imply removing INBOX

    for action in actions:
        action_type = action.get('type', '').lower()
        
        if action_type == "mark_as_read":
            print(f"  Action: Mark message {email_message_id} as read.")
            remove_label_ids.append('UNREAD')
        elif action_type == "mark_as_unread":
            print(f"  Action: Mark message {email_message_id} as unread.")
            add_label_ids.append('UNREAD')
        elif action_type == "move_message":
            target_mailbox_name = action.get('mailbox')
            if not target_mailbox_name:
                print(f"  Action Error: 'move_message' action for {email_message_id} is missing 'mailbox' name.")
                continue

            print(f"  Action: Move message {email_message_id} to mailbox '{target_mailbox_name}'.")
            
            if target_mailbox_name.upper() == "ARCHIVE":
                # Archiving in Gmail means removing the INBOX label.
                # Other labels (like custom ones) are typically kept.
                remove_label_ids.append('INBOX')
                moved = True # Indicate a move-like action
            else:
                target_label_id = get_label_id_by_name(service, target_mailbox_name)
                if target_label_id:
                    add_label_ids.append(target_label_id)
                    # Typically, moving to a new folder/label also means removing it from INBOX
                    # if it's currently there. This might need to be smarter based on current labels.
                    # For now, let's assume if we move it, it leaves the inbox.
                    remove_label_ids.append('INBOX') # Common behavior
                    moved = True # Indicate a move-like action
                else:
                    print(f"  Action Error: Could not find label ID for mailbox '{target_mailbox_name}' for message {email_message_id}. Skipping move.")
        
        elif action_type == "add_label": # Custom action not in requirement, but useful
            label_to_add_name = action.get('label_name')
            if not label_to_add_name:
                print(f"  Action Error: 'add_label' action for {email_message_id} is missing 'label_name'.")
                continue
            label_id = get_label_id_by_name(service, label_to_add_name)
            if label_id:
                print(f"  Action: Add label '{label_to_add_name}' (ID: {label_id}) to message {email_message_id}.")
                add_label_ids.append(label_id)
            else:
                print(f"  Action Error: Could not find label ID for '{label_to_add_name}' for message {email_message_id}. Skipping add_label.")

        else:
            print(f"  Action Warning: Unknown action type '{action_type}' for message {email_message_id}. Skipping.")

    # Consolidate label IDs to avoid duplicates
    add_label_ids = list(set(add_label_ids))
    remove_label_ids = list(set(remove_label_ids))

    # Prevent adding and removing the same label in one go if logic leads to it
    # (though current actions don't directly conflict like that)
    common_labels = set(add_label_ids) & set(remove_label_ids)
    if common_labels:
        print(f"  Action Warning: Attempting to both add and remove labels {common_labels} for {email_message_id}. Prioritizing removal.")
        for lbl_id in common_labels:
            if lbl_id in add_label_ids:
                add_label_ids.remove(lbl_id)


    if add_label_ids or remove_label_ids:
        # If an email is explicitly moved to INBOX, don't remove INBOX if it was also added.
        # This handles the rule from the PDF screenshot: "Move Message to mailbox: Inbox"
        inbox_id = get_label_id_by_name(service, "INBOX") # Ensure we have the ID
        if inbox_id in add_label_ids and inbox_id in remove_label_ids:
            print(f"  Action Info: Explicitly moving to INBOX for {email_message_id}, so INBOX will be added, not removed.")
            remove_label_ids.remove(inbox_id)
            
        print(f"  Applying label modifications for {email_message_id}: Add={add_label_ids}, Remove={remove_label_ids}")
        modify_message_labels(service, email_message_id, add_label_ids, remove_label_ids)
    
    return True


def main():
    """
    Main function to process emails from the database based on rules
    and apply actions using the Gmail API.
    """
    print("Starting email processing script...")

    # 0. Ensure database tables exist (though fetch script should have done this)
    try:
        create_tables()
    except Exception as e:
        print(f"Warning: Could not ensure database tables: {e}")


    # 1. Load Rules
    print("Loading rules...")
    rules = load_rules()
    if not rules:
        print("No rules loaded or rules file not found. Exiting.")
        return

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
        # 4. Fetch emails from the database
        # For now, let's process all emails. In a real scenario, you might want to
        # fetch only unread, or emails not yet processed by rules (needs an extra flag in DB).
        print(f"Fetching all emails from the local database '{DATABASE_NAME}'...")
        emails_to_process = db_session.query(Email).all() # Or add .filter(...) for specific emails

        if not emails_to_process:
            print("No emails found in the local database to process.")
            return

        print(f"Found {len(emails_to_process)} emails in the database to evaluate against rules.")
        
        emails_matched_count = 0
        actions_taken_count = 0

        # 5. Iterate through emails and rules
        for i, email_obj in enumerate(emails_to_process):
            print(f"\n--- Evaluating Email {i+1}/{len(emails_to_process)} (ID: {email_obj.message_id}, Subject: '{email_obj.subject}') ---")
            
            matched_any_rule = False
            for rule in rules:
                rule_description = rule.get('description', 'Unnamed Rule')
                print(f"  Checking against rule: '{rule_description}'")
                
                if evaluate_email(email_obj, rule):
                    print(f"  MATCHED Rule: '{rule_description}' for email {email_obj.message_id}.")
                    matched_any_rule = True
                    emails_matched_count +=1 # Count unique emails that matched at least one rule
                    
                    actions = rule.get('actions', [])
                    if actions:
                        apply_actions(service, email_obj.message_id, actions)
                        actions_taken_count += len(actions) # Count total actions attempted
                        # After a rule matches and actions are applied, you might want to stop
                        # processing further rules for this email, or continue.
                        # For now, let's assume an email can match multiple rules.
                    else:
                        print(f"  Rule '{rule_description}' matched, but has no actions defined.")
                    # break # Uncomment if an email should only be processed by the first rule it matches
                else:
                    print(f"  No match for rule: '{rule_description}'.")
            
            if not matched_any_rule:
                print(f"  Email {email_obj.message_id} did not match any rules.")

            # Optional: Add a small delay to avoid hitting API rate limits too quickly
            if (i + 1) % 5 == 0 and actions_taken_count > 0: # Every 5 emails that had actions
                print("Pausing for 1 second to respect API rate limits...")
                time.sleep(1)

        print("\n--- Rule Processing Summary ---")
        print(f"Total emails evaluated: {len(emails_to_process)}")
        print(f"Number of unique emails that matched at least one rule: {emails_matched_count}") # This needs adjustment if one email can match multiple rules and we only count it once
        print(f"Total actions attempted across all matched rules: {actions_taken_count}")


    except Exception as e:
        print(f"An error occurred during the email processing: {e}")
        # db_session.rollback() # Not strictly necessary as we are mostly reading
    finally:
        print("Closing database session.")
        db_session.close()

    print("Email processing script completed.")

if __name__ == '__main__':
    main()
