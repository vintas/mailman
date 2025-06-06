# Mailman: Gmail Automation Script
---

Manage you gmail mails efficiently.

Mailman is a standalone Python script designed to help you manage your Gmail inbox more efficiently through customizable, rule-based automation. It integrates directly with the Gmail API to fetch emails, apply user-defined rules, and perform actions like marking emails as read/unread or moving them between mailboxes/labels.

## Video Presentation & Demonstration

[Mailman Video](https://youtu.be/0BMe27vJ_AY)

## Key features:

* **Gmail API Integration:** Securely authenticates with Gmail using OAuth 2.0.

* **Email Fetching:** Retrieves emails from the user's Inbox.

* **Local Storage:** Stores email details (metadata and content) in a local SQLite database.

* **Rule-Based Processing:**

  * Processes emails based on rules defined in a `rules.json` file.

  * Rules consist of conditions (field, predicate, value) and actions.

  * Supports "all" or "any" predicates for a set of conditions within a rule.

  * **Supported Fields for Conditions:** From, Subject, Message (body), Received Date/Time.

  * **Supported String Predicates:** Contains, Does not Contain, Equals, Does not equal.

  * **Supported Date Predicates:** Less than (days/months), Greater than (days/months).

* **Email Actions:**

  * Mark as read / Mark as unread.

  * Move Message (to specified mailboxes/labels, including Archive and Inbox).

* **Standalone Scripts:**

  * `main_fetch_emails.py`: Fetches emails from Gmail and stores them in the database.

  * `main_process_emails.py`: Processes emails from the database based on rules and applies actions via Gmail API.

## Project Structure

```
mailman/
│
├── main_fetch_emails.py        # Main script to run email fetching and storing
├── main_process_emails.py      # Main script to run email processing based on rules
│
├── mailman_components/         # Core logic modules
│   ├── __init__.py
│   ├── gmail_auth.py           # Gmail API authentication
│   ├── gmail_client.py         # Gmail API interaction (fetch, modify)
│   ├── database_handler.py     # Database schema and operations (SQLite)
│   ├── rule_engine.py          # Rule parsing and evaluation logic
│   └── email_parser.py         # Parsing raw email data from Gmail API
│
├── rules.json                  # User-configurable rules for email processing
├── config.py                   # Configuration constants (paths, API scopes)
├── requirements.txt            # Python package dependencies
├── README.md                   # This file
│
├── credentials/                # Stores OAuth credentials (GITIGNORED - DO NOT COMMIT token.json)
│   └── client_secret.json      # Google API client secret file (user-provided)
│   └── token.json              # Generated token after successful OAuth (GITIGNORED)
│
├── emails.db                   # SQLite database file (GITIGNORED - will be created on run)
│
└── tests/                      # Optional: Unit and/or integration tests
    ├── __init__.py
    └── ...

```

## Getting Started

Follow these steps to set up and run the Mailman script.

### Prerequisites

* Python 3.8+
* A Google Cloud Project with the Gmail API enabled.
* OAuth 2.0 Client ID credentials ( `client_secret.json` ) downloaded from your Google Cloud Console.

### Installation

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/vintas/mailman.git
    cd mailman
    ```

2. **Set up Google Cloud Project & Credentials:**

   * Go to the [Google Cloud Console](https://console.cloud.google.com/).

   * Create a new project (or select an existing one).

   * Enable the **Gmail API** for your project. (Search for "Gmail API" in the API Library).

   * Create OAuth 2.0 credentials:

     * Go to "APIs & Services" > "Credentials".

     * Click "+ CREATE CREDENTIALS" > "OAuth client ID".

     * Select "Desktop app" for the Application type.

     * Give it a name (e.g., "Mailman Script").

     * Click "Create".

     * A dialog will show your Client ID and Client secret. Click "DOWNLOAD JSON" to download the client secret file.

   * Rename the downloaded JSON file to `client_secret.json`.

   * Create a directory named `credentials` in the root of the `mailman` project.

   * Move the `client_secret.json` file into this `mailman/credentials/` directory.

     ```
     mailman/
     └── credentials/
         └── client_secret.json
     
     ```

3.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: `venv\Scripts\activate`
    ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Database Setup:**
    This project uses SQLite3 by default for simplicity. No additional setup is required for SQLite3; the database file will be created automatically.
    If you would like to use PostgreSQL or MySQL, you'll need to configure the database connection string (`DATABASE_URI` in `config.py`) appropriately and ensure the database server is running. Things should ideally work seamlessly though I provide no guarantees yet.

## Configuration

### `rules.json`

This file, located in the project root, defines the rules for processing emails. Each rule is an object in a JSON array.

**Rule Structure:**

```jsonc
{
  "description": "Descriptive name for the rule",
  "conditions_predicate": "all", // or "any"
  "conditions": [
    {
      "field": "from_address", // Supported: "from_address" (or "From"), "subject" (or "Subject"), "body_plain" (or "Message"), "received_datetime" (or "Date received", "Received Date/Time"), "to_addresses" (or "To"), "cc_addresses" (or "Cc"), "bcc_addresses" (or "Bcc")
      "predicate": "contains", // String fields: "contains", "does_not_contain", "equals", "does_not_equal"
                               // Date fields: "less_than_days", "greater_than_days", "less_than_months", "greater_than_months"
      "value": "example.com"   // Value to check against (string for text, number string for dates)
    }
    // ... more conditions
  ],
  "actions": [
    {
      "type": "mark_as_read" // or "mark_as_unread"
    },
    {
      "type": "move_message",
      "mailbox": "Archive" // or "Trash", "Inbox", or a custom label name
    },
    {
      "type": "add_label",   // Additional action to add a specific label
      "label_name": "MyCustomLabel"
    }
    // ... more actions
  ]
}

```

## Running the Scripts

Ensure you are in the project's root directory (`mailman/`) and your virtual environment is activated.

1. **Fetch Emails from Gmail (`main_fetch_emails.py`):**
   This script will:

   * Authenticate with Gmail (a browser window will open for the first-time OAuth consent).

   * Create `credentials/token.json` to store the access token.

   * Create `emails.db` (SQLite database) if it doesn't exist.

   * Fetch a predefined number of recent emails from your Inbox (configurable in `main_fetch_emails.py`).

   * Parse and store these emails in the `emails.db` database.

   ```
   python main_fetch_emails.py
   ```

2. **Process Emails Based on Rules (`main_process_emails.py`):**
   This script will:

   * Load rules from `rules.json`.

   * Authenticate with Gmail (using the stored `token.json`).

   * Fetch all emails currently stored in `emails.db`.

   * Evaluate each email against each rule.

   * If an email matches a rule, the specified actions will be performed on that email in your Gmail account via the API.

   ```
   python main_process_emails.py
   ```

   **Caution:** Actions performed by this script (like moving emails or marking them as read/unread) will modify your actual Gmail data. Test with non-critical rules or a test Gmail account first.

## Development Notes & Potential Improvements

* **Rate Limiting:** While basic delays are included, more sophisticated handling of Gmail API rate limits could be implemented for very large volumes.

* **Configuration:** More settings could be moved to `config.py` or a dedicated configuration file (e.g., number of emails to fetch, default query).

* **Processed Flag:** Add a flag to the `emails` table in the database to mark emails that have already been processed by the rules, to avoid reprocessing them on subsequent runs of `main_process_emails.py`.

* **Selective Fetching:** `main_fetch_emails.py` could be enhanced to fetch only unread emails or emails received after the last fetch operation.
