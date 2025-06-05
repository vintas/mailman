# tests/test_rule_engine.py
import unittest
import json
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
import os
import sys

# Add the project root to sys.path to allow importing mailman_components
# This assumes 'tests' is a subdirectory of the project root 'mailman'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mailman_components.rule_engine import (
    _check_string_condition,
    _check_date_condition,
    evaluate_email,
    RuleConditionError
)

# DummyEmail class to mock SQLAlchemy Email objects for testing
class DummyEmail:
    def __init__(self, message_id="dummy_id", from_address="", subject="", body_plain="",
                    received_datetime=None, to_addresses_json_str='[]',
                    cc_addresses_json_str='[]', bcc_addresses_json_str='[]'):
        self.message_id = message_id
        self.from_address = from_address
        self.subject = subject
        self.body_plain = body_plain
        self.received_datetime = received_datetime if received_datetime else datetime.now(timezone.utc)
        self.to_addresses = to_addresses_json_str
        self.cc_addresses = cc_addresses_json_str
        self.bcc_addresses = bcc_addresses_json_str

    def __getattr__(self, name):
        # Fallback for any other attributes that might be accessed
        # print(f"Warning: DummyEmail accessed undefined attribute '{name}'")
        return None


class TestRuleEngine(unittest.TestCase):

    def setUp(self):
        # Common setup for tests, if any
        self.now = datetime.now(timezone.utc)
        self.email1 = DummyEmail(
            message_id="email1",
            from_address="sender@tenmiles.com",
            subject="Regarding your Interview",
            body_plain="This is an important email about your interview.",
            received_datetime=(self.now - timedelta(days=1)) # 1 day old
        )
        self.email2 = DummyEmail(
            message_id="email2",
            from_address="newsletter@example.org",
            subject="Weekly News",
            body_plain="Some news for you.",
            received_datetime=(self.now - timedelta(days=10)), # 10 days old
            to_addresses_json_str=json.dumps(["user1@test.com", "user2@example.com"])
        )
        self.email3 = DummyEmail(
            message_id="email3",
            from_address="urgent@example.com",
            subject="Action Required: Update",
            body_plain="Please update your details.",
            received_datetime=(self.now - relativedelta(months=7)) # 7 months old
        )

    # --- Tests for _check_string_condition ---
    def test_string_contains(self):
        self.assertTrue(_check_string_condition("Hello World", "contains", "World"))
        self.assertTrue(_check_string_condition("Hello World", "contains", "hello")) # case-insensitive
        self.assertFalse(_check_string_condition("Hello World", "contains", "Python"))

    def test_string_does_not_contain(self):
        self.assertTrue(_check_string_condition("Hello World", "does_not_contain", "Python"))
        self.assertFalse(_check_string_condition("Hello World", "does_not_contain", "World"))

    def test_string_equals(self):
        self.assertTrue(_check_string_condition("Hello World", "equals", "hello world"))
        self.assertTrue(_check_string_condition("  Hello World  ", "equals", "hello world")) # whitespace
        self.assertFalse(_check_string_condition("Hello World", "equals", "HelloWorld"))

    def test_string_does_not_equal(self):
        self.assertTrue(_check_string_condition("Hello World", "does_not_equal", "HelloWorld"))
        self.assertFalse(_check_string_condition("Hello World", "does_not_equal", "hello world"))

    def test_string_invalid_predicate(self):
        with self.assertRaises(RuleConditionError):
            _check_string_condition("Hello", "invalid_predicate", "H")

    # --- Tests for _check_date_condition ---
    def test_date_less_than_days(self):
        one_day_ago = self.now - timedelta(days=1)
        self.assertTrue(_check_date_condition(one_day_ago, "less_than_days", "2")) # 1 day ago < 2 days old
        self.assertFalse(_check_date_condition(one_day_ago, "less_than_days", "1"))# 1 day ago is not < 1 day old (it's exactly 1 day old)
        self.assertFalse(_check_date_condition(one_day_ago, "less_than_days", "0"))

    def test_date_greater_than_days(self):
        three_days_ago = self.now - timedelta(days=3)
        self.assertTrue(_check_date_condition(three_days_ago, "greater_than_days", "2")) # 3 days ago > 2 days old
        self.assertFalse(_check_date_condition(three_days_ago, "greater_than_days", "3"))

    def test_date_less_than_months(self):
        one_month_ago = self.now - relativedelta(months=1)
        self.assertTrue(_check_date_condition(one_month_ago, "less_than_months", "2"))
        self.assertFalse(_check_date_condition(one_month_ago, "less_than_months", "1"))

    def test_date_greater_than_months(self):
        three_months_ago = self.now - relativedelta(months=3)
        self.assertTrue(_check_date_condition(three_months_ago, "greater_than_months", "2"))
        self.assertFalse(_check_date_condition(three_months_ago, "greater_than_months", "3"))

    def test_date_invalid_predicate(self):
        with self.assertRaises(RuleConditionError):
            _check_date_condition(self.now, "invalid_date_predicate", "1")
    
    def test_date_invalid_value(self):
        with self.assertRaises(RuleConditionError):
            _check_date_condition(self.now, "less_than_days", "abc")

    # --- Tests for evaluate_email ---
    def test_evaluate_email_all_conditions_match(self):
        rule = {
            "description": "Test ALL match",
            "conditions_predicate": "all",
            "conditions": [
                {"field": "from_address", "predicate": "contains", "value": "tenmiles.com"},
                {"field": "subject", "predicate": "contains", "value": "Interview"},
                {"field": "received_datetime", "predicate": "less_than_days", "value": "2"}
            ]
        }
        self.assertTrue(evaluate_email(self.email1, rule))

    def test_evaluate_email_all_conditions_one_fails(self):
        rule = {
            "description": "Test ALL one fail",
            "conditions_predicate": "all",
            "conditions": [
                {"field": "from_address", "predicate": "contains", "value": "tenmiles.com"},
                {"field": "subject", "predicate": "contains", "value": "Python Job"}, # This will fail
                {"field": "received_datetime", "predicate": "less_than_days", "value": "2"}
            ]
        }
        self.assertFalse(evaluate_email(self.email1, rule))

    def test_evaluate_email_any_conditions_one_matches(self):
        rule = {
            "description": "Test ANY one match",
            "conditions_predicate": "any",
            "conditions": [
                {"field": "from_address", "predicate": "equals", "value": "nonexistent@example.com"},
                {"field": "subject", "predicate": "contains", "value": "Interview"}, # This will match
                {"field": "received_datetime", "predicate": "greater_than_days", "value": "5"}
            ]
        }
        self.assertTrue(evaluate_email(self.email1, rule))

    def test_evaluate_email_any_conditions_none_match(self):
        rule = {
            "description": "Test ANY none match",
            "conditions_predicate": "any",
            "conditions": [
                {"field": "from_address", "predicate": "equals", "value": "nonexistent@example.com"},
                {"field": "subject", "predicate": "contains", "value": "Python Job"},
                {"field": "received_datetime", "predicate": "greater_than_days", "value": "100"} # email1 is 1 day old
            ]
        }
        self.assertFalse(evaluate_email(self.email1, rule))

    def test_evaluate_email_to_addresses_equals_match(self):
        rule = {
            "description": "TO field equals match",
            "conditions_predicate": "all",
            "conditions": [
                {"field": "to_addresses", "predicate": "equals", "value": "user2@example.com"}
            ]
        }
        self.assertTrue(evaluate_email(self.email2, rule))

    def test_evaluate_email_to_addresses_contains_match(self):
        rule = {
            "description": "TO field contains match",
            "conditions_predicate": "all",
            "conditions": [
                {"field": "to_addresses", "predicate": "contains", "value": "user1"}
            ]
        }
        self.assertTrue(evaluate_email(self.email2, rule))
        
    def test_evaluate_email_to_addresses_does_not_equal_true(self):
        # True because ALL items in email2's to_addresses are not "non_existent_user@example.com"
        rule = {
            "description": "TO field does_not_equal (non-existent value)",
            "conditions_predicate": "all",
            "conditions": [
                {"field": "to_addresses", "predicate": "does_not_equal", "value": "non_existent_user@example.com"}
            ]
        }
        self.assertTrue(evaluate_email(self.email2, rule))

    def test_evaluate_email_to_addresses_does_not_equal_false(self):
        # False because "user1@test.com" IS in email2's to_addresses, so not ALL items "do_not_equal" it.
        rule = {
            "description": "TO field does_not_equal (existing value)",
            "conditions_predicate": "all",
            "conditions": [
                {"field": "to_addresses", "predicate": "does_not_equal", "value": "user1@test.com"}
            ]
        }
        self.assertFalse(evaluate_email(self.email2, rule))


    def test_evaluate_email_message_field_alias(self): # Testing "Message" alias for "body_plain"
        rule = {
            "description": "Test Message field alias",
            "conditions_predicate": "all",
            "conditions": [
                {"field": "Message", "predicate": "contains", "value": "important email"}
            ]
        }
        self.assertTrue(evaluate_email(self.email1, rule))

    def test_evaluate_email_no_conditions(self):
        rule = {"description": "No conditions rule", "conditions_predicate": "all", "conditions": []}
        self.assertFalse(evaluate_email(self.email1, rule)) # Rule with no conditions should not match

    def test_evaluate_email_invalid_field_in_rule(self):
        rule = {
            "description": "Invalid field in rule",
            "conditions_predicate": "all",
            "conditions": [
                {"field": "non_existent_field", "predicate": "contains", "value": "test"}
            ]
        }
        # The current implementation prints a warning and treats the condition as False.
        # So, if this is the only condition, the rule should evaluate to False.
        self.assertFalse(evaluate_email(self.email1, rule))

    def test_evaluate_email_complex_rule_assignment_example(self):
        # This rule matches the assignment PDF screenshot example
        rule = {
            "description": "Assignment PDF Screenshot Rule",
            "conditions_predicate": "all",
            "conditions": [
                {"field": "from_address", "predicate": "contains", "value": "tenmiles.com"},
                {"field": "subject", "predicate": "contains", "value": "Interview"},
                {"field": "received_datetime", "predicate": "less_than_days", "value": "2"}
            ]
        }
        # email1 is from tenmiles.com, subject contains Interview, and is 1 day old
        self.assertTrue(evaluate_email(self.email1, rule))
        # email2 should not match (wrong sender, subject, older than 2 days)
        self.assertFalse(evaluate_email(self.email2, rule))


if __name__ == '__main__':
    unittest.main()
