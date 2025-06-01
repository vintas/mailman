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

## Getting Started

Follow these steps to set up and run the Mailman script.

### Prerequisites

* Python 3.8+
* A Google Cloud Project with the Gmail API enabled.
* OAuth 2.0 Client ID credentials ( `credentials.json` ) downloaded from your Google Cloud Console.

### Installation

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/vintas/mailman.git](https://github.com/vintas/mailman.git)
    cd mailman
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: `venv\Scripts\activate`
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Google API Credentials:**
    * Go to the Google Cloud Console.
    * Create a new project or select an existing one.
    * Navigate to "APIs & Services" > "Enabled APIs & services" and ensure "Gmail API" is enabled.
    * Go to "APIs & Services" > "Credentials".
    * Click "Create Credentials" > "OAuth client ID."
    * Choose "Desktop app" for the application type.
    * Download the `credentials.json` file and place it in the root directory of your `mailman` project.

5.  **Database Setup:**
    This project uses SQLite3 by default for simplicity. No additional setup is required for SQLite3; the database file will be created automatically.
    If you would like to use PostgreSQL or MySQL, you'll need to configure the database connection string appropriately in your script and ensure the respective database server is running. Things should ideally work seamlessly though I provide no guarantees yet.
