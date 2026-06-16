"""pammi_timezone - Timezone handling for the Pammi Content System.

Strategy:
- All internal computation and storage in UTC
- Display in Eastern Time (America/New_York)
- Convert at the boundary (input from user, output for display)

Uses zoneinfo (Python 3.9+) for accurate IANA timezone handling with DST.
"""

import argparse
import datetime
import re
import sys
from typing import Optional, Union
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

__all__ = [
    "EASTERN",
    "UTC",
    "now_utc",
    "now_eastern",
    "eastern_to_utc",
    "utc_to_eastern",
    "parse_user_datetime",
    "format_for_display",
    "main",
]


def now_utc() -> datetime.datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.datetime.now(UTC)


def now_eastern() -> datetime.datetime:
    """Return current Eastern datetime (timezone-aware)."""
    return datetime.datetime.now(EASTERN)


def _ensure_aware(dt: datetime.datetime, default_tz: ZoneInfo) -> datetime.datetime:
    """If dt is naive, attach default_tz. Otherwise return as-is."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=default_tz)
    return dt


def eastern_to_utc(dt_or_string: Union[datetime.datetime, str]) -> datetime.datetime:
    """Convert Eastern datetime to UTC.

    Args:
        dt_or_string: A datetime or string. If naive, assumed to be Eastern.

    Returns:
        Timezone-aware UTC datetime.

    Examples:
        >>> eastern_to_utc(datetime(2026, 6, 18, 9, 0))  # 9am EDT
        datetime.datetime(2026, 6, 18, 13, 0, tzinfo=ZoneInfo('UTC'))
        >>> eastern_to_utc("2026-06-18 09:00 ET")
        datetime.datetime(2026, 6, 18, 13, 0, tzinfo=ZoneInfo('UTC'))
    """
    if isinstance(dt_or_string, str):
        dt = _parse_iso_or_natural(dt_or_string)
    else:
        dt = dt_or_string
    dt = _ensure_aware(dt, EASTERN)
    # If it's already in UTC, just return
    if dt.tzinfo == UTC:
        return dt
    return dt.astimezone(UTC)


def utc_to_eastern(dt_or_string: Union[datetime.datetime, str]) -> datetime.datetime:
    """Convert UTC datetime to Eastern.

    Args:
        dt_or_string: A datetime or string. If naive, assumed to be UTC.

    Returns:
        Timezone-aware Eastern datetime.

    Examples:
        >>> utc_to_eastern(datetime(2026, 6, 18, 13, 0, tzinfo=UTC))
        datetime.datetime(2026, 6, 18, 9, 0, tzinfo=ZoneInfo('America/New_York'))
    """
    if isinstance(dt_or_string, str):
        dt = _parse_iso_or_natural(dt_or_string)
    else:
        dt = dt_or_string
    dt = _ensure_aware(dt, UTC)
    return dt.astimezone(EASTERN)


def _parse_iso_or_natural(s: str) -> datetime.datetime:
    """Parse a string into datetime, supporting ISO and common natural formats."""
    s = s.strip()

    # Try ISO 8601 first (fromisoformat handles Z suffix since Python 3.11)
    try:
        # Python 3.11+ fromisoformat handles 'Z' and timezone offsets
        return datetime.datetime.fromisoformat(s)
    except (ValueError, TypeError):
        pass

    # Try common formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue

    raise ValueError(f"Could not parse datetime string: {s!r}")


def parse_user_datetime(user_input: str,
                        now: Optional[datetime.datetime] = None) -> datetime.datetime:
    """Parse a user-friendly datetime string and return UTC.

    Supports many formats:
    - "tomorrow 9am" / "tomorrow 9:00 AM"
    - "today 14:00"
    - "next monday 10am"
    - "in 2 hours"
    - "in 30 minutes"
    - "2026-06-18 14:00"
    - "2026-06-18 14:00 EST"
    - "2026-06-18T14:00:00-04:00"
    - "Jun 18, 2026 9:00 AM"

    Args:
        user_input: User-provided string.
        now: Reference "now" for relative parsing. Defaults to actual now_utc().

    Returns:
        Timezone-aware UTC datetime.

    Raises:
        ValueError: If input cannot be parsed.
    """
    if not isinstance(user_input, str):
        raise TypeError("user_input must be a string")

    original = user_input
    s = user_input.strip()
    if not s:
        raise ValueError("Empty datetime string")

    # Normalize whitespace
    s = re.sub(r"\s+", " ", s)

    if now is None:
        now = now_utc()

    # Handle relative expressions
    s_lower = s.lower()

    # "in N hours" / "in N minutes" / "in N hour" / "in 1 hour"
    m = re.match(r"^in\s+(\d+)\s*(hour|hours|hr|hr)s?$", s_lower)
    if m:
        n = int(m.group(1))
        return now + datetime.timedelta(hours=n)

    m = re.match(r"^in\s+(\d+)\s*(minute|minutes|min|mins)s?$", s_lower)
    if m:
        n = int(m.group(1))
        return now + datetime.timedelta(minutes=n)

    m = re.match(r"^in\s+(\d+)\s*(day|days|d)s?$", s_lower)
    if m:
        n = int(m.group(1))
        return now + datetime.timedelta(days=n)

    # "tomorrow [time]" / "today [time]"
    m = re.match(r"^(today|tomorrow|tonight)(?:\s+(.*))?$", s_lower)
    if m:
        day_keyword = m.group(1)
        time_part = (m.group(2) or "").strip()
        ref_date = now.astimezone(EASTERN).date()
        if day_keyword == "tomorrow":
            ref_date += datetime.timedelta(days=1)
        if not time_part or time_part == "tonight":
            # Default to 9 AM
            return _build_utc_for_eastern_date_and_time(ref_date, "9am")
        return _build_utc_for_eastern_date_and_time(ref_date, time_part)

    # "next <weekday> [time]"
    m = re.match(r"^next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(.*))?$", s_lower)
    if m:
        weekday_name = m.group(1)
        time_part = (m.group(2) or "").strip()
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        target_weekday = weekdays.index(weekday_name)
        ref_today = now.astimezone(EASTERN).date()
        days_ahead = target_weekday - ref_today.weekday()
        if days_ahead <= 0:  # "next monday" usually means the one after this week's
            days_ahead += 7
        ref_date = ref_today + datetime.timedelta(days=days_ahead)
        if not time_part:
            return _build_utc_for_eastern_date_and_time(ref_date, "9am")
        return _build_utc_for_eastern_date_and_time(ref_date, time_part)

    # "Jun 18, 2026 9:00 AM" - try strptime with various formats
    # Try with explicit timezone suffix first
    dt = _try_parse_with_tz(s, original)
    if dt is not None:
        return dt

    # Try parsing as Eastern
    dt_eastern = _try_parse_eastern(s)
    if dt_eastern is not None:
        return dt_eastern.astimezone(UTC)

    # Try parsing as UTC ISO
    try:
        dt = datetime.datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (ValueError, TypeError):
        pass

    raise ValueError(f"Could not parse user datetime: {original!r}")


def _try_parse_with_tz(s: str, original: str) -> Optional[datetime.datetime]:
    """Try parsing with explicit timezone suffix like ET, EST, EDT, UTC, Z."""
    s_lower = s.lower()
    # Extract timezone suffix
    tz_map = {
        "est": -5, "edt": -4,
        "cst": -6, "cdt": -5,
        "mst": -7, "mdt": -6,
        "pst": -8, "pdt": -7,
        "et": None,  # handled by Eastern
        "ct": -6,
        "mt": -7,
        "pt": -8,
        "utc": 0, "z": 0, "gmt": 0,
    }

    m = re.search(r"\s+([a-z]{2,4})$", s_lower)
    if m and m.group(1) in tz_map:
        suffix = m.group(1)
        body = s[:m.start()].strip()
        offset = tz_map[suffix]
        if suffix == "et":
            # Parse as Eastern
            try:
                eastern_dt = _try_parse_eastern(body)
                if eastern_dt is not None:
                    return eastern_dt.astimezone(UTC)
            except Exception:
                pass
        elif offset is not None:
            try:
                dt = datetime.datetime.strptime(body, "%Y-%m-%d %H:%M")
                dt = dt.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=offset)))
                return dt.astimezone(UTC)
            except ValueError:
                try:
                    dt = datetime.datetime.strptime(body, "%Y-%m-%d %I:%M %p")
                    dt = dt.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=offset)))
                    return dt.astimezone(UTC)
                except ValueError:
                    try:
                        dt = datetime.datetime.strptime(body, "%Y-%m-%d")
                        dt = dt.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=offset)))
                        return dt.astimezone(UTC)
                    except ValueError:
                        pass
    return None


def _try_parse_eastern(s: str) -> Optional[datetime.datetime]:
    """Try parsing a string as Eastern time."""
    formats = [
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %I:%M %p",
        "%Y-%m-%d %I:%M%p",
        "%Y-%m-%d %I %p",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%Y",
        "%b %d, %Y %I:%M %p",
        "%b %d, %Y %H:%M",
        "%B %d, %Y %I:%M %p",
        "%B %d, %Y %H:%M",
        "%b %d %Y %I:%M %p",
        "%b %d %Y %H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S.%f",
    ]
    for fmt in formats:
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return dt.replace(tzinfo=EASTERN)
        except ValueError:
            continue
    return None


def _build_utc_for_eastern_date_and_time(date: datetime.date, time_str: str) -> datetime.datetime:
    """Build a UTC datetime for an Eastern date and a time string like '9am', '14:00'."""
    hour, minute = _parse_time_string(time_str)
    naive = datetime.datetime(date.year, date.month, date.day, hour, minute)
    return naive.replace(tzinfo=EASTERN).astimezone(UTC)


def _parse_time_string(time_str: str) -> tuple[int, int]:
    """Parse '9am', '9:00 AM', '14:30', '9:00' into (hour, minute)."""
    s = time_str.strip().lower()
    # Strip optional "at" prefix
    s = re.sub(r"^at\s+", "", s)
    # 12-hour with am/pm
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*([ap])m?$", s)
    if m:
        h = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm = m.group(3)
        if ampm == "p" and h != 12:
            h += 12
        elif ampm == "a" and h == 12:
            h = 0
        return h, minute
    # 24-hour
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Just hour
    m = re.match(r"^(\d{1,2})$", s)
    if m:
        return int(m.group(1)), 0
    raise ValueError(f"Could not parse time: {time_str!r}")


def format_for_display(utc_dt: datetime.datetime) -> str:
    """Format a UTC datetime as a user-friendly Eastern display string.

    Output format: 'Jun 18, 2026 9:00 AM EDT'

    Args:
        utc_dt: A timezone-aware datetime. If naive, assumed to be UTC.

    Returns:
        Formatted Eastern string with timezone abbreviation.

    Examples:
        >>> format_for_display(datetime(2026, 6, 18, 13, 0, tzinfo=UTC))
        'Jun 18, 2026 9:00 AM EDT'
        >>> format_for_display(datetime(2026, 1, 18, 14, 0, tzinfo=UTC))
        'Jan 18, 2026 9:00 AM EST'
    """
    dt = _ensure_aware(utc_dt, UTC)
    eastern_dt = dt.astimezone(EASTERN)

    # Get the timezone abbreviation (EDT or EST)
    tz_name = eastern_dt.tzname()  # e.g., "EDT" or "EST"

    # Format: "Jun 18, 2026 9:00 AM EDT"
    return eastern_dt.strftime(f"%b %-d, %Y %-I:%M %p {tz_name}")


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pammi-timezone",
        description="Pammi timezone - convert and format times between UTC and Eastern",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # now
    now_parser = subparsers.add_parser("now", help="Print current UTC and Eastern time")

    # convert
    convert_parser = subparsers.add_parser("convert", help="Convert a time")
    convert_parser.add_argument("--input", required=True, help="Input datetime string")
    convert_parser.add_argument(
        "--from",
        dest="from_tz",
        choices=["utc", "eastern", "et"],
        required=True,
        help="Input timezone (utc, eastern/et)",
    )
    convert_parser.add_argument(
        "--to",
        choices=["utc", "eastern", "et", "iso"],
        required=True,
        help="Output timezone",
    )

    # format
    format_parser = subparsers.add_parser("format", help="Format a UTC time as Eastern display")
    format_parser.add_argument("--input", required=True, help="UTC datetime string (ISO 8601)")

    # parse
    parse_parser = subparsers.add_parser("parse", help="Parse a user-friendly datetime and show UTC")
    parse_parser.add_argument("--input", required=True, help="User-friendly datetime string")

    args = parser.parse_args(argv)

    try:
        if args.command == "now":
            utc = now_utc()
            eastern = utc.astimezone(EASTERN)
            print(f"UTC:    {utc.isoformat()}")
            print(f"Eastern: {eastern.isoformat()}")
            print(f"Display: {format_for_display(utc)}")
            return 0
        elif args.command == "convert":
            from_tz = "eastern" if args.from_tz in ("eastern", "et") else "utc"
            to_tz = "eastern" if args.to in ("eastern", "et") else "utc"

            # Parse input
            try:
                dt = datetime.datetime.fromisoformat(args.input)
            except (ValueError, TypeError):
                # Try common formats
                dt = _try_parse_eastern(args.input)
                if dt is None:
                    raise ValueError(f"Could not parse input: {args.input!r}")

            if from_tz == "eastern":
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=EASTERN)
                result = dt.astimezone(UTC if to_tz == "utc" else EASTERN)
            else:
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                result = dt.astimezone(EASTERN if to_tz == "eastern" else UTC)

            if args.to == "iso":
                print(result.isoformat())
            else:
                print(result.isoformat())
            return 0
        elif args.command == "format":
            dt = datetime.datetime.fromisoformat(args.input)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            print(format_for_display(dt))
            return 0
        elif args.command == "parse":
            utc = parse_user_datetime(args.input)
            print(f"UTC:  {utc.isoformat()}")
            print(f"Display: {format_for_display(utc)}")
            return 0
        else:
            parser.print_help()
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
