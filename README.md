# Mailman: Rule-Based Gmail Automation
---

Manage you gmail mails efficiently.

Mailman is a standalone Python script designed to help you manage your Gmail inbox more efficiently through customizable, rule-based automation. It integrates directly with the Gmail API to fetch emails, apply user-defined rules, and perform actions like marking emails as read/unread or moving them between mailboxes.

## Key features to be implemented include:

- OAuth authentication with Gmail API using Google's official Python client.
- Fetching and storing emails from Inbox into a relational database (e.g., SQLite3).
- A flexible rule engine defined via a JSON file for processing emails.
- Support for various conditions (From, Subject, Date Received, etc.) with predicates like "contains", "equals", "less than".
- Actions such as "mark as read/unread" and "move message".
- Emphasis on not using IMAP or Gmail's native search for rule processing.