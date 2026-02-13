"""
Silver Tier AI Employee - Gmail Watcher (OAuth 2.0)

Monitors Gmail inbox for new unread emails using Google OAuth 2.0.
On first run, opens a browser for Google login and consent.
Saves a refreshable token to token.json for subsequent runs.

Features:
- Full OAuth 2.0 flow via google-auth-oauthlib
- Browser-based Google login & consent on first run
- Automatic token refresh (no re-login needed)
- Polls every 60 seconds for unread emails
- Creates structured .md task files in /Needs_Action/
- Marks processed emails as read + adds "ProcessedByAI" label
- Full YAML frontmatter with from, subject, labels, snippet
- Demo mode fallback if credentials.json is missing

Setup:
    1. Go to Google Cloud Console > APIs & Services > Credentials
    2. Create OAuth 2.0 Client ID (Desktop app)
    3. Download credentials.json to project root
    4. Enable Gmail API in your Google Cloud project
    5. Run: python gmail_watcher.py
    6. Browser opens -> log in -> grant permissions
    7. token.json is saved automatically for future runs

Required packages:
    pip install google-auth google-auth-oauthlib google-api-python-client

Press Ctrl+C to stop the watcher.
"""

import os
import sys
import time
import base64
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

CHECK_INTERVAL = 60  # seconds between polls

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "credentials.json")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "token.json")

NEEDS_ACTION_FOLDER = os.path.join(SCRIPT_DIR, "Needs_Action")
LOGS_FOLDER = os.path.join(SCRIPT_DIR, "Logs")
ERROR_LOG_FILE = os.path.join(LOGS_FOLDER, "gmail_watcher_errors.log")
SYSTEM_LOG_FILE = os.path.join(LOGS_FOLDER, "System_Log.md")

# Label name to apply after processing
PROCESSED_LABEL = "ProcessedByAI"

# Track processed message IDs in-memory to avoid duplicates within a session
seen_message_ids = set()

# Demo mode counter
demo_counter = 0

# Whether we're in demo mode
DEMO_MODE = False


# =============================================================================
# ERROR HANDLING UTILITIES
# =============================================================================

def log_error(error_message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] ERROR: {error_message}\n"
    try:
        os.makedirs(LOGS_FOLDER, exist_ok=True)
        with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
        print(f"[ERROR LOGGED] {error_message}")
    except Exception as e:
        print(f"[CRITICAL] Could not write to error log: {e}")
        print(f"[ORIGINAL ERROR] {error_message}")


def log_to_system_log(action, details):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_row = f"| {timestamp} | {action} | {details} |"
    try:
        if not os.path.exists(SYSTEM_LOG_FILE):
            return
        with open(SYSTEM_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        marker = "|-----------|--------|---------|"
        if marker in content:
            content = content.replace(marker, f"{marker}\n{new_row}")
            with open(SYSTEM_LOG_FILE, "w", encoding="utf-8") as f:
                f.write(content)
    except Exception as e:
        log_error(f"Could not update System_Log: {e}")


def ensure_folder_exists(folder_path, folder_name):
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"[SETUP] Created {folder_name} folder: {folder_path}")
        return True
    except Exception as e:
        log_error(f"Failed to create {folder_name} folder: {e}")
        return False


# =============================================================================
# OAUTH 2.0 AUTHENTICATION
# =============================================================================

def authenticate_gmail():
    """
    Authenticate with Gmail using OAuth 2.0.
    - If token.json exists and is valid, use it.
    - If token is expired, refresh it automatically.
    - If no token exists, open browser for consent flow.

    Returns:
        google.oauth2.credentials.Credentials or None
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None

    # Load existing token
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
            print("[AUTH] Loaded existing token from token.json")
        except Exception as e:
            log_error(f"Could not load token.json: {e}")
            creds = None

    # Refresh or get new token
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("[AUTH] Token expired, refreshing...")
                creds.refresh(Request())
                print("[AUTH] Token refreshed successfully")
            except Exception as e:
                log_error(f"Token refresh failed: {e}")
                creds = None

        if not creds:
            # Run full OAuth flow - opens browser
            print("[AUTH] No valid token found. Opening browser for Google login...")
            print("[AUTH] Please log in and grant Gmail permissions in the browser window.")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
                creds = flow.run_local_server(port=0)
                print("[AUTH] Authentication successful!")
            except Exception as e:
                log_error(f"OAuth flow failed: {e}")
                return None

        # Save token for future runs
        try:
            with open(TOKEN_FILE, "w") as token_file:
                token_file.write(creds.to_json())
            print("[AUTH] Token saved to token.json")
        except Exception as e:
            log_error(f"Could not save token: {e}")

    return creds


def build_gmail_service(creds):
    """Build the Gmail API service client."""
    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=creds)


# =============================================================================
# LABEL MANAGEMENT
# =============================================================================

def get_or_create_label(service, label_name):
    """
    Get the label ID for label_name. Create it if it doesn't exist.
    Returns label ID string or None.
    """
    try:
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])

        for label in labels:
            if label["name"] == label_name:
                return label["id"]

        # Create the label
        label_body = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        }
        created = service.users().labels().create(userId="me", body=label_body).execute()
        print(f"[GMAIL] Created label: {label_name}")
        return created["id"]

    except Exception as e:
        log_error(f"Could not get/create label '{label_name}': {e}")
        return None


# =============================================================================
# EMAIL FETCHING (Gmail API)
# =============================================================================

def fetch_unread_emails(service):
    """
    Fetch unread emails from Inbox using Gmail API.
    Returns list of message dicts with full details.
    """
    emails = []
    try:
        results = service.users().messages().list(
            userId="me",
            q="is:unread in:inbox",
            maxResults=10,
        ).execute()

        messages = results.get("messages", [])
        if not messages:
            return emails

        for msg_ref in messages:
            msg_id = msg_ref["id"]

            if msg_id in seen_message_ids:
                continue

            try:
                msg = service.users().messages().get(
                    userId="me",
                    id=msg_id,
                    format="full",
                ).execute()

                headers = msg.get("payload", {}).get("headers", [])
                header_dict = {}
                for h in headers:
                    header_dict[h["name"].lower()] = h["value"]

                sender = header_dict.get("from", "Unknown")
                subject = header_dict.get("subject", "(No Subject)")
                date = header_dict.get("date", "Unknown")
                message_id_header = header_dict.get("message-id", msg_id)

                # Get labels
                label_ids = msg.get("labelIds", [])
                snippet = msg.get("snippet", "")

                # Extract body
                body = extract_body(msg.get("payload", {}))

                emails.append({
                    "id": msg_id,
                    "message_id": message_id_header,
                    "sender": sender,
                    "subject": subject,
                    "date": date,
                    "body": body,
                    "snippet": snippet,
                    "labels": label_ids,
                })

            except Exception as e:
                log_error(f"Error fetching message {msg_id}: {e}")
                continue

        return emails

    except Exception as e:
        log_error(f"Error listing messages: {e}")
        return emails


def extract_body(payload):
    """
    Recursively extract plain text body from Gmail API message payload.
    """
    body = ""

    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        raw = payload["body"]["data"]
        body = base64.urlsafe_b64decode(raw).decode("utf-8", errors="replace")
    elif payload.get("parts"):
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
                raw = part["body"]["data"]
                body = base64.urlsafe_b64decode(raw).decode("utf-8", errors="replace")
                break
            elif part.get("parts"):
                body = extract_body(part)
                if body:
                    break

    # Truncate very long bodies
    if len(body) > 2000:
        body = body[:2000] + "\n\n... (truncated)"

    return body.strip()


def mark_as_read_and_label(service, msg_id, label_id):
    """
    Mark a message as read and add the ProcessedByAI label.
    """
    try:
        modify_body = {
            "removeLabelIds": ["UNREAD"],
        }
        if label_id:
            modify_body["addLabelIds"] = [label_id]

        service.users().messages().modify(
            userId="me",
            id=msg_id,
            body=modify_body,
        ).execute()
    except Exception as e:
        log_error(f"Could not mark message {msg_id} as read: {e}")


# =============================================================================
# TASK CREATION
# =============================================================================

def create_email_task(sender, subject, body, message_id, received_date, labels, snippet):
    """
    Create a .md task file in Needs_Action/ for an incoming email.
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Safe filename
        safe_subject = "".join(c if c.isalnum() or c in " _-" else "_" for c in subject)
        safe_subject = safe_subject.strip()[:50] or "no_subject"
        task_filename = f"task_email_{safe_subject}.md"
        task_path = os.path.join(NEEDS_ACTION_FOLDER, task_filename)

        counter = 1
        while os.path.exists(task_path):
            task_filename = f"task_email_{safe_subject}_{counter}.md"
            task_path = os.path.join(NEEDS_ACTION_FOLDER, task_filename)
            counter += 1

        # Determine if approval is needed
        needs_approval = False
        approval_actions = []
        body_lower = body.lower()
        if any(word in body_lower for word in ["reply", "respond", "send", "forward", "schedule", "call"]):
            needs_approval = True
            approval_actions.append("send_email")

        # Suggest actions based on content
        suggested_actions = []
        if any(word in body_lower for word in ["reply", "respond", "feedback", "review"]):
            suggested_actions.append("Reply to sender")
        if any(word in body_lower for word in ["schedule", "call", "meeting", "discuss"]):
            suggested_actions.append("Schedule a meeting/call")
        if any(word in body_lower for word in ["newsletter", "digest", "update", "weekly"]):
            suggested_actions.append("Archive (informational)")
        if any(word in body_lower for word in ["urgent", "asap", "immediately", "critical"]):
            suggested_actions.append("Flag as high priority")
        if not suggested_actions:
            suggested_actions.append("Review and decide on action")

        # Format labels
        labels_str = ", ".join(labels) if labels else "INBOX"

        task_content = f"""---
type: email_response
status: pending
priority: medium
created_at: {timestamp}
from: "{sender}"
subject: "{subject}"
received_at: "{received_date}"
message_id: "{message_id}"
labels: "{labels_str}"
snippet: "{snippet[:200]}"
related_files: []
approval_needed: {str(needs_approval).lower()}
approved: false
mcp_action: {str(approval_actions) if approval_actions else "[]"}
source: gmail_watcher
---

# Email Task: {subject}

## Email Details

| Field | Value |
|-------|-------|
| **From** | {sender} |
| **Subject** | {subject} |
| **Received** | {received_date} |
| **Labels** | {labels_str} |
| **Message ID** | `{message_id}` |

## Snippet

> {snippet}

## Email Body

{body if body else "(No body content)"}

## Suggested Actions

{chr(10).join(f"- [ ] {action}" for action in suggested_actions)}

## Steps

- [ ] Read and understand the email content
- [ ] Determine what action is needed
- [ ] If reply needed: draft response and route through approval
- [ ] Execute the required action
- [ ] Mark this task as completed

## Notes

- **Source:** Gmail Watcher (OAuth 2.0)
- **Detected at:** {timestamp}
- Auto-generated by the Gmail Watcher system.
"""

        with open(task_path, "w", encoding="utf-8") as f:
            f.write(task_content)

        return task_path

    except Exception as e:
        log_error(f"Error creating email task for '{subject}': {e}")
        return None


# =============================================================================
# DEMO MODE
# =============================================================================

DEMO_EMAILS = [
    {
        "sender": "client@example.com",
        "subject": "Project Proposal Review Request",
        "body": "Hi,\n\nCould you please review the attached project proposal and send me your feedback by Friday?\n\nWe need to finalize the budget and timeline sections.\n\nBest regards,\nJohn Smith",
        "snippet": "Could you please review the attached project proposal and send me your feedback by Friday?",
        "labels": ["INBOX", "IMPORTANT"],
    },
    {
        "sender": "team@startup.io",
        "subject": "Partnership Opportunity - AI Consulting",
        "body": "Hello,\n\nWe came across your consulting services and would like to discuss a potential partnership.\n\nOur startup is looking for AI strategy consulting for Q2 2026.\n\nCould we schedule a call this week?\n\nThanks,\nSarah Chen",
        "snippet": "We came across your consulting services and would like to discuss a potential partnership.",
        "labels": ["INBOX"],
    },
    {
        "sender": "newsletter@industry.com",
        "subject": "Weekly Industry Digest - AI Trends",
        "body": "This week in AI:\n\n1. New developments in autonomous agents\n2. MCP protocol gaining adoption\n3. Enterprise AI spending up 40%\n\nRead more at industry.com/digest",
        "snippet": "This week in AI: New developments in autonomous agents, MCP protocol gaining adoption",
        "labels": ["INBOX", "CATEGORY_UPDATES"],
    },
]


def get_demo_email():
    global demo_counter
    if demo_counter >= len(DEMO_EMAILS):
        return None

    demo = DEMO_EMAILS[demo_counter]
    demo_counter += 1

    timestamp = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
    return {
        "id": f"demo-{demo_counter}",
        "message_id": f"<demo-{demo_counter}@gmail-watcher.demo>",
        "sender": demo["sender"],
        "subject": demo["subject"],
        "date": timestamp,
        "body": demo["body"],
        "snippet": demo["snippet"],
        "labels": demo["labels"],
    }


def check_for_new_emails_demo():
    demo_email = get_demo_email()
    if demo_email is None:
        return 0

    print(f"[DEMO EMAIL] From: {demo_email['sender']}")
    print(f"             Subject: {demo_email['subject']}")

    task_path = create_email_task(
        sender=demo_email["sender"],
        subject=demo_email["subject"],
        body=demo_email["body"],
        message_id=demo_email["message_id"],
        received_date=demo_email["date"],
        labels=demo_email["labels"],
        snippet=demo_email["snippet"],
    )

    if task_path:
        print(f"  -> Created task: {os.path.basename(task_path)}")
        seen_message_ids.add(demo_email["id"])
        return 1
    else:
        print(f"  -> Failed to create task")
        return 0


# =============================================================================
# LIVE MODE - POLL LOOP
# =============================================================================

def check_for_new_emails_live(service, processed_label_id):
    """
    Fetch unread emails, create tasks, mark as read + label.
    Returns number of emails processed.
    """
    emails = fetch_unread_emails(service)
    count = 0

    for email_data in emails:
        msg_id = email_data["id"]

        if msg_id in seen_message_ids:
            continue

        print(f"[NEW EMAIL] From: {email_data['sender']}")
        print(f"            Subject: {email_data['subject']}")

        task_path = create_email_task(
            sender=email_data["sender"],
            subject=email_data["subject"],
            body=email_data["body"],
            message_id=email_data["message_id"],
            received_date=email_data["date"],
            labels=email_data["labels"],
            snippet=email_data["snippet"],
        )

        if task_path:
            print(f"  -> Created task: {os.path.basename(task_path)}")
            seen_message_ids.add(msg_id)

            # Mark as read and add ProcessedByAI label
            mark_as_read_and_label(service, msg_id, processed_label_id)
            print(f"  -> Marked as read + labeled '{PROCESSED_LABEL}'")
            count += 1
        else:
            print(f"  -> Failed to create task")

    return count


# =============================================================================
# MAIN
# =============================================================================

def main():
    global DEMO_MODE

    print("=" * 55)
    print("Silver Tier AI Employee - Gmail Watcher (OAuth 2.0)")
    print("=" * 55)
    print()

    ensure_folder_exists(NEEDS_ACTION_FOLDER, "Needs_Action")
    ensure_folder_exists(LOGS_FOLDER, "Logs")

    # Check if credentials.json exists
    if not os.path.exists(CREDENTIALS_FILE):
        print("[SETUP] credentials.json not found in project root.")
        print("[SETUP] Falling back to DEMO MODE.")
        print(f"[SETUP] To use live Gmail, place credentials.json from Google Cloud Console here:")
        print(f"        {CREDENTIALS_FILE}")
        print()
        DEMO_MODE = True
    else:
        print(f"[SETUP] Found credentials.json")
        DEMO_MODE = False

    service = None
    processed_label_id = None

    if not DEMO_MODE:
        # Authenticate with OAuth 2.0
        creds = authenticate_gmail()
        if creds:
            service = build_gmail_service(creds)
            processed_label_id = get_or_create_label(service, PROCESSED_LABEL)
            print("[SETUP] Gmail API connected successfully")
        else:
            print("[SETUP] Authentication failed. Falling back to DEMO MODE.")
            DEMO_MODE = True

    mode_label = "DEMO" if DEMO_MODE else "LIVE (OAuth 2.0)"
    print()
    print(f"Tasks will be created in: {NEEDS_ACTION_FOLDER}")
    print(f"Errors will be logged to: {ERROR_LOG_FILE}")
    print(f"Checking every {CHECK_INTERVAL} seconds...")
    print(f"Mode: {mode_label}")
    if not DEMO_MODE:
        print(f"Processed emails will be labeled: {PROCESSED_LABEL}")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 55)

    log_to_system_log("Gmail Watcher Started", f"Mode: {mode_label}, interval: {CHECK_INTERVAL}s")

    try:
        while True:
            try:
                if DEMO_MODE:
                    new_count = check_for_new_emails_demo()
                    if new_count > 0:
                        print(f"[DEMO] Processed {new_count} demo email(s). "
                              f"{len(DEMO_EMAILS) - demo_counter} remaining.")
                    elif demo_counter >= len(DEMO_EMAILS):
                        print(f"[DEMO] All {len(DEMO_EMAILS)} demo emails processed. "
                              f"Watcher continues running (no more demos to send).")
                else:
                    new_count = check_for_new_emails_live(service, processed_label_id)
                    if new_count > 0:
                        print(f"[GMAIL] Processed {new_count} new email(s)")
                    else:
                        print(f"[GMAIL] No new unread emails. Waiting...")

                time.sleep(CHECK_INTERVAL)

            except KeyboardInterrupt:
                raise
            except Exception as e:
                log_error(f"Unexpected error in main loop: {e}")
                print("[RECOVERING] Waiting 30 seconds before retrying...")
                time.sleep(30)

    except KeyboardInterrupt:
        print()
        print("-" * 55)
        print("Gmail Watcher stopped by user.")
        print(f"Total emails processed this session: {len(seen_message_ids)}")
        log_to_system_log("Gmail Watcher Stopped", f"Processed {len(seen_message_ids)} email(s)")


if __name__ == "__main__":
    main()
