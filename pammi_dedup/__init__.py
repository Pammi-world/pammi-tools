"""Pammi Dedup

Content deduplication for the Pammi Content System.

Generates and checks dedup_keys to prevent duplicate content from being
posted to the same platform on the same day.

Format: platform:normalized_topic:yyyy-mm-dd
Example: linkedin:queues-for-ai-agents:2026-06-18
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from typing import Optional

# The Pammi Content Calendar spreadsheet
SPREADSHEET_ID = "1rHM6bHIsq8h8a0jG83afWdlZs6wHV25yANutPdkhODk"

# Map platform → sheet tab name
PLATFORM_TO_TAB = {
    "linkedin": "LinkedIn",
}

# Map platform → ID column name
PLATFORM_TO_ID_COL = {
    "linkedin": "post_id",
}

# Map platform → dedup_key column
PLATFORM_TO_DEDUP_COL = {
    "linkedin": "dedup_key",
}

# Map platform → status column
PLATFORM_TO_STATUS_COL = {
    "linkedin": "status",
}

# Statuses that count as "exists" for duplicate detection
ACTIVE_STATUSES = {"DRAFT", "ASSET_READY", "READY", "APPROVED", "SCHEDULED", "POSTED"}

# Regex for normalization: keep alphanumerics, spaces, dashes
KEEP_CHARS_RE = re.compile(r"[^a-z0-9\s\-]")
MULTI_SPACE_RE = re.compile(r"\s+")
LEADING_TRAILING_DASH_RE = re.compile(r"^-+|-+$")


def normalize_topic(topic: str) -> str:
    """Normalize a topic string for use in a dedup_key.

    Rules:
    - Lowercase
    - Strip leading/trailing whitespace
    - Collapse multiple spaces
    - Replace underscores with spaces
    - Remove punctuation (keep alphanumerics, spaces, dashes)
    - Trim leading/trailing dashes
    - Replace spaces with dashes

    Examples:
        >>> normalize_topic("Queues for AI Agents!")
        'queues-for-ai-agents'
        >>> normalize_topic("  Hello,   World!!  ")
        'hello-world'
        >>> normalize_topic("Foo___Bar")
        'foo-bar'
        >>> normalize_topic("  --leading--  ")
        'leading'
    """
    if not isinstance(topic, str):
        raise TypeError(f"topic must be a string, got {type(topic).__name__}")

    # Lowercase
    result = topic.lower()
    # Replace underscores with spaces (so they collapse to dashes later)
    result = result.replace("_", " ")
    # Remove punctuation (keep alphanumerics, spaces, dashes)
    result = KEEP_CHARS_RE.sub("", result)
    # Collapse multiple spaces
    result = MULTI_SPACE_RE.sub(" ", result)
    # Strip whitespace
    result = result.strip()
    # Replace spaces with dashes
    result = result.replace(" ", "-")
    # Remove leading/trailing dashes
    result = LEADING_TRAILING_DASH_RE.sub("", result)
    return result


def compute_dedup_key(platform: str, topic: str,
                      scheduled_date: Optional[str] = None) -> str:
    """Compute the dedup_key for a post.

    Format: platform:normalized_topic:yyyy-mm-dd

    Args:
        platform: e.g. "linkedin"
        topic: The topic text to normalize
        scheduled_date: Date string in YYYY-MM-DD format. If None, uses today.

    Returns:
        The dedup_key string.

    Examples:
        >>> compute_dedup_key("linkedin", "Queues for AI Agents!", "2026-06-18")
        'linkedin:queues-for-ai-agents:2026-06-18'
        >>> compute_dedup_key("linkedin", "Hello World")
        'linkedin:hello-world'
    """
    if not isinstance(platform, str) or not platform:
        raise ValueError("platform must be a non-empty string")
    platform = platform.lower().strip()

    normalized = normalize_topic(topic)

    if scheduled_date is None:
        scheduled_date = datetime.date.today().isoformat()
    else:
        # Validate the date format
        try:
            datetime.date.fromisoformat(scheduled_date)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"scheduled_date must be in YYYY-MM-DD format, got: {scheduled_date!r}"
            ) from e

    return f"{platform}:{normalized}:{scheduled_date}"


def _composio_env() -> dict:
    """Build env with composio on PATH."""
    return {**os.environ, "PATH": "/root/.composio:" + os.environ.get("PATH", "")}


def _read_sheet_columns(sheet_id: str, tab: str, columns: list[str]) -> dict[str, list[str]]:
    """Read multiple columns from a Google Sheet tab.

    Args:
        sheet_id: The Google Sheet ID
        tab: Tab name within the sheet
        columns: List of column letters/names to read

    Returns:
        Dict {column_name: [values...]}.
    """
    # Build a range that captures all needed columns
    ranges = []
    for col in columns:
        ranges.append(f"{tab}!{col}2:{col}Z")

    result = subprocess.run(
        ["composio", "execute", "GOOGLESHEETS_BATCH_GET", "-d",
         json.dumps({"spreadsheet_id": sheet_id, "ranges": ranges})],
        env=_composio_env(),
        capture_output=True,
        text=True,
        timeout=30,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Composio failed (exit {result.returncode}): {result.stderr}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON: {result.stdout[:200]}") from e

    if not data.get("successful"):
        raise RuntimeError(f"Sheet read failed: {data.get('error')}")

    # Extract values per column
    response_data = data.get("data", {})
    value_ranges = response_data.get("valueRanges", response_data.get("value_ranges", []))

    result_dict = {col: [] for col in columns}
    for i, vr in enumerate(value_ranges):
        if i >= len(columns):
            break
        col = columns[i]
        values = vr.get("values", [])
        # Each row is a list of cells; flatten
        flat = []
        for row in values:
            for cell in row:
                if isinstance(cell, str):
                    flat.append(cell)
        result_dict[col] = flat

    return result_dict


def find_duplicate(sheet_id: str, platform: str, topic: str,
                   scheduled_date: Optional[str] = None) -> Optional[dict]:
    """Check the Google Sheet for an existing post with the same dedup_key.

    Args:
        sheet_id: The Google Sheet ID (e.g., the Pammi Content Calendar ID)
        platform: e.g. "linkedin"
        topic: The topic text
        scheduled_date: Date string in YYYY-MM-DD format

    Returns:
        Dict with the existing post info if duplicate found, else None.
        Format: {post_id, dedup_key, status, topic, ...}
    """
    platform = platform.lower().strip()
    if platform not in PLATFORM_TO_TAB:
        raise ValueError(f"Unsupported platform: {platform!r}")

    target_key = compute_dedup_key(platform, topic, scheduled_date)

    # Read the relevant columns
    tab = PLATFORM_TO_TAB[platform]
    id_col = PLATFORM_TO_ID_COL[platform]
    dedup_col = PLATFORM_TO_DEDUP_COL[platform]
    status_col = PLATFORM_TO_STATUS_COL[platform]
    topic_col = "topic"

    columns = [id_col, dedup_col, status_col, topic_col]
    sheet_data = _read_sheet_columns(sheet_id, tab, columns)

    # Walk through rows
    dedups = sheet_data.get(dedup_col, [])
    ids = sheet_data.get(id_col, [])
    statuses = sheet_data.get(status_col, [])
    topics = sheet_data.get(topic_col, [])

    for i, dedup in enumerate(dedups):
        if not dedup:
            continue
        if dedup.strip() != target_key:
            continue
        # Found a matching dedup_key
        # Get status (default to empty if not present)
        status = statuses[i].strip() if i < len(statuses) else ""
        # Skip SKIPPED or other inactive statuses
        if status and status.upper() not in ACTIVE_STATUSES:
            continue
        return {
            "post_id": ids[i].strip() if i < len(ids) else "",
            "dedup_key": dedup.strip(),
            "status": status,
            "topic": topics[i].strip() if i < len(topics) else "",
            "row": i + 2,  # +2 because sheet is 1-indexed and we skip header
        }

    return None


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pammi-dedup",
        description="Pammi dedup - check for duplicate content",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # compute command
    compute_parser = subparsers.add_parser("compute", help="Compute a dedup_key")
    compute_parser.add_argument("--platform", required=True, help="Platform (linkedin, etc.)")
    compute_parser.add_argument("--topic", required=True, help="Topic text")
    compute_parser.add_argument(
        "--date", default=None,
        help="Scheduled date in YYYY-MM-DD format (default: today)",
    )

    # check command
    check_parser = subparsers.add_parser("check", help="Check for existing duplicate")
    check_parser.add_argument("--platform", required=True, help="Platform")
    check_parser.add_argument("--topic", required=True, help="Topic text")
    check_parser.add_argument("--date", default=None, help="Scheduled date")
    check_parser.add_argument(
        "--sheet-id",
        default=SPREADSHEET_ID,
        help=f"Google Sheet ID (default: {SPREADSHEET_ID})",
    )

    # normalize command (helper)
    norm_parser = subparsers.add_parser("normalize", help="Just normalize a topic")
    norm_parser.add_argument("topic", help="Topic text to normalize")

    args = parser.parse_args(argv)

    if args.command == "compute":
        try:
            key = compute_dedup_key(args.platform, args.topic, args.date)
            print(key)
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "check":
        try:
            existing = find_duplicate(args.sheet_id, args.platform, args.topic, args.date)
            if existing:
                print(json.dumps(existing, indent=2))
            else:
                print("null")
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "normalize":
        try:
            print(normalize_topic(args.topic))
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
