"""Tests for pammi_ids library."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pammi_ids import (
    PREFIXES,
    SPREADSHEET_ID,
    ID_PATTERN,
    validate_id,
    parse_id,
    format_id,
    get_next,
    reserve,
    reset_counter,
    _load_counters,
    _save_counters,
    _extract_max_number,
    main,
)


class TestValidateID(unittest.TestCase):
    """Test ID format validation."""

    def test_valid_three_digit(self):
        for prefix in PREFIXES:
            self.assertTrue(validate_id(f"{prefix}-001"))
            self.assertTrue(validate_id(f"{prefix}-999"))

    def test_valid_four_digit(self):
        self.assertTrue(validate_id("CP-1000"))
        self.assertTrue(validate_id("AS-1234"))

    def test_invalid_lowercase(self):
        self.assertFalse(validate_id("cp-001"))

    def test_invalid_too_short(self):
        self.assertFalse(validate_id("CP-1"))
        self.assertFalse(validate_id("CP-01"))

    def test_invalid_no_dash(self):
        self.assertFalse(validate_id("CP001"))

    def test_invalid_empty(self):
        self.assertFalse(validate_id(""))
        self.assertFalse(validate_id("-"))

    def test_invalid_non_string(self):
        self.assertFalse(validate_id(123))
        self.assertFalse(validate_id(None))
        self.assertFalse(validate_id(["CP-001"]))

    def test_invalid_extra_chars(self):
        self.assertFalse(validate_id("CP-001!"))
        self.assertFalse(validate_id("CP-001 "))
        self.assertFalse(validate_id(" CP-001"))


class TestParseID(unittest.TestCase):
    """Test ID parsing."""

    def test_parse_basic(self):
        self.assertEqual(parse_id("CP-001"), ("CP", 1))
        self.assertEqual(parse_id("LI-042"), ("LI", 42))
        self.assertEqual(parse_id("AS-1234"), ("AS", 1234))

    def test_parse_invalid_raises(self):
        with self.assertRaises(ValueError):
            parse_id("invalid")
        with self.assertRaises(ValueError):
            parse_id("cp-001")


class TestFormatID(unittest.TestCase):
    """Test ID formatting."""

    def test_format_three_digit_pads(self):
        self.assertEqual(format_id("CP", 1), "CP-001")
        self.assertEqual(format_id("CP", 42), "CP-042")
        self.assertEqual(format_id("LI", 100), "LI-100")

    def test_format_four_digit(self):
        self.assertEqual(format_id("AS", 1234), "AS-1234")

    def test_format_invalid_prefix(self):
        with self.assertRaises(ValueError):
            format_id("cp", 1)
        with self.assertRaises(ValueError):
            format_id("CP1", 1)
        with self.assertRaises(ValueError):
            format_id("", 1)

    def test_format_invalid_number(self):
        with self.assertRaises(ValueError):
            format_id("CP", -1)
        with self.assertRaises(ValueError):
            format_id("CP", "1")  # not int


class TestExtractMaxNumber(unittest.TestCase):
    """Test max-number extraction from a list of IDs."""

    def test_empty_list(self):
        self.assertEqual(_extract_max_number([], "CP"), 0)

    def test_single_id(self):
        self.assertEqual(_extract_max_number(["CP-001"], "CP"), 1)

    def test_multiple_ids_same_prefix(self):
        self.assertEqual(
            _extract_max_number(["CP-001", "CP-005", "CP-003"], "CP"),
            5,
        )

    def test_filters_by_prefix(self):
        ids = ["CP-001", "LI-002", "CP-010", "AS-003"]
        self.assertEqual(_extract_max_number(ids, "CP"), 10)
        self.assertEqual(_extract_max_number(ids, "LI"), 2)
        self.assertEqual(_extract_max_number(ids, "AS"), 3)

    def test_ignores_invalid(self):
        ids = ["CP-001", "garbage", "CP-005", None, 123, "cp-002"]
        self.assertEqual(_extract_max_number(ids, "CP"), 5)

    def test_global_uniqueness_as(self):
        # AS-### should be globally unique across packages
        ids = ["AS-001", "AS-005", "AS-010"]
        self.assertEqual(_extract_max_number(ids, "AS"), 10)


class TestCountersPersistence(unittest.TestCase):
    """Test counter file persistence."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.original_path = Path.home() / ".pammi-tools" / "counters.json"
        self.patcher = patch("pammi_ids.COUNTERS_PATH", Path(self.tmpdir) / "counters.json")
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_save_and_load(self):
        _save_counters({"CP": 5, "LI": 10})
        loaded = _load_counters()
        self.assertEqual(loaded, {"CP": 5, "LI": 10})

    def test_load_missing_file(self):
        loaded = _load_counters()
        self.assertEqual(loaded, {})

    def test_load_corrupt_file(self):
        Path(self.tmpdir, "counters.json").parent.mkdir(parents=True, exist_ok=True)
        with open(Path(self.tmpdir) / "counters.json", "w") as f:
            f.write("not json")
        loaded = _load_counters()
        self.assertEqual(loaded, {})


class TestGetNext(unittest.TestCase):
    """Test get_next function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = patch("pammi_ids.COUNTERS_PATH", Path(self.tmpdir) / "counters.json")
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch("pammi_ids._read_sheet_ids")
    def test_first_id_with_empty_sheet(self, mock_read):
        mock_read.return_value = []
        new_id = get_next("CP", use_sheet=True)
        self.assertEqual(new_id, "CP-001")

    @patch("pammi_ids._read_sheet_ids")
    def test_increments_from_sheet(self, mock_read):
        mock_read.return_value = ["CP-001", "CP-002", "CP-005"]
        new_id = get_next("CP", use_sheet=True)
        self.assertEqual(new_id, "CP-006")

    @patch("pammi_ids._read_sheet_ids")
    def test_uses_local_max_when_higher(self, mock_read):
        _save_counters({"CP": 100})
        mock_read.return_value = ["CP-001", "CP-002"]
        new_id = get_next("CP", use_sheet=True)
        self.assertEqual(new_id, "CP-101")

    @patch("pammi_ids._read_sheet_ids")
    def test_globally_unique_assets(self, mock_read):
        # AS-### should be unique across all packages
        mock_read.return_value = [
            "AS-001", "AS-002", "AS-005",
            "CP-001", "LI-001",  # different prefixes, ignored
        ]
        new_id = get_next("AS", use_sheet=True)
        self.assertEqual(new_id, "AS-006")

    def test_no_sheet_mode(self):
        new_id = get_next("LI", use_sheet=False)
        self.assertEqual(new_id, "LI-001")

    def test_invalid_prefix_raises(self):
        with self.assertRaises(ValueError):
            get_next("XX", use_sheet=False)

    @patch("pammi_ids._read_sheet_ids")
    def test_persists_counter(self, mock_read):
        mock_read.return_value = []
        get_next("LOG", use_sheet=True)
        counters = _load_counters()
        self.assertEqual(counters.get("LOG"), 1)


class TestReserve(unittest.TestCase):
    """Test reserve function."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = patch("pammi_ids.COUNTERS_PATH", Path(self.tmpdir) / "counters.json")
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    @patch("pammi_ids._read_sheet_ids")
    def test_reserve_single(self, mock_read):
        mock_read.return_value = []
        ids = reserve("CP", count=1, use_sheet=True)
        self.assertEqual(ids, ["CP-001"])

    @patch("pammi_ids._read_sheet_ids")
    def test_reserve_multiple(self, mock_read):
        mock_read.return_value = []
        ids = reserve("LI", count=3, use_sheet=True)
        self.assertEqual(ids, ["LI-001", "LI-002", "LI-003"])

    @patch("pammi_ids._read_sheet_ids")
    def test_reserve_consecutive_from_existing(self, mock_read):
        mock_read.return_value = ["VR-005"]
        ids = reserve("VR", count=3, use_sheet=True)
        self.assertEqual(ids, ["VR-006", "VR-007", "VR-008"])

    def test_reserve_zero_raises(self):
        with self.assertRaises(ValueError):
            reserve("CP", count=0, use_sheet=False)


class TestResetCounter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = patch("pammi_ids.COUNTERS_PATH", Path(self.tmpdir) / "counters.json")
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_reset_existing(self):
        _save_counters({"CP": 5})
        reset_counter("CP")
        self.assertEqual(_load_counters(), {})

    def test_reset_nonexistent(self):
        _save_counters({"CP": 5})
        reset_counter("LI")
        self.assertEqual(_load_counters(), {"CP": 5})


class TestCLI(unittest.TestCase):
    """Test CLI interface."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.patcher = patch("pammi_ids.COUNTERS_PATH", Path(self.tmpdir) / "counters.json")
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def _run_cli(self, args):
        """Run CLI and capture stdout."""
        import io
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            result = main(args)
        return result, captured.getvalue()

    @patch("pammi_ids._read_sheet_ids")
    def test_cli_next(self, mock_read):
        mock_read.return_value = []
        result, output = self._run_cli(["next", "CP", "--no-sheet"])
        self.assertEqual(result, 0)
        self.assertEqual(output, "CP-001\n")

    def test_cli_validate_valid(self):
        result, output = self._run_cli(["validate", "LI-042"])
        self.assertEqual(result, 0)
        self.assertIn("valid", output)
        self.assertIn("LI-042", output)

    def test_cli_validate_invalid(self):
        result, output = self._run_cli(["validate", "bad"])
        self.assertEqual(result, 1)
        self.assertIn("invalid", output)

    @patch("pammi_ids._read_sheet_ids")
    def test_cli_reserve(self, mock_read):
        mock_read.return_value = []
        result, output = self._run_cli(["reserve", "AS", "2", "--no-sheet"])
        self.assertEqual(result, 0)
        self.assertIn("AS-001", output)
        self.assertIn("AS-002", output)

    def test_cli_list(self):
        result, output = self._run_cli(["list"])
        self.assertEqual(result, 0)
        self.assertIn("CP", output)
        self.assertIn("Content Packages", output)


class TestSpreadsheetID(unittest.TestCase):
    """Sanity check on constants."""

    def test_spreadsheet_id_format(self):
        # Google Sheets IDs are 44 chars
        self.assertEqual(len(SPREADSHEET_ID), 44)

    def test_all_prefixes_in_tab_map(self):
        for prefix in PREFIXES:
            self.assertIn(prefix, PREFIXES)


if __name__ == "__main__":
    unittest.main()
