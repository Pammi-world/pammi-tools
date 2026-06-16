"""Pammi ID Generator

Deterministic, human-readable ID generator for the Pammi Content System.

Prefixes:
- CP-###  Content Packages
- LI-###  LinkedIn posts
- AS-###  Assets (globally unique)
- LOG-### Publishing Log entries
- VR-###  Visual Requests
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

# ID prefix constants
PREFIXES = {
    "CP": "Content Packages",
    "LI": "LinkedIn posts",
    "AS": "Assets (globally unique)",
    "LOG": "Publishing Log entries",
    "VR": "Visual Requests",
}

# Sheet column that contains the ID for each tab
SHEET_TAB = {
    "CP": "Content Packages",
    "LI": "LinkedIn",
    "AS": "Assets",
    "LOG": "Publishing Log",
    "VR": "Assets",  # Visual Requests live in Assets tab as separate asset_type
}

SHEET_ID_COLUMN = {
    "CP": "package_id",
    "LI": "post_id",
    "AS": "asset_id",
    "LOG": "log_id",
    "VR": "asset_id",  # VRs share Assets tab
}

SPREADSHEET_ID = "1rHM6bHIsq8h8a0jG83afWdlZs6wHV25yANutPdkhODk"
COUNTERS_PATH = Path.home() / ".pammi-tools" / "counters.json"
ID_PATTERN = re.compile(r"^([A-Z]+)-(\d{3,})$")

# Type aliases
ID = str
Prefix = str


def validate_id(id_str: str) -> bool:
    """Check if a string matches the ID format: PREFIX-NNN (zero-padded).

    Examples:
        >>> validate_id("CP-001")
        True
        >>> validate_id("AS-1234")
        True
        >>> validate_id("cp-001")
        False
        >>> validate_id("CP-1")
        False
    """
    if not isinstance(id_str, str):
        return False
    return bool(ID_PATTERN.match(id_str))


def parse_id(id_str: str) -> tuple[str, int]:
    """Parse an ID into (prefix, number).

    Raises ValueError if invalid.
    """
    match = ID_PATTERN.match(id_str)
    if not match:
        raise ValueError(f"Invalid ID format: {id_str!r} (expected PREFIX-NNN)")
    return match.group(1), int(match.group(2))


def format_id(prefix: str, number: int) -> ID:
    """Format an ID with the given prefix and number (zero-padded to 3+ digits)."""
    if not isinstance(prefix, str) or not prefix.isalpha() or not prefix.isupper():
        raise ValueError(f"Invalid prefix: {prefix!r} (must be uppercase letters)")
    if not isinstance(number, int) or number < 0:
        raise ValueError(f"Invalid number: {number!r}")
    return f"{prefix}-{number:03d}"


def _load_counters() -> dict:
    """Load persisted counter cache (fallback)."""
    if not COUNTERS_PATH.exists():
        return {}
    try:
        with open(COUNTERS_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_counters(counters: dict) -> None:
    """Persist counter cache to disk."""
    COUNTERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(COUNTERS_PATH, "w") as f:
        json.dump(counters, f, indent=2)


def _read_sheet_ids(tab: str, id_column: str) -> list[str]:
    """Read all IDs from a specific column in a Google Sheet tab.

    Uses Composio CLI. Returns a list of ID strings.
    Falls back to empty list if Composio is unavailable.
    """
    try:
        import subprocess

        result = subprocess.run(
            [
                "composio", "execute", "GOOGLESHEETS_BATCH_GET",
                "-d", json.dumps({
                    "spreadsheet_id": SPREADSHEET_ID,
                    "ranges": [f"{tab}!{id_column}2:{id_column}Z"],
                })
            ],
            env={**os.environ, "PATH": "/root/.composio:" + os.environ.get("PATH", "")},
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return []

        data = json.loads(result.stdout)
        if not data.get("successful"):
            return []

        # Extract IDs from the response
        ids = []
        for key in ("valueRanges", "value_ranges"):
            if key in data.get("data", {}):
                for vr in data["data"][key]:
                    values = vr.get("values", [])
                    for row in values:
                        for cell in row:
                            if isinstance(cell, str) and cell.strip():
                                ids.append(cell.strip())
        return ids
    except Exception:
        return []


def _extract_max_number(ids: list[str], prefix: str) -> int:
    """Given a list of ID strings, find the max number for the given prefix.

    Returns 0 if no IDs match.
    """
    max_num = 0
    for id_str in ids:
        if not isinstance(id_str, str):
            continue
        match = ID_PATTERN.match(id_str.strip())
        if not match:
            continue
        if match.group(1) == prefix:
            num = int(match.group(2))
            if num > max_num:
                max_num = num
    return max_num


def get_next(prefix: str, use_sheet: bool = True) -> ID:
    """Get the next available ID for the given prefix.

    Strategy:
    1. If use_sheet=True, read all IDs from the Google Sheet for this prefix
       and find the max number.
    2. Compare with local counter cache.
    3. Return max + 1.

    Args:
        prefix: ID prefix (e.g., "CP", "LI", "AS", "LOG", "VR")
        use_sheet: Whether to read from Google Sheet (default True)

    Returns:
        Next available ID string.

    Examples:
        >>> get_next("CP", use_sheet=False)
        'CP-001'
    """
    prefix = prefix.upper()
    if prefix not in PREFIXES:
        raise ValueError(f"Unknown prefix: {prefix!r}. Valid: {list(PREFIXES.keys())}")

    counters = _load_counters()
    local_max = counters.get(prefix, 0)

    sheet_max = 0
    if use_sheet:
        tab = SHEET_TAB[prefix]
        col = SHEET_ID_COLUMN[prefix]
        ids = _read_sheet_ids(tab, col)
        sheet_max = _extract_max_number(ids, prefix)

    next_num = max(local_max, sheet_max) + 1
    new_id = format_id(prefix, next_num)

    # Persist the new high-water mark
    counters[prefix] = next_num
    _save_counters(counters)

    return new_id


def reserve(prefix: str, count: int = 1, use_sheet: bool = True) -> list[ID]:
    """Reserve one or more consecutive IDs.

    Useful when you know you need multiple at once.
    """
    prefix = prefix.upper()
    if count < 1:
        raise ValueError("count must be >= 1")

    # Get the next ID first
    first = get_next(prefix, use_sheet=use_sheet)
    first_num = parse_id(first)[1]

    ids = [format_id(prefix, first_num + i) for i in range(count)]

    # Update counter to the highest reserved
    counters = _load_counters()
    counters[prefix] = first_num + count - 1
    _save_counters(counters)

    return ids


def reset_counter(prefix: str) -> None:
    """Reset the local counter cache for a prefix. Use with caution."""
    counters = _load_counters()
    if prefix in counters:
        del counters[prefix]
        _save_counters(counters)


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pammi-ids",
        description="Pammi ID generator - deterministic, human-readable IDs",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # next command
    next_parser = subparsers.add_parser("next", help="Get the next available ID")
    next_parser.add_argument(
        "prefix",
        choices=list(PREFIXES.keys()),
        help="ID prefix",
    )
    next_parser.add_argument(
        "--no-sheet",
        action="store_true",
        help="Don't read from Google Sheet (use local counter only)",
    )

    # validate command
    val_parser = subparsers.add_parser("validate", help="Validate an ID format")
    val_parser.add_argument("id", help="ID to validate")

    # reserve command
    res_parser = subparsers.add_parser("reserve", help="Reserve multiple IDs")
    res_parser.add_argument(
        "prefix",
        choices=list(PREFIXES.keys()),
        help="ID prefix",
    )
    res_parser.add_argument(
        "count",
        type=int,
        nargs="?",
        default=1,
        help="Number of IDs to reserve (default: 1)",
    )
    res_parser.add_argument(
        "--no-sheet",
        action="store_true",
        help="Don't read from Google Sheet (use local counter only)",
    )

    # list command
    subparsers.add_parser("list", help="List all valid prefixes")

    args = parser.parse_args(argv)

    if args.command == "next":
        try:
            new_id = get_next(args.prefix, use_sheet=not args.no_sheet)
            print(new_id)
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "validate":
        if validate_id(args.id):
            print(f"✓ {args.id} is valid")
            return 0
        else:
            print(f"✗ {args.id} is invalid (expected format: PREFIX-NNN)")
            return 1

    elif args.command == "reserve":
        try:
            ids = reserve(args.prefix, args.count, use_sheet=not args.no_sheet)
            for id in ids:
                print(id)
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "list":
        print("Valid prefixes:")
        for prefix, desc in PREFIXES.items():
            print(f"  {prefix:6} {desc}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
