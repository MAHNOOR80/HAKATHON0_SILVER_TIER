"""
Bronze Tier AI Employee - File Watcher

This script monitors the Inbox folder for new files.
When a new file is detected, it automatically creates a task file
in the Needs_Action folder for processing.

Features:
- Automatic folder creation if missing
- Error handling that never crashes
- Error logging to Logs/watcher_errors.log

Usage:
    python file_watcher.py

Press Ctrl+C to stop the watcher.
"""

import os
import time
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

# How often to check for new files (in seconds)
CHECK_INTERVAL = 5

# Folder paths (relative to where this script is located)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INBOX_FOLDER = os.path.join(SCRIPT_DIR, "Inbox")
NEEDS_ACTION_FOLDER = os.path.join(SCRIPT_DIR, "Needs_Action")
LOGS_FOLDER = os.path.join(SCRIPT_DIR, "Logs")
ERROR_LOG_FILE = os.path.join(LOGS_FOLDER, "watcher_errors.log")

# =============================================================================
# TRACKING PROCESSED FILES
# =============================================================================

# This set keeps track of files we've already processed.
# Using a set allows fast lookup to avoid creating duplicate tasks.
processed_files = set()


# =============================================================================
# ERROR HANDLING UTILITIES
# =============================================================================

def log_error(error_message):
    """
    Write an error message to the error log file with a timestamp.

    This function is called whenever something goes wrong. It writes the error
    to a log file so you can review what happened later, even if you weren't
    watching the console.

    Args:
        error_message: A string describing what went wrong.

    Why this matters:
        - Errors are recorded even if no one is watching
        - You can review the log file later to diagnose issues
        - The script continues running instead of crashing
    """
    # Get the current time for the log entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Format the log entry with timestamp and error message
    log_entry = f"[{timestamp}] ERROR: {error_message}\n"

    try:
        # Ensure the Logs folder exists before writing
        # exist_ok=True means "don't error if folder already exists"
        os.makedirs(LOGS_FOLDER, exist_ok=True)

        # Open the log file in "append" mode ('a') so we add to it, not overwrite
        # encoding="utf-8" ensures special characters are handled properly
        with open(ERROR_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)

        # Also print to console so the user sees it immediately
        print(f"[ERROR LOGGED] {error_message}")

    except Exception as e:
        # If we can't even write to the log file, at least print to console
        # This is a "last resort" fallback
        print(f"[CRITICAL] Could not write to error log: {e}")
        print(f"[ORIGINAL ERROR] {error_message}")


def ensure_folder_exists(folder_path, folder_name):
    """
    Check if a folder exists, and create it if it doesn't.

    This is a helper function that safely creates folders. It handles errors
    gracefully and logs them if something goes wrong.

    Args:
        folder_path: The full path to the folder.
        folder_name: A friendly name for the folder (used in messages).

    Returns:
        bool: True if the folder exists (or was created), False if creation failed.
    """
    try:
        if not os.path.exists(folder_path):
            # Create the folder (and any parent folders if needed)
            os.makedirs(folder_path)
            print(f"[SETUP] Created {folder_name} folder: {folder_path}")
        return True

    except PermissionError:
        # This happens if you don't have permission to create folders here
        log_error(f"Permission denied when creating {folder_name} folder at {folder_path}")
        return False

    except Exception as e:
        # Catch any other unexpected errors
        log_error(f"Failed to create {folder_name} folder: {e}")
        return False


# =============================================================================
# CORE FUNCTIONS
# =============================================================================

def get_existing_files():
    """
    Get a list of all files currently in the Inbox folder.

    Returns:
        set: A set of filenames found in the Inbox folder.
              Returns empty set if there's an error.
    """
    try:
        # Check if the Inbox folder exists
        if not os.path.exists(INBOX_FOLDER):
            # Try to create it instead of just warning
            if not ensure_folder_exists(INBOX_FOLDER, "Inbox"):
                return set()

        # List all files (not folders) in the Inbox
        files = set()
        for item in os.listdir(INBOX_FOLDER):
            item_path = os.path.join(INBOX_FOLDER, item)
            # Only include files, not subdirectories
            if os.path.isfile(item_path):
                files.add(item)

        return files

    except PermissionError:
        log_error(f"Permission denied when reading Inbox folder")
        return set()

    except Exception as e:
        log_error(f"Error reading Inbox folder: {e}")
        return set()


def create_task_file(filename):
    """
    Create a task file in the Needs_Action folder for a given Inbox file.

    Args:
        filename: The name of the file that was added to Inbox.

    Returns:
        str: The path to the created task file, or None if creation failed.
    """
    try:
        # Generate a timestamp for when this task was created
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Create a safe task filename by adding "task_" prefix
        # This helps identify task files and avoids naming conflicts
        task_filename = f"task_{filename}.md"
        task_path = os.path.join(NEEDS_ACTION_FOLDER, task_filename)

        # Build the task file content using the improved structured template
        # The section between --- markers is called "frontmatter" (metadata)
        task_content = f"""---
type: file_review
status: pending
priority: medium
created_at: {timestamp}
related_files: ["Inbox/{filename}"]
---

# Review File: {filename}

## Description

A new file was detected in the Inbox folder and requires review. The AI Employee should examine this file and determine the appropriate action to take.

## Steps

- [ ] Open and review the file content
- [ ] Determine what action is needed (process, archive, or escalate)
- [ ] Execute the required action
- [ ] Mark this task as completed

## Notes

- **Source:** Inbox folder
- **Detected at:** {timestamp}
- This task was auto-generated by the File Watcher system.
"""

        # Write the task file to the Needs_Action folder
        with open(task_path, "w", encoding="utf-8") as f:
            f.write(task_content)
        return task_path

    except PermissionError:
        log_error(f"Permission denied when creating task file for {filename}")
        return None

    except Exception as e:
        log_error(f"Error creating task file for {filename}: {e}")
        return None


def check_for_new_files():
    """
    Check the Inbox folder for any new files that haven't been processed yet.
    For each new file found, create a corresponding task in Needs_Action.

    Returns:
        int: The number of new files processed.
    """
    try:
        # Get current files in Inbox
        current_files = get_existing_files()

        # Find files that are new (not in our processed set)
        new_files = current_files - processed_files

        # Process each new file
        for filename in new_files:
            print(f"[NEW FILE DETECTED] {filename}")

            # Create a task file for this new file
            task_path = create_task_file(filename)

            if task_path:
                print(f"  -> Created task: {os.path.basename(task_path)}")
                # Mark this file as processed so we don't create duplicate tasks
                processed_files.add(filename)
            else:
                print(f"  -> Failed to create task for {filename}")

        return len(new_files)

    except Exception as e:
        # If something unexpected happens during the check, log it but don't crash
        log_error(f"Error during file check: {e}")
        return 0


def initialize_watcher():
    """
    Initialize the watcher by setting up folders and recording existing files.

    This function:
    1. Creates the Inbox folder if it doesn't exist
    2. Creates the Needs_Action folder if it doesn't exist
    3. Creates the Logs folder if it doesn't exist
    4. Records existing files so we don't process them as "new"

    Returns:
        bool: True if initialization was successful, False otherwise.
    """
    global processed_files

    print("[SETUP] Initializing file watcher...")

    # Ensure all required folders exist
    # If any folder creation fails, we log the error but try to continue
    inbox_ok = ensure_folder_exists(INBOX_FOLDER, "Inbox")
    needs_action_ok = ensure_folder_exists(NEEDS_ACTION_FOLDER, "Needs_Action")
    logs_ok = ensure_folder_exists(LOGS_FOLDER, "Logs")

    # Check if critical folders are ready
    if not inbox_ok or not needs_action_ok:
        log_error("Critical folders could not be created. Watcher may not function correctly.")
        # Continue anyway - maybe the folders will be created later

    # Mark all existing files as already processed
    # This way we only create tasks for NEW files added after the watcher starts
    processed_files = get_existing_files()

    if processed_files:
        print(f"[SETUP] Found {len(processed_files)} existing file(s) in Inbox (will be ignored)")

    print("[SETUP] Initialization complete.")
    return True


def main():
    """
    Main function that runs the file watcher loop.

    This function contains the main monitoring loop wrapped in error handling.
    If an error occurs, it's logged and the loop continues - the script never crashes.
    """
    print("=" * 50)
    print("Bronze Tier AI Employee - File Watcher")
    print("=" * 50)
    print()

    # Initialize - set up folders and record existing files
    initialize_watcher()

    print()
    print(f"Watching folder: {INBOX_FOLDER}")
    print(f"Tasks will be created in: {NEEDS_ACTION_FOLDER}")
    print(f"Errors will be logged to: {ERROR_LOG_FILE}")
    print(f"Checking every {CHECK_INTERVAL} seconds...")
    print()
    print("Press Ctrl+C to stop")
    print("-" * 50)

    # Main loop - runs forever until user presses Ctrl+C
    # The outer try/except catches KeyboardInterrupt (Ctrl+C)
    try:
        while True:
            # Inner try/except ensures the loop NEVER crashes
            # Even if something goes wrong, we log it and keep running
            try:
                # Check for new files
                new_count = check_for_new_files()

                # Wait before checking again
                time.sleep(CHECK_INTERVAL)

            except KeyboardInterrupt:
                # Re-raise KeyboardInterrupt so the outer handler catches it
                # This ensures Ctrl+C still works to stop the script
                raise

            except Exception as e:
                # Something unexpected happened in the loop
                # Log the error and continue - don't crash!
                log_error(f"Unexpected error in main loop: {e}")

                # Wait a bit before retrying to avoid spamming errors
                print("[RECOVERING] Waiting 10 seconds before retrying...")
                time.sleep(10)

    except KeyboardInterrupt:
        # User pressed Ctrl+C to stop - this is expected, not an error
        print()
        print("-" * 50)
        print("Watcher stopped by user.")
        print(f"Total files processed this session: {len(processed_files)}")


# =============================================================================
# ENTRY POINT
# =============================================================================

# This block only runs if you execute this file directly (not when imported)
if __name__ == "__main__":
    main()
