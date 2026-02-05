"""
Bronze Tier AI Employee - Log Manager

This script prevents log files from growing forever by rotating them
when they exceed a size limit.

Behavior:
- Checks System_Log.md and watcher_errors.log
- If a file exceeds 1 MB, it gets archived with a timestamp
- A fresh empty log file is created in its place

Usage:
    python log_manager.py

You can run this manually or schedule it to run periodically.
"""

import os
from datetime import datetime

# =============================================================================
# CONFIGURATION
# =============================================================================

# Maximum log file size in bytes (1 MB = 1,048,576 bytes)
MAX_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB

# Folder paths (relative to where this script is located)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_FOLDER = os.path.join(SCRIPT_DIR, "Logs")

# List of log files to monitor
# Each entry is a tuple: (file_path, header_content_for_new_file)
LOG_FILES = [
    (
        os.path.join(LOGS_FOLDER, "System_Log.md"),
        """# System Log

Central log for all AI Employee activity and system events.

---

## Activity Log

| Timestamp | Action | Details |
|-----------|--------|---------|

---

_New entries should be added at the top of the Activity Log table._
"""
    ),
    (
        os.path.join(LOGS_FOLDER, "watcher_errors.log"),
        "# Watcher Error Log\n# This file records errors from the file watcher.\n\n"
    ),
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_file_size(file_path):
    """
    Get the size of a file in bytes.

    Args:
        file_path: Path to the file.

    Returns:
        int: Size in bytes, or 0 if file doesn't exist.
    """
    try:
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        return 0
    except Exception as e:
        print(f"[ERROR] Could not get size of {file_path}: {e}")
        return 0


def format_size(size_bytes):
    """
    Convert bytes to a human-readable format.

    Args:
        size_bytes: Size in bytes.

    Returns:
        str: Formatted size string (e.g., "1.5 MB").
    """
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def generate_archive_name(file_path):
    """
    Generate an archive filename with a timestamp.

    Example:
        System_Log.md -> System_Log_2026-01-29.md
        watcher_errors.log -> watcher_errors_2026-01-29.log

    Args:
        file_path: Original file path.

    Returns:
        str: New file path with timestamp inserted before extension.
    """
    # Get the directory, filename, and extension
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)

    # Split filename into name and extension
    # Example: "System_Log.md" -> ("System_Log", ".md")
    if "." in filename:
        name, extension = filename.rsplit(".", 1)
        extension = "." + extension
    else:
        name = filename
        extension = ""

    # Generate timestamp string
    timestamp = datetime.now().strftime("%Y-%m-%d")

    # Build the new filename
    new_filename = f"{name}_{timestamp}{extension}"

    # Handle case where archive already exists (add counter)
    new_path = os.path.join(directory, new_filename)
    counter = 1
    while os.path.exists(new_path):
        new_filename = f"{name}_{timestamp}_{counter}{extension}"
        new_path = os.path.join(directory, new_filename)
        counter += 1

    return new_path


# =============================================================================
# MAIN ROTATION LOGIC
# =============================================================================

def rotate_log_file(file_path, header_content):
    """
    Rotate a log file if it exceeds the size limit.

    Steps:
    1. Check if file exists and exceeds size limit
    2. Rename the old file with a timestamp
    3. Create a fresh file with the original name

    Args:
        file_path: Path to the log file.
        header_content: Content to put in the new empty file.

    Returns:
        bool: True if rotation happened, False otherwise.
    """
    # Check if file exists
    if not os.path.exists(file_path):
        print(f"[SKIP] File does not exist: {file_path}")
        return False

    # Get current file size
    current_size = get_file_size(file_path)
    filename = os.path.basename(file_path)

    print(f"[CHECK] {filename}: {format_size(current_size)}")

    # Check if rotation is needed
    if current_size < MAX_SIZE_BYTES:
        print(f"  -> Size OK (limit: {format_size(MAX_SIZE_BYTES)})")
        return False

    # Rotation needed!
    print(f"  -> Exceeds limit! Rotating...")

    try:
        # Step 1: Generate archive filename
        archive_path = generate_archive_name(file_path)
        archive_name = os.path.basename(archive_path)

        # Step 2: Rename the old file to archive name
        os.rename(file_path, archive_path)
        print(f"  -> Archived as: {archive_name}")

        # Step 3: Create fresh file with header content
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(header_content)
        print(f"  -> Created fresh: {filename}")

        return True

    except PermissionError:
        print(f"  -> [ERROR] Permission denied. File may be in use.")
        return False

    except Exception as e:
        print(f"  -> [ERROR] Rotation failed: {e}")
        return False


def run_log_rotation():
    """
    Check all configured log files and rotate any that exceed the size limit.
    """
    print("=" * 50)
    print("Bronze Tier AI Employee - Log Manager")
    print("=" * 50)
    print()
    print(f"Size limit: {format_size(MAX_SIZE_BYTES)}")
    print(f"Checking {len(LOG_FILES)} log file(s)...")
    print()

    # Track how many files were rotated
    rotated_count = 0

    # Check each log file
    for file_path, header_content in LOG_FILES:
        if rotate_log_file(file_path, header_content):
            rotated_count += 1
        print()

    # Summary
    print("-" * 50)
    if rotated_count > 0:
        print(f"Done! Rotated {rotated_count} file(s).")
    else:
        print("Done! No rotation needed.")


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    run_log_rotation()
