import json
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta # For month calculations
import re # For "contains" and "equals" on potentially complex strings
from email.utils import parseaddr

from config import RULES_FILE

class RuleConditionError(ValueError):
    """Custom exception for errors in rule conditions."""
    pass

def load_rules(rules_filepath=RULES_FILE):
    """
    Loads rules from a JSON file.
    Args:
        rules_filepath (str): Path to the JSON rules file.
    Returns:
        list: A list of rule dictionaries, or an empty list if an error occurs.
    """
    try:
        with open(rules_filepath, 'r') as f:
            rules = json.load(f)
        print(f"Successfully loaded {len(rules)} rules from {rules_filepath}")
        return rules
    except FileNotFoundError:
        print(f"Error: Rules file not found at {rules_filepath}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from {rules_filepath}: {e}")
        return []
    except Exception as e:
        print(f"An unexpected error occurred while loading rules: {e}")
        return []

def _normalize_string(text):
    """Helper to normalize strings for comparison (lowercase, strip whitespace)."""
    return str(text).lower().strip() if text is not None else ""

def _check_string_condition(email_field_value_single_string, predicate, rule_value):
    """
    Checks a string-based condition for a single string.
    Args:
        email_field_value_single_string (str): The single string value from the email field (or one item from a list).
        predicate (str): The comparison predicate (e.g., "contains", "equals").
        rule_value (str): The value from the rule to compare against.
    Returns:
        bool: True if the condition is met, False otherwise.
    """
    norm_email_value = _normalize_string(email_field_value_single_string)
    norm_rule_value = _normalize_string(rule_value)

    if predicate == "contains":
        return norm_rule_value in norm_email_value
    elif predicate == "does_not_contain":
        return norm_rule_value not in norm_email_value
    elif predicate == "equals":
        return norm_email_value == norm_rule_value
    elif predicate == "does_not_equal":
        return norm_email_value != norm_rule_value
    else:
        raise RuleConditionError(f"Unsupported string predicate: {predicate}")

def _check_date_condition(email_datetime_value, predicate, rule_value_str):
    """
    Checks a date-based condition.
    Args:
        email_datetime_value (datetime): The datetime value from the email.
        predicate (str): The comparison predicate (e.g., "less_than_days", "greater_than_months").
        rule_value_str (str): The value from the rule (e.g., "2" for days, "6" for months).
    Returns:
        bool: True if the condition is met, False otherwise.
    Raises:
        RuleConditionError: If predicate or rule_value is invalid.
    """
    if not isinstance(email_datetime_value, datetime):
        # Try to parse if it's a string, though it should be datetime from DB
        if isinstance(email_datetime_value, str):
            try:
                from dateutil import parser as date_parser # Local import to avoid circularity if not always needed
                email_datetime_value = date_parser.isoparse(email_datetime_value)
            except ValueError:
                 raise RuleConditionError(f"Email date field is not a valid datetime object or ISO string: {email_datetime_value}")
        else:
            raise RuleConditionError(f"Email date field is not a datetime object: {type(email_datetime_value)}")

    try:
        # Ensure email_datetime_value is offset-aware if comparing with offset-aware now()
        # or make both naive. For simplicity, let's assume UTC for rule comparison.
        # If email_datetime_value is naive, assume it's UTC. If aware, convert to UTC.
        if email_datetime_value.tzinfo is not None and email_datetime_value.tzinfo.utcoffset(email_datetime_value) is not None:
            email_datetime_value = email_datetime_value.astimezone(timezone.utc)
        else: # Naive, assume UTC
            email_datetime_value = email_datetime_value.replace(tzinfo=timezone.utc)

        now_utc = datetime.now(timezone.utc)

        value = int(rule_value_str)
    except ValueError:
        raise RuleConditionError(f"Invalid numeric value for date condition: {rule_value_str}")

    if predicate == "less_than_days": # e.g., "less than 2 days old"
        # Email date must be MORE RECENT than (NOW - N days)
        return email_datetime_value > (now_utc - timedelta(days=value))
    elif predicate == "greater_than_days": # e.g., "greater than 2 days old"
        # Email date must be OLDER than (NOW - N days)
        return email_datetime_value < (now_utc - timedelta(days=value))
    elif predicate == "less_than_months": # e.g., "less than 2 months old"
        return email_datetime_value > (now_utc - relativedelta(months=value))
    elif predicate == "greater_than_months": # e.g., "greater than 2 months old"
        return email_datetime_value < (now_utc - relativedelta(months=value))
    else:
        raise RuleConditionError(f"Unsupported date predicate: {predicate}")

def evaluate_email(email_db_object, rule):
    """
    Evaluates if an email (from database object) matches a given rule.
    Args:
        email_db_object (Email): The SQLAlchemy Email object from the database.
        rule (dict): A single rule dictionary.
    Returns:
        bool: True if the email matches the rule, False otherwise.
    """
    conditions = rule.get('conditions', [])
    if not conditions:
        print(f"Warning: Rule '{rule.get('description', 'N/A')}' has no conditions. Defaulting to False.")
        return False # A rule with no conditions probably shouldn't match anything by default

    conditions_predicate = rule.get('conditions_predicate', 'all').lower() # 'all' or 'any'

    condition_results = []

    for condition in conditions:
        field_name_from_rule = condition.get('field')
        predicate = condition.get('predicate')
        rule_value = condition.get('value')

        if not all([field_name_from_rule, predicate, rule_value is not None]): # rule_value can be "" or 0
            print(f"Warning: Skipping invalid condition in rule '{rule.get('description', 'N/A')}': {condition}")
            condition_results.append(False) # Treat malformed condition as not met
            continue
        
        db_field_name = field_name_from_rule
        # Handle aliases for field names
        if field_name_from_rule.lower() == "message": # As per requirement
            db_field_name = "body_plain"
        elif field_name_from_rule.lower() == "from":
             db_field_name = "from_address"
        elif field_name_from_rule.lower() in ["date received", "received date/time"]:
            db_field_name = "received_datetime"
        elif field_name_from_rule.lower() == "to":
            db_field_name = "to_addresses"
        elif field_name_from_rule.lower() == "cc":
            db_field_name = "cc_addresses"
        elif field_name_from_rule.lower() == "bcc":
            db_field_name = "bcc_addresses"


        if not hasattr(email_db_object, db_field_name):
            print(f"Warning: Field '{db_field_name}' (from rule field '{field_name_from_rule}') not found in email object. Condition failed.")
            condition_results.append(False)
            continue
            
        email_field_value_original = getattr(email_db_object, db_field_name)
        condition_met = False
        value_to_check_against_rule = email_field_value_original # Default

        try:
            if db_field_name == "from_address":
                if email_field_value_original and isinstance(email_field_value_original, str):
                    name, addr = parseaddr(email_field_value_original)
                    value_to_check_against_rule = addr if addr else email_field_value_original # Use extracted email, or original if parse fails badly
                # If not a string or empty, it will be handled by _check_string_condition as an empty string
                condition_met = _check_string_condition(value_to_check_against_rule, predicate, rule_value)

            # Fields that are single strings or need direct string comparison (excluding from_address now)
            elif db_field_name in ["subject", "body_plain"]:
                condition_met = _check_string_condition(email_field_value_original, predicate, rule_value)
            
            # Fields that are JSON strings representing lists of addresses
            elif db_field_name in ["to_addresses", "cc_addresses", "bcc_addresses"]:
                if not isinstance(email_field_value_original, str): # Should be a JSON string from DB
                    print(f"Warning: Field '{db_field_name}' is not a string as expected. Value: {email_field_value_original}. Condition failed.")
                    condition_met = False
                else:
                    try:
                        address_list = json.loads(email_field_value_original)
                        if not isinstance(address_list, list):
                            print(f"Warning: Parsed JSON for '{db_field_name}' is not a list. Value: {address_list}. Condition failed.")
                            condition_met = False
                        else:
                            parsed_address_list_emails_only = []
                            for item in address_list:
                                if isinstance(item, str):
                                    name, addr = parseaddr(item)
                                    parsed_address_list_emails_only.append(addr if addr else item)
                                else:
                                    parsed_address_list_emails_only.append(str(item)) # fallback

                            if predicate in ["equals", "contains"]:
                                condition_met = any(_check_string_condition(addr_email_part, predicate, rule_value) for addr_email_part in parsed_address_list_emails_only)
                            elif predicate in ["does_not_equal", "does_not_contain"]:
                                condition_met = all(_check_string_condition(addr_email_part, predicate, rule_value) for addr_email_part in parsed_address_list_emails_only)
                            else:
                                raise RuleConditionError(f"Unsupported predicate '{predicate}' for address list field '{db_field_name}'.")
                    except json.JSONDecodeError:
                        print(f"Warning: Could not parse JSON for address list field '{db_field_name}'. Value: {email_field_value_original}. Condition failed.")
                        condition_met = False
            
            # Date fields
            elif db_field_name == "received_datetime":
                condition_met = _check_date_condition(email_field_value_original, predicate, rule_value)
            else:
                print(f"Warning: Unhandled field type for condition processing: {db_field_name}. Value: '{email_field_value_original}'. Condition failed.")
                condition_met = False
            
            condition_results.append(condition_met)

        except RuleConditionError as e:
            print(f"Error evaluating condition for rule '{rule.get('description', 'N/A')}' on email {email_db_object.message_id}: {e}. Condition failed.")
            condition_results.append(False)
        except Exception as e_gen:
            print(f"Unexpected error during condition evaluation for rule '{rule.get('description', 'N/A')}' on email {email_db_object.message_id}: {e_gen}. Condition failed.")
            condition_results.append(False)


    if not condition_results: # Should not happen if conditions list is not empty and valid
        return False

    if conditions_predicate == 'all':
        return all(condition_results)
    elif conditions_predicate == 'any':
        return any(condition_results)
    else:
        print(f"Warning: Unknown conditions_predicate '{conditions_predicate}' in rule '{rule.get('description', 'N/A')}'. Defaulting to 'all'.")
        return all(condition_results)


if __name__ == '__main__':
    print("Testing Rule Engine...")

    # Create a dummy email object (mimicking SQLAlchemy object)
    class DummyEmail:
        def __init__(self, message_id, from_address, subject, body_plain, received_datetime_str, 
                     to_addresses_json_str='[]', cc_addresses_json_str='[]', bcc_addresses_json_str='[]'):
            self.message_id = message_id
            self.from_address = from_address
            self.subject = subject
            self.body_plain = body_plain
            try:
                self.received_datetime = datetime.fromisoformat(received_datetime_str)
            except ValueError:
                # Fallback for simpler date strings if needed for testing
                from dateutil import parser as date_parser
                self.received_datetime = date_parser.parse(received_datetime_str)
            self.to_addresses = to_addresses_json_str
            self.cc_addresses = cc_addresses_json_str
            self.bcc_addresses = bcc_addresses_json_str


    email1_date = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    email1 = DummyEmail(
        message_id="test001",
        from_address="HR Team <hr@tenmiles.com>",
        subject="Your Interview Schedule",
        body_plain="Details about your upcoming interview.",
        received_datetime_str=email1_date,
        to_addresses_json_str=json.dumps(["Candidate <candidate@example.com>", "manager@tenmiles.com"])
    )

    email_from_only_addr = DummyEmail(
        message_id="test_from_only",
        from_address="my_name@gmail.com", # No name part
        subject="Simple From",
        body_plain="Test",
        received_datetime_str=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    )

    email2_date = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    email2 = DummyEmail(
        message_id="test002",
        from_address="newsletter@example.com",
        subject="Weekly Updates",
        body_plain="Here are your weekly news and updates.",
        received_datetime_str=email2_date,
        to_addresses_json_str=json.dumps(["subscriber1@example.net", "subscriber2@example.org"])
    )
    
    email3_date = (datetime.now(timezone.utc) - relativedelta(months=7)).isoformat()
    email3 = DummyEmail(
        message_id="test003",
        from_address="old_updates@example.com",
        subject="Project Update Archive",
        body_plain="This is an old project update.",
        received_datetime_str=email3_date
    )
    
    email4_to_test_json = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    email4 = DummyEmail(
        message_id="test004_to_specific",
        from_address="sender@example.com",
        subject="To specific user",
        body_plain="This email is for a specific user in the TO field.",
        received_datetime_str=email4_to_test_json,
        to_addresses_json_str=json.dumps(["alpha@example.com", "beta@example.com", "gamma@example.com"])
    )


    test_rules = load_rules() 

    if not test_rules:
        print("No rules loaded from file. Using a dummy rule for TO field testing.")
        test_rules = [
            {
                "description": "Rule for specific TO address (equals)",
                "conditions_predicate": "all",
                "conditions": [
                    {"field": "to_addresses", "predicate": "equals", "value": "beta@example.com"}
                ],
                "actions": [{"type": "mark_as_read"}]
            },
            {
                "description": "Rule for specific TO address (contains domain)",
                "conditions_predicate": "all",
                "conditions": [
                    {"field": "to_addresses", "predicate": "contains", "value": "example.com"}
                ],
                "actions": [{"type": "mark_as_read"}]
            },
            {
                "description": "Rule for TO address NOT equals specific",
                "conditions_predicate": "all",
                "conditions": [
                    {"field": "to_addresses", "predicate": "does_not_equal", "value": "delta@example.com"} # delta is not in email4's TO list
                ],
                "actions": [{"type": "mark_as_read"}]
            },
             {
                "description": "Rule for TO address NOT equals specific (where one matches)",
                "conditions_predicate": "all",
                "conditions": [
                    {"field": "to_addresses", "predicate": "does_not_equal", "value": "beta@example.com"} # beta IS in email4's TO list
                ],
                "actions": [{"type": "mark_as_read"}]
            },
            {
                "description": "FROM equals specific email (with name in DB)",
                "conditions_predicate": "all",
                "conditions": [{"field": "from_address", "predicate": "equals", "value": "hr@tenmiles.com"}],
                "actions": []
            },
            {
                "description": "FROM contains domain (with name in DB)",
                "conditions_predicate": "all",
                "conditions": [{"field": "from_address", "predicate": "contains", "value": "tenmiles.com"}],
                "actions": []
            },
            {
                "description": "FROM equals specific email (no name in DB)",
                "conditions_predicate": "all",
                "conditions": [{"field": "from_address", "predicate": "equals", "value": "my_name@gmail.com"}],
                "actions": []
            },
            {
                "description": "FROM (alias) equals specific email (with name in DB)",
                "conditions_predicate": "all",
                "conditions": [{"field": "From", "predicate": "equals", "value": "hr@tenmiles.com"}],
                "actions": []
            }
        ]
        # Append existing rules if any
        # test_rules.extend(load_rules())

    if not test_rules:
        print("No rules defined (neither from file nor dummy). Cannot run full tests.")
    else:
        print(f"\n--- Evaluating Email 1 (from tenmiles.com, TO: ['candidate@example.com', 'manager@tenmiles.com']) ---")
        for rule in test_rules:
            if rule.get('description') != "Test Rule matching screenshot": continue
            print(f"Rule: {rule.get('description')}")
            matches = evaluate_email(email1, rule)
            print(f"  Matches: {matches}")
            if rule.get('description') == "Test Rule matching screenshot":
                 # This rule might not match if 'to_addresses' was part of its conditions and not handled before
                pass # Re-evaluate assertion based on rule


        print(f"\n--- Evaluating Email 4 (TO: ['alpha@example.com', 'beta@example.com', 'gamma@example.com']) for specific TO rules ---")
        rule_to_beta_equals = next((r for r in test_rules if r['description'] == "Rule for specific TO address (equals)"), None)
        if rule_to_beta_equals:
            print(f"Rule: {rule_to_beta_equals.get('description')}")
            matches = evaluate_email(email4, rule_to_beta_equals)
            print(f"  Matches (should be True): {matches}")
            assert matches is True

        rule_to_contains_domain = next((r for r in test_rules if r['description'] == "Rule for specific TO address (contains domain)"), None)
        if rule_to_contains_domain:
            print(f"Rule: {rule_to_contains_domain.get('description')}")
            matches = evaluate_email(email4, rule_to_contains_domain)
            print(f"  Matches (should be True as all contain example.com): {matches}")
            assert matches is True
            
        rule_to_not_equals_delta = next((r for r in test_rules if r['description'] == "Rule for TO address NOT equals specific"), None)
        if rule_to_not_equals_delta:
            print(f"Rule: {rule_to_not_equals_delta.get('description')}")
            matches = evaluate_email(email4, rule_to_not_equals_delta)
            print(f"  Matches (delta@example.com is not in the list, so all 'do not equal' it - should be True): {matches}")
            assert matches is True

        rule_to_not_equals_beta = next((r for r in test_rules if r['description'] == "Rule for TO address NOT equals specific (where one matches)"), None)
        if rule_to_not_equals_beta:
            print(f"Rule: {rule_to_not_equals_beta.get('description')}")
            matches = evaluate_email(email4, rule_to_not_equals_beta)
            print(f"  Matches (beta@example.com IS in the list, so NOT all 'do not equal' it - should be False): {matches}")
            assert matches is False

    effective_rules = test_rules

    print(f"\n--- Evaluating Email 1 (From: 'HR Team <hr@tenmiles.com>') ---")
    rule_from_equals_hr = next((r for r in effective_rules if r['description'] == "FROM equals specific email (with name in DB)"), None)
    if rule_from_equals_hr:
        matches = evaluate_email(email1, rule_from_equals_hr)
        print(f"Rule: {rule_from_equals_hr['description']} -> Matches: {matches} (Expected: True)")
        assert matches is True

    rule_from_contains_domain = next((r for r in effective_rules if r['description'] == "FROM contains domain (with name in DB)"), None)
    if rule_from_contains_domain:
        matches = evaluate_email(email1, rule_from_contains_domain)
        print(f"Rule: {rule_from_contains_domain['description']} -> Matches: {matches} (Expected: True)")
        assert matches is True
    
    rule_from_alias_equals_hr = next((r for r in effective_rules if r['description'] == "FROM (alias) equals specific email (with name in DB)"), None)
    if rule_from_alias_equals_hr:
        matches = evaluate_email(email1, rule_from_alias_equals_hr)
        print(f"Rule: {rule_from_alias_equals_hr['description']} -> Matches: {matches} (Expected: True)")
        assert matches is True


    print(f"\n--- Evaluating Email (From: 'my_name@gmail.com') ---")
    rule_from_equals_myname = next((r for r in effective_rules if r['description'] == "FROM equals specific email (no name in DB)"), None)
    if rule_from_equals_myname:
        matches = evaluate_email(email_from_only_addr, rule_from_equals_myname)
        print(f"Rule: {rule_from_equals_myname['description']} -> Matches: {matches} (Expected: True)")
        assert matches is True

    # Also test To/Cc/Bcc address parsing
    print(f"\n--- Evaluating Email 1 (To: ['Candidate <candidate@example.com>', 'manager@tenmiles.com']) for TO field ---")
    to_field_test_rule_equals = {
        "description": "TO equals specific email (with name in DB list item)",
        "conditions_predicate": "all",
        "conditions": [{"field": "To", "predicate": "equals", "value": "candidate@example.com"}],
        "actions": []
    }
    matches_to_equals = evaluate_email(email1, to_field_test_rule_equals)
    print(f"Rule: {to_field_test_rule_equals['description']} -> Matches: {matches_to_equals} (Expected: True)")
    assert matches_to_equals is True
    
    to_field_test_rule_contains_domain = {
        "description": "TO contains domain (from name in DB list item)",
        "conditions_predicate": "all",
        "conditions": [{"field": "To", "predicate": "contains", "value": "tenmiles.com"}], # manager@tenmiles.com
        "actions": []
    }
    matches_to_contains = evaluate_email(email1, to_field_test_rule_contains_domain)
    print(f"Rule: {to_field_test_rule_contains_domain['description']} -> Matches: {matches_to_contains} (Expected: True)")
    assert matches_to_contains is True


    print("Rule engine tests completed.")
