"""
Silver Tier AI Employee - Gmail Watcher

This script monitors a Gmail inbox for new emails via IMAP.
When a new email is detected, it automatically creates a task file
in the Needs_Action folder for processing.

This is the SECOND watcher (alongside file_watcher.py), fulfilling
the Silver Tier "Expanded Perception" requirement.

Features:
- Gmail IMAP monitoring with OAuth2 or App Password support
- Test/demo mode that works without credentials
- Automatic task creation from incoming emails
- Duplicate prevention via seen message tracking
- Error handling that never crashes
- Error logging to Logs/gmail_watcher_errors.log

Setup (Production):
    1. Enable IMAP in Gmail: Settings > See all settings > Forwarding and POP/IMAP
    2. Generate an App Password: Google Account > Security > 2-Step Verification > App Passwords
    3. Set environment variables:
         GMAIL_USER=your_email@gmail.com
         GMAIL_APP_PASSWORD=your_app_password
    4. Run: python gmail_watcher.py

Setup (Demo/Test):
    Run without environment variables for demo mode:
        python gmail_watcher.py
    Demo mode simulates incoming emails every 60 seconds.

Press Ctrl+C to stop the watcher.
"""

import os
import sys
import time
import imaplib
import email
from email.header import decode_header
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

# How often to check for new emails (in seconds)
CHECK_INTERVAL = 60

# Gmail IMAP settings
IMAP_SERVER = os.environ.get("GMAIL_IMAP_SERVER", "imap.gmail.com")
IMAP_PORT = int(os.environ.get("GMAIL_IMAP_PORT", "993"))
GMAIL_USER = os.environ.get("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

# Enable demo mode if no credentials are set
DEMO_MODE = not GMAIL_USER or not GMAIL_APP_PASSWORD

# Folder paths (relative to where this script is located)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
NEEDS_ACTION_FOLDER = os.path.join(SCRIPT_DIR, "Needs_Action")
LOGS_FOLDER = os.path.join(SCRIPT_DIR, "Logs")
ERROR_LOG_FILE = os.path.join(LOGS_FOLDER, "gmail_watcher_errors.log")
SYSTEM_LOG_FILE = os.path.join(LOGS_FOLDER, "System_Log.md")

# Track which emails we've already processed (by Message-ID)
seen_message_ids = set()

# Demo mode counter
demo_counter = 0


# =============================================================================
# ERROR HANDLING UTILITIES
# =============================================================================

def log_error(error_message):
    """
    Write an error message to the error log file with a timestamp.
    """
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
    """
    Add an entry to the System_Log.md activity table.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    new_row = f"| {timestamp} | {action} | {details} |"

    try:
        if not os.path.exists(SYSTEM_LOG_FILE):
            return

        with open(SYSTEM_LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # Find the header row separator and insert after it
        marker = "|-----------|--------|---------|"
        if marker in content:
            content = content.replace(marker, f"{marker}\n{new_row}")
            with open(SYSTEM_LOG_FILE, "w", encoding="utf-8") as f:
                f.write(content)
    except Exception as e:
        log_error(f"Could not update System_Log: {e}")


def ensure_folder_exists(folder_path, folder_name):
    """
    Check if a folder exists, and create it if it doesn't.
    """
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"[SETUP] Created {folder_name} folder: {folder_path}")
        return True
    except PermissionError:
        log_error(f"Permission denied when creating {folder_name} folder at {folder_path}")
        return False
    except Exception as e:
        log_error(f"Failed to create {folder_name} folder: {e}")
        return False


# =============================================================================
# EMAIL PARSING UTILITIES
# =============================================================================

def decode_mime_header(header_value):
    """
    Decode a MIME-encoded email header into a readable string.
    """
    if header_value is None:
        return ""

    decoded_parts = decode_header(header_value)
    result = ""
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result += part.decode(charset or "utf-8", errors="replace")
        else:
            result += part
    return result


def get_email_body(msg):
    """
    Extract the plain text body from an email message.
    Handles both simple and multipart messages.
    """
    body = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))

            # Skip attachments, get text/plain parts
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    charset = part.get_content_charset() or "utf-8"
                    body = part.get_payload(decode=True).decode(charset, errors="replace")
                    break
                except Exception:
                    pass
    else:
        try:
            charset = msg.get_content_charset() or "utf-8"
            body = msg.get_payload(decode=True).decode(charset, errors="replace")
        except Exception:
            body = "(Could not decode email body)"

    # Truncate very long bodies for the task file
    max_length = 2000
    if len(body) > max_length:
        body = body[:max_length] + "\n\n... (truncated)"

    return body.strip()


# =============================================================================
# TASK CREATION
# =============================================================================

def create_email_task(sender, subject, body, message_id, received_date):
    """
    Create a task file in Needs_Action for an incoming email.

    Returns:
        str: Path to the created task file, or None if failed.
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Create a safe filename from the subject
        safe_subject = "".join(c if c.isalnum() or c in " _-" else "_" for c in subject)
        safe_subject = safe_subject.strip()[:50] or "no_subject"
        task_filename = f"task_email_{safe_subject}.md"
        task_path = os.path.join(NEEDS_ACTION_FOLDER, task_filename)

        # Avoid overwriting existing task files
        counter = 1
        while os.path.exists(task_path):
            task_filename = f"task_email_{safe_subject}_{counter}.md"
            task_path = os.path.join(NEEDS_ACTION_FOLDER, task_filename)
            counter += 1

        # Determine if this might need approval (external communication)
        needs_approval = False
        approval_actions = []
        body_lower = body.lower()

        # Check if the email requests actions that need approval
        if any(word in body_lower for word in ["reply", "respond", "send", "forward"]):
            needs_approval = True
            approval_actions.append("send_email")

        task_content = f"""---
type: email_response
status: pending
priority: medium
created_at: {timestamp}
related_files: []
approval_needed: {str(needs_approval).lower()}
approved: false
mcp_action: {str(approval_actions) if approval_actions else "[]"}
source: gmail_watcher
message_id: "{message_id}"
---

# Email Task: {subject}

## Email Details

- **From:** {sender}
- **Subject:** {subject}
- **Received:** {received_date}
- **Message ID:** {message_id}

## Email Body

{body}

## Steps

- [ ] Read and understand the email content
- [ ] Determine what action is needed (reply, forward, archive, or escalate)
- [ ] If reply needed: draft response and route through approval
- [ ] Execute the required action
- [ ] Mark this task as completed

## Notes

- **Source:** Gmail Watcher (automatic detection)
- **Detected at:** {timestamp}
- This task was auto-generated by the Gmail Watcher system.
"""

        with open(task_path, "w", encoding="utf-8") as f:
            f.write(task_content)

        return task_path

    except Exception as e:
        log_error(f"Error creating email task for '{subject}': {e}")
        return None


# =============================================================================
# GMAIL IMAP CONNECTION
# =============================================================================

def connect_to_gmail():
    """
    Connect to Gmail via IMAP and return the connection object.

    Returns:
        imaplib.IMAP4_SSL: Connected IMAP connection, or None on failure.
    """
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        print("[GMAIL] Connected successfully")
        return mail
    except imaplib.IMAP4.error as e:
        log_error(f"IMAP authentication failed: {e}")
        return None
    except Exception as e:
        log_error(f"Could not connect to Gmail: {e}")
        return None


def fetch_unseen_emails(mail):
    """
    Fetch all unseen (unread) emails from the inbox.

    Returns:
        list: List of dicts with email data (sender, subject, body, etc.)
    """
    emails_found = []

    try:
        mail.select("INBOX")

        # Search for unseen (unread) emails
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            return emails_found

        message_nums = messages[0].split()
        if not message_nums:
            return emails_found

        for num in message_nums:
            try:
                # Fetch the email (PEEK so it stays unread until we process it)
                status, msg_data = mail.fetch(num, "(BODY.PEEK[])")
                if status != "OK":
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Extract headers
                message_id = msg.get("Message-ID", f"unknown-{num}")
                sender = decode_mime_header(msg.get("From", "Unknown"))
                subject = decode_mime_header(msg.get("Subject", "(No Subject)"))
                date_str = msg.get("Date", "Unknown")
                body = get_email_body(msg)

                # Skip if we've already seen this message
                if message_id in seen_message_ids:
                    continue

                emails_found.append({
                    "message_id": message_id,
                    "sender": sender,
                    "subject": subject,
                    "date": date_str,
                    "body": body,
                    "num": num,
                })

            except Exception as e:
                log_error(f"Error parsing email #{num}: {e}")
                continue

        return emails_found

    except Exception as e:
        log_error(f"Error fetching emails: {e}")
        return emails_found


def mark_as_seen(mail, email_num):
    """
    Mark an email as seen/read in Gmail after processing.
    """
    try:
        mail.store(email_num, "+FLAGS", "\\Seen")
    except Exception as e:
        log_error(f"Could not mark email as seen: {e}")


# =============================================================================
# DEMO MODE
# =============================================================================

DEMO_EMAILS = [
    {
        "sender": "client@example.com",
        "subject": "Project Proposal Review Request",
        "body": "Hi,\n\nCould you please review the attached project proposal and send me your feedback by Friday?\n\nWe need to finalize the budget and timeline sections.\n\nBest regards,\nJohn Smith",
        "date": None,
    },
    {
        "sender": "team@startup.io",
        "subject": "Partnership Opportunity - AI Consulting",
        "body": "Hello,\n\nWe came across your consulting services and would like to discuss a potential partnership.\n\nOur startup is looking for AI strategy consulting for Q2 2026.\n\nCould we schedule a call this week?\n\nThanks,\nSarah Chen",
        "date": None,
    },
    {
        "sender": "newsletter@industry.com",
        "subject": "Weekly Industry Digest - AI Trends",
        "body": "This week in AI:\n\n1. New developments in autonomous agents\n2. MCP protocol gaining adoption\n3. Enterprise AI spending up 40%\n\nRead more at industry.com/digest",
        "date": None,
    },
]


def get_demo_email():
    """
    Return a simulated email for demo mode.
    Returns None when all demo emails have been sent.
    """
    global demo_counter

    if demo_counter >= len(DEMO_EMAILS):
        return None

    demo = DEMO_EMAILS[demo_counter]
    demo_counter += 1

    timestamp = datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")
    return {
        "message_id": f"<demo-{demo_counter}@gmail-watcher.demo>",
        "sender": demo["sender"],
        "subject": demo["subject"],
        "date": demo["date"] or timestamp,
        "body": demo["body"],
        "num": None,
    }


# =============================================================================
# MAIN CHECK LOOP
# =============================================================================

def check_for_new_emails_live():
    """
    Check Gmail for new emails and create tasks (live mode).

    Returns:
        int: Number of new emails processed.
    """
    mail = connect_to_gmail()
    if not mail:
        return 0

    try:
        emails = fetch_unseen_emails(mail)
        count = 0

        for email_data in emails:
            msg_id = email_data["message_id"]

            if msg_id in seen_message_ids:
                continue

            print(f"[NEW EMAIL] From: {email_data['sender']}")
            print(f"            Subject: {email_data['subject']}")

            task_path = create_email_task(
                sender=email_data["sender"],
                subject=email_data["subject"],
                body=email_data["body"],
                message_id=msg_id,
                received_date=email_data["date"],
            )

            if task_path:
                print(f"  -> Created task: {os.path.basename(task_path)}")
                seen_message_ids.add(msg_id)

                # Mark as read in Gmail
                if email_data["num"]:
                    mark_as_seen(mail, email_data["num"])

                count += 1
            else:
                print(f"  -> Failed to create task")

        return count

    except Exception as e:
        log_error(f"Error in email check: {e}")
        return 0

    finally:
        try:
            mail.logout()
        except Exception:
            pass


def check_for_new_emails_demo():
    """
    Simulate checking for new emails in demo mode.

    Returns:
        int: Number of demo emails processed.
    """
    demo_email = get_demo_email()

    if demo_email is None:
        return 0

    msg_id = demo_email["message_id"]
    print(f"[DEMO EMAIL] From: {demo_email['sender']}")
    print(f"             Subject: {demo_email['subject']}")

    task_path = create_email_task(
        sender=demo_email["sender"],
        subject=demo_email["subject"],
        body=demo_email["body"],
        message_id=msg_id,
        received_date=demo_email["date"],
    )

    if task_path:
        print(f"  -> Created task: {os.path.basename(task_path)}")
        seen_message_ids.add(msg_id)
        return 1
    else:
        print(f"  -> Failed to create task")
        return 0


# =============================================================================
# INITIALIZATION AND MAIN LOOP
# =============================================================================

def initialize_watcher():
    """
    Initialize the Gmail watcher by setting up folders and configuration.

    Returns:
        bool: True if initialization was successful.
    """
    print("[SETUP] Initializing Gmail Watcher...")

    needs_action_ok = ensure_folder_exists(NEEDS_ACTION_FOLDER, "Needs_Action")
    logs_ok = ensure_folder_exists(LOGS_FOLDER, "Logs")

    if not needs_action_ok:
        log_error("Critical folder Needs_Action could not be created.")

    if DEMO_MODE:
        print("[SETUP] Running in DEMO MODE (no Gmail credentials detected)")
        print("[SETUP] Set GMAIL_USER and GMAIL_APP_PASSWORD environment variables for live mode")
        print(f"[SETUP] Will simulate {len(DEMO_EMAILS)} incoming emails for demonstration")
    else:
        print(f"[SETUP] Gmail account: {GMAIL_USER}")
        print(f"[SETUP] IMAP server: {IMAP_SERVER}:{IMAP_PORT}")

        # Test connection
        mail = connect_to_gmail()
        if mail:
            print("[SETUP] Gmail connection test: SUCCESS")
            try:
                mail.logout()
            except Exception:
                pass
        else:
            print("[SETUP] Gmail connection test: FAILED (check credentials)")
            print("[SETUP] Continuing anyway - will retry on each check")

    print("[SETUP] Initialization complete.")
    return True


def main():
    """
    Main function that runs the Gmail watcher loop.
    """
    print("=" * 55)
    print("Silver Tier AI Employee - Gmail Watcher")
    print("=" * 55)
    print()

    initialize_watcher()

    print()
    print(f"Tasks will be created in: {NEEDS_ACTION_FOLDER}")
    print(f"Errors will be logged to: {ERROR_LOG_FILE}")
    print(f"Checking every {CHECK_INTERVAL} seconds...")
    mode_label = "DEMO" if DEMO_MODE else "LIVE"
    print(f"Mode: {mode_label}")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 55)

    # Log startup
    log_to_system_log("Gmail Watcher Started", f"Mode: {mode_label}, checking every {CHECK_INTERVAL}s")

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
                    new_count = check_for_new_emails_live()
                    if new_count > 0:
                        print(f"[GMAIL] Processed {new_count} new email(s)")

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


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    main()
