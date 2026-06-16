"""Tests for pammi_timezone library."""

import datetime
import os
import sys
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pammi_timezone import (
    EASTERN,
    UTC,
    now_utc,
    now_eastern,
    eastern_to_utc,
    utc_to_eastern,
    parse_user_datetime,
    format_for_display,
    main,
)


class TestNowFunctions(unittest.TestCase):
    """Test now_utc and now_eastern."""

    def test_now_utc_is_aware(self):
        n = now_utc()
        self.assertIsNotNone(n.tzinfo)
        self.assertEqual(n.tzinfo, UTC)

    def test_now_eastern_is_aware(self):
        n = now_eastern()
        self.assertIsNotNone(n.tzinfo)
        self.assertEqual(n.tzinfo, EASTERN)

    def test_now_utc_eastern_are_same_instant(self):
        # They should be the same instant in time (within a few microseconds)
        u = now_utc()
        e = now_eastern()
        # Convert both to UTC and check the difference is < 1 second
        diff = abs((u.astimezone(UTC) - e.astimezone(UTC)).total_seconds())
        self.assertLess(diff, 1.0)


class TestEasternToUtc(unittest.TestCase):
    """Test eastern_to_utc conversions, including DST transitions."""

    def test_summer_edt(self):
        # June 18, 2026 9:00 AM EDT (UTC-4)
        eastern = datetime.datetime(2026, 6, 18, 9, 0, tzinfo=EASTERN)
        utc = eastern_to_utc(eastern)
        self.assertEqual(utc, datetime.datetime(2026, 6, 18, 13, 0, tzinfo=UTC))

    def test_winter_est(self):
        # January 18, 2026 9:00 AM EST (UTC-5)
        eastern = datetime.datetime(2026, 1, 18, 9, 0, tzinfo=EASTERN)
        utc = eastern_to_utc(eastern)
        self.assertEqual(utc, datetime.datetime(2026, 1, 18, 14, 0, tzinfo=UTC))

    def test_naive_assumed_eastern(self):
        # Naive datetime should be assumed Eastern
        naive = datetime.datetime(2026, 6, 18, 9, 0)
        utc = eastern_to_utc(naive)
        self.assertEqual(utc, datetime.datetime(2026, 6, 18, 13, 0, tzinfo=UTC))

    def test_string_input(self):
        utc = eastern_to_utc("2026-06-18 09:00")
        self.assertEqual(utc, datetime.datetime(2026, 6, 18, 13, 0, tzinfo=UTC))

    def test_iso_with_offset(self):
        utc = eastern_to_utc("2026-06-18T09:00:00-04:00")
        self.assertEqual(utc, datetime.datetime(2026, 6, 18, 13, 0, tzinfo=UTC))

    def test_dst_spring_forward(self):
        # March 8, 2026 is DST start in US (clocks jump 2am -> 3am)
        # 2026-03-08 1:30 AM EST -> 2026-03-08 6:30 AM UTC
        # 2026-03-08 3:30 AM EDT -> 2026-03-08 7:30 AM UTC
        before = eastern_to_utc(datetime.datetime(2026, 3, 8, 1, 30, tzinfo=EASTERN))
        after = eastern_to_utc(datetime.datetime(2026, 3, 8, 3, 30, tzinfo=EASTERN))
        self.assertEqual(before, datetime.datetime(2026, 3, 8, 6, 30, tzinfo=UTC))
        self.assertEqual(after, datetime.datetime(2026, 3, 8, 7, 30, tzinfo=UTC))

    def test_dst_fall_back(self):
        # November 1, 2026 is DST end (clocks fall back 2am -> 1am)
        # 0:30 AM is still EDT (-4) -> 4:30 UTC
        # 2:30 AM is EST (-5) -> 7:30 UTC
        before = eastern_to_utc(datetime.datetime(2026, 11, 1, 0, 30, tzinfo=EASTERN))
        after = eastern_to_utc(datetime.datetime(2026, 11, 1, 2, 30, tzinfo=EASTERN))
        self.assertEqual(before, datetime.datetime(2026, 11, 1, 4, 30, tzinfo=UTC))
        self.assertEqual(after, datetime.datetime(2026, 11, 1, 7, 30, tzinfo=UTC))


class TestUtcToEastern(unittest.TestCase):
    """Test utc_to_eastern conversions."""

    def test_summer_edt(self):
        utc = datetime.datetime(2026, 6, 18, 13, 0, tzinfo=UTC)
        eastern = utc_to_eastern(utc)
        self.assertEqual(eastern, datetime.datetime(2026, 6, 18, 9, 0, tzinfo=EASTERN))

    def test_winter_est(self):
        utc = datetime.datetime(2026, 1, 18, 14, 0, tzinfo=UTC)
        eastern = utc_to_eastern(utc)
        self.assertEqual(eastern, datetime.datetime(2026, 1, 18, 9, 0, tzinfo=EASTERN))

    def test_naive_assumed_utc(self):
        naive = datetime.datetime(2026, 6, 18, 13, 0)
        eastern = utc_to_eastern(naive)
        self.assertEqual(eastern, datetime.datetime(2026, 6, 18, 9, 0, tzinfo=EASTERN))

    def test_round_trip(self):
        original = datetime.datetime(2026, 6, 18, 9, 0, tzinfo=EASTERN)
        round_trip = utc_to_eastern(eastern_to_utc(original))
        self.assertEqual(original, round_trip)


class TestParseUserDatetime(unittest.TestCase):
    """Test parse_user_datetime with various inputs."""

    def setUp(self):
        # Fix "now" to a known Eastern time for deterministic tests
        # 2026-06-15 23:30 EDT (Monday night)
        self.fixed_now_utc = datetime.datetime(2026, 6, 16, 3, 30, tzinfo=UTC)
        # 2026-06-15 23:30 EDT
        # Tomorrow = 2026-06-16 (Tuesday)
        # Today = 2026-06-15 (Monday)

    def _parse(self, s):
        return parse_user_datetime(s, now=self.fixed_now_utc)

    # ISO formats
    def test_iso_with_offset(self):
        result = self._parse("2026-06-18T09:00:00-04:00")
        self.assertEqual(result, datetime.datetime(2026, 6, 18, 13, 0, tzinfo=UTC))

    def test_iso_naive_assumes_eastern(self):
        result = self._parse("2026-06-18 09:00")
        self.assertEqual(result, datetime.datetime(2026, 6, 18, 13, 0, tzinfo=UTC))

    def test_iso_date_only(self):
        result = self._parse("2026-06-18")
        # Date only - time defaults to 00:00
        self.assertEqual(result, datetime.datetime(2026, 6, 18, 4, 0, tzinfo=UTC))

    def test_iso_with_z(self):
        result = self._parse("2026-06-18T13:00:00Z")
        self.assertEqual(result, datetime.datetime(2026, 6, 18, 13, 0, tzinfo=UTC))

    # Natural language
    def test_tomorrow_9am(self):
        # Fixed now: Mon 2026-06-15 23:30 EDT
        # Tomorrow = 2026-06-16 9:00 AM EDT
        # In UTC: 2026-06-16 13:00 UTC
        result = self._parse("tomorrow 9am")
        self.assertEqual(result, datetime.datetime(2026, 6, 16, 13, 0, tzinfo=UTC))

    def test_tomorrow_2pm(self):
        result = self._parse("tomorrow 2pm")
        self.assertEqual(result, datetime.datetime(2026, 6, 16, 18, 0, tzinfo=UTC))

    def test_tomorrow_14_30(self):
        result = self._parse("tomorrow 14:30")
        self.assertEqual(result, datetime.datetime(2026, 6, 16, 18, 30, tzinfo=UTC))

    def test_today(self):
        # Fixed now: Mon 2026-06-15 23:30 EDT
        # Today 9am = 2026-06-15 9:00 AM EDT
        # In UTC: 2026-06-15 13:00 UTC
        result = self._parse("today 9am")
        self.assertEqual(result, datetime.datetime(2026, 6, 15, 13, 0, tzinfo=UTC))

    def test_tomorrow_no_time_defaults_to_9am(self):
        result = self._parse("tomorrow")
        self.assertEqual(result, datetime.datetime(2026, 6, 16, 13, 0, tzinfo=UTC))

    def test_in_2_hours(self):
        # Fixed now: 2026-06-16 03:30 UTC
        # +2h = 2026-06-16 05:30 UTC
        result = self._parse("in 2 hours")
        self.assertEqual(result, datetime.datetime(2026, 6, 16, 5, 30, tzinfo=UTC))

    def test_in_30_minutes(self):
        result = self._parse("in 30 minutes")
        self.assertEqual(result, datetime.datetime(2026, 6, 16, 4, 0, tzinfo=UTC))

    def test_next_monday(self):
        # Fixed now: Mon 2026-06-15 (so next monday = 2026-06-22)
        result = self._parse("next monday 10am")
        self.assertEqual(result, datetime.datetime(2026, 6, 22, 14, 0, tzinfo=UTC))

    def test_next_friday(self):
        # From Monday 2026-06-15, "next friday" = this week's Friday = 2026-06-19
        result = self._parse("next friday 2pm")
        self.assertEqual(result, datetime.datetime(2026, 6, 19, 18, 0, tzinfo=UTC))

    # With timezone suffix
    def test_with_est_suffix(self):
        result = self._parse("2026-06-18 09:00 EST")
        self.assertEqual(result, datetime.datetime(2026, 6, 18, 14, 0, tzinfo=UTC))

    def test_with_edt_suffix(self):
        result = self._parse("2026-06-18 09:00 EDT")
        self.assertEqual(result, datetime.datetime(2026, 6, 18, 13, 0, tzinfo=UTC))

    def test_with_utc_suffix(self):
        result = self._parse("2026-06-18 13:00 UTC")
        self.assertEqual(result, datetime.datetime(2026, 6, 18, 13, 0, tzinfo=UTC))

    def test_with_et_suffix(self):
        # ET is treated as Eastern, which uses DST
        # In June, that's EDT
        result = self._parse("2026-06-18 09:00 ET")
        self.assertEqual(result, datetime.datetime(2026, 6, 18, 13, 0, tzinfo=UTC))

    # Edge cases
    def test_empty_string_raises(self):
        with self.assertRaises(ValueError):
            self._parse("")

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValueError):
            self._parse("   ")

    def test_garbage_raises(self):
        with self.assertRaises(ValueError):
            self._parse("not a real date")

    def test_invalid_type_raises(self):
        with self.assertRaises(TypeError):
            parse_user_datetime(123)
        with self.assertRaises(TypeError):
            parse_user_datetime(None)

    def test_whitespace_tolerated(self):
        result = self._parse("  tomorrow   9am  ")
        self.assertEqual(result, datetime.datetime(2026, 6, 16, 13, 0, tzinfo=UTC))

    def test_uppercase_tomorrow(self):
        result = self._parse("TOMORROW 9AM")
        self.assertEqual(result, datetime.datetime(2026, 6, 16, 13, 0, tzinfo=UTC))

    # DST boundary tests
    def test_dst_spring_forward_eastern_input(self):
        # March 8, 2026 9:00 AM Eastern - on this day Eastern is EDT
        # (spring forward at 2am)
        result = self._parse("2026-03-08 09:00")
        self.assertEqual(result, datetime.datetime(2026, 3, 8, 13, 0, tzinfo=UTC))

    def test_dst_fall_back_eastern_input(self):
        # November 1, 2026 9:00 AM Eastern - on this day Eastern is EST
        # (fall back at 2am)
        result = self._parse("2026-11-01 09:00")
        self.assertEqual(result, datetime.datetime(2026, 11, 1, 14, 0, tzinfo=UTC))


class TestFormatForDisplay(unittest.TestCase):
    """Test format_for_display output format."""

    def test_summer_edt(self):
        utc = datetime.datetime(2026, 6, 18, 13, 0, tzinfo=UTC)
        result = format_for_display(utc)
        self.assertEqual(result, "Jun 18, 2026 9:00 AM EDT")

    def test_winter_est(self):
        utc = datetime.datetime(2026, 1, 18, 14, 0, tzinfo=UTC)
        result = format_for_display(utc)
        self.assertEqual(result, "Jan 18, 2026 9:00 AM EST")

    def test_naive_assumed_utc(self):
        naive = datetime.datetime(2026, 6, 18, 13, 0)
        result = format_for_display(naive)
        self.assertEqual(result, "Jun 18, 2026 9:00 AM EDT")

    def test_already_eastern(self):
        # If we pass Eastern time, it should still display as Eastern
        eastern = datetime.datetime(2026, 6, 18, 9, 0, tzinfo=EASTERN)
        result = format_for_display(eastern)
        self.assertEqual(result, "Jun 18, 2026 9:00 AM EDT")

    def test_single_digit_hour_no_padding(self):
        utc = datetime.datetime(2026, 6, 18, 5, 0, tzinfo=UTC)
        result = format_for_display(utc)
        # 1 AM (not 01 AM)
        self.assertEqual(result, "Jun 18, 2026 1:00 AM EDT")

    def test_noon(self):
        utc = datetime.datetime(2026, 6, 18, 16, 0, tzinfo=UTC)
        result = format_for_display(utc)
        self.assertEqual(result, "Jun 18, 2026 12:00 PM EDT")

    def test_midnight(self):
        utc = datetime.datetime(2026, 6, 19, 4, 0, tzinfo=UTC)
        result = format_for_display(utc)
        self.assertEqual(result, "Jun 19, 2026 12:00 AM EDT")


class TestLeapYear(unittest.TestCase):
    """Test leap year handling."""

    def test_feb_29_2024(self):
        # 2024 is a leap year
        utc = eastern_to_utc(datetime.datetime(2024, 2, 29, 12, 0, tzinfo=EASTERN))
        self.assertEqual(utc, datetime.datetime(2024, 2, 29, 17, 0, tzinfo=UTC))

    def test_feb_29_2024_parse(self):
        result = parse_user_datetime("2024-02-29 12:00")
        self.assertEqual(result, datetime.datetime(2024, 2, 29, 17, 0, tzinfo=UTC))

    def test_feb_28_to_mar_1_in_leap_year(self):
        # Feb 28, 2024 + 1 day should be Feb 29, 2024
        feb28 = datetime.datetime(2024, 2, 28, 12, 0, tzinfo=UTC)
        next_day = feb28 + datetime.timedelta(days=1)
        self.assertEqual(next_day.day, 29)
        self.assertEqual(next_day.month, 2)


class TestCLI(unittest.TestCase):
    """Test CLI interface."""

    def _run_cli(self, args):
        import io
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            result = main(args)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_now_command(self):
        result, stdout, stderr = self._run_cli(["now"])
        self.assertEqual(result, 0)
        self.assertIn("UTC:", stdout)
        self.assertIn("Eastern:", stdout)
        self.assertIn("Display:", stdout)

    def test_convert_utc_to_eastern(self):
        result, stdout, stderr = self._run_cli([
            "convert", "--input", "2026-06-18T13:00:00", "--from", "utc", "--to", "eastern"
        ])
        self.assertEqual(result, 0)
        # ISO output includes the offset
        self.assertIn("09:00:00", stdout)
        self.assertIn("-04:00", stdout)  # EDT offset

    def test_convert_eastern_to_utc(self):
        result, stdout, stderr = self._run_cli([
            "convert", "--input", "2026-06-18T09:00:00", "--from", "eastern", "--to", "utc"
        ])
        self.assertEqual(result, 0)
        self.assertIn("13:00:00", stdout)

    def test_convert_invalid_input(self):
        result, stdout, stderr = self._run_cli([
            "convert", "--input", "not a date", "--from", "utc", "--to", "eastern"
        ])
        self.assertEqual(result, 1)
        self.assertIn("Error", stderr)

    def test_format_command(self):
        result, stdout, stderr = self._run_cli([
            "format", "--input", "2026-06-18T13:00:00Z"
        ])
        self.assertEqual(result, 0)
        self.assertIn("Jun 18, 2026 9:00 AM EDT", stdout)

    def test_parse_command(self):
        result, stdout, stderr = self._run_cli([
            "parse", "--input", "2026-06-18 09:00"
        ])
        self.assertEqual(result, 0)
        self.assertIn("UTC:", stdout)
        self.assertIn("13:00:00", stdout)
        self.assertIn("Display:", stdout)


class TestIntegration(unittest.TestCase):
    """End-to-end integration tests."""

    def test_parse_then_format(self):
        # Parse user input, then format it back
        utc = parse_user_datetime("tomorrow 9am")
        display = format_for_display(utc)
        # Display should include "AM EDT" or "AM EST"
        self.assertIn("AM", display)
        self.assertTrue(display.endswith("EDT") or display.endswith("EST"))

    def test_parse_then_convert(self):
        utc = parse_user_datetime("2026-06-18 09:00")
        eastern = utc_to_eastern(utc)
        # Should be 9 AM Eastern
        self.assertEqual(eastern.hour, 9)
        self.assertEqual(eastern.tzinfo, EASTERN)

    def test_dst_consistency(self):
        # Summer: 9 AM Eastern = 13:00 UTC
        summer = parse_user_datetime("2026-06-18 09:00")
        self.assertEqual(summer.hour, 13)

        # Winter: 9 AM Eastern = 14:00 UTC
        winter = parse_user_datetime("2026-01-18 09:00")
        self.assertEqual(winter.hour, 14)

        # The actual Eastern hour should always be 9
        summer_eastern = utc_to_eastern(summer)
        winter_eastern = utc_to_eastern(winter)
        self.assertEqual(summer_eastern.hour, 9)
        self.assertEqual(winter_eastern.hour, 9)


if __name__ == "__main__":
    unittest.main()
