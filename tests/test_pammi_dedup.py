"""Tests for pammi_dedup library."""

import datetime
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pammi_dedup import (
    SPREADSHEET_ID,
    PLATFORM_TO_TAB,
    ACTIVE_STATUSES,
    normalize_topic,
    compute_dedup_key,
    find_duplicate,
    main,
)


class TestNormalizeTopic(unittest.TestCase):
    """Test topic normalization rules."""

    def test_simple_lowercase(self):
        self.assertEqual(normalize_topic("Hello World"), "hello-world")

    def test_strip_whitespace(self):
        self.assertEqual(normalize_topic("  hello  "), "hello")

    def test_collapse_spaces(self):
        self.assertEqual(normalize_topic("hello    world"), "hello-world")

    def test_remove_punctuation(self):
        self.assertEqual(normalize_topic("Hello, World!"), "hello-world")

    def test_remove_special_chars(self):
        self.assertEqual(normalize_topic("Foo@Bar#Baz$Qux"), "foobarbazqux")

    def test_underscores_to_spaces_to_dashes(self):
        self.assertEqual(normalize_topic("foo_bar_baz"), "foo-bar-baz")

    def test_keeps_dashes(self):
        self.assertEqual(normalize_topic("foo-bar"), "foo-bar")

    def test_keeps_numbers(self):
        self.assertEqual(normalize_topic("Top 10 Tips"), "top-10-tips")

    def test_trims_leading_trailing_dashes(self):
        self.assertEqual(normalize_topic("  --leading--  "), "leading")

    def test_keeps_inner_dashes(self):
        self.assertEqual(normalize_topic("foo--bar"), "foo--bar")

    def test_removes_emojis(self):
        # Emojis are not in the keep set
        self.assertEqual(normalize_topic("Hello 👋 World 🌍"), "hello-world")

    def test_removes_question_marks(self):
        self.assertEqual(normalize_topic("What is AI?"), "what-is-ai")

    def test_removes_apostrophes(self):
        self.assertEqual(normalize_topic("What's the deal?"), "whats-the-deal")

    def test_removes_slashes(self):
        self.assertEqual(normalize_topic("C++ vs Go/Rust"), "c-vs-gorust")

    def test_real_world_example(self):
        self.assertEqual(
            normalize_topic("Queues for AI Agents!"),
            "queues-for-ai-agents"
        )

    def test_already_normalized(self):
        self.assertEqual(normalize_topic("already-normalized"), "already-normalized")

    def test_only_punctuation(self):
        self.assertEqual(normalize_topic("!!!"), "")

    def test_only_spaces(self):
        self.assertEqual(normalize_topic("     "), "")

    def test_empty_string(self):
        self.assertEqual(normalize_topic(""), "")

    def test_mixed_case_with_punct(self):
        self.assertEqual(
            normalize_topic("Don't Repeat Yourself (DRY) Principle"),
            "dont-repeat-yourself-dry-principle"
        )

    def test_unicode_letters_become_ascii(self):
        # Non-ASCII gets removed by the keep regex
        self.assertEqual(normalize_topic("café"), "caf")

    def test_invalid_input_type(self):
        with self.assertRaises(TypeError):
            normalize_topic(123)
        with self.assertRaises(TypeError):
            normalize_topic(None)
        with self.assertRaises(TypeError):
            normalize_topic([])


class TestComputeDedupKey(unittest.TestCase):
    """Test dedup_key computation."""

    def test_basic(self):
        self.assertEqual(
            compute_dedup_key("linkedin", "Queues for AI Agents!", "2026-06-18"),
            "linkedin:queues-for-ai-agents:2026-06-18"
        )

    def test_different_date_different_key(self):
        k1 = compute_dedup_key("linkedin", "Topic", "2026-06-18")
        k2 = compute_dedup_key("linkedin", "Topic", "2026-06-19")
        self.assertNotEqual(k1, k2)

    def test_different_platform_different_key(self):
        k1 = compute_dedup_key("linkedin", "Topic", "2026-06-18")
        k2 = compute_dedup_key("twitter", "Topic", "2026-06-18")
        self.assertNotEqual(k1, k2)

    def test_similar_topics_same_key(self):
        # Both should normalize to the same thing
        k1 = compute_dedup_key("linkedin", "Queues for AI Agents!", "2026-06-18")
        k2 = compute_dedup_key("linkedin", "Queues for AI Agents", "2026-06-18")
        k3 = compute_dedup_key("linkedin", "  queues for ai agents?!  ", "2026-06-18")
        self.assertEqual(k1, k2)
        self.assertEqual(k2, k3)

    def test_platform_lowercased(self):
        k = compute_dedup_key("LinkedIn", "Topic", "2026-06-18")
        self.assertTrue(k.startswith("linkedin:"))

    def test_default_date_is_today(self):
        k = compute_dedup_key("linkedin", "Topic")
        today = datetime.date.today().isoformat()
        self.assertTrue(k.endswith(f":{today}"))

    def test_invalid_date_format(self):
        with self.assertRaises(ValueError):
            compute_dedup_key("linkedin", "Topic", "06/18/2026")
        with self.assertRaises(ValueError):
            compute_dedup_key("linkedin", "Topic", "2026-13-01")
        with self.assertRaises(ValueError):
            compute_dedup_key("linkedin", "Topic", "not-a-date")

    def test_empty_platform(self):
        with self.assertRaises(ValueError):
            compute_dedup_key("", "Topic", "2026-06-18")

    def test_empty_topic_allowed(self):
        # Empty topic should still produce a key
        k = compute_dedup_key("linkedin", "", "2026-06-18")
        self.assertEqual(k, "linkedin::2026-06-18")


class TestFindDuplicate(unittest.TestCase):
    """Test find_duplicate function with mocked Sheet reads."""

    @patch("pammi_dedup._read_sheet_columns")
    def test_no_duplicates_empty_sheet(self, mock_read):
        mock_read.return_value = {
            "post_id": [],
            "dedup_key": [],
            "status": [],
            "topic": [],
        }
        result = find_duplicate("linkedin", "Brand New Topic", "2026-06-18")
        self.assertIsNone(result)

    @patch("pammi_dedup._read_sheet_columns")
    def test_finds_duplicate(self, mock_read):
        mock_read.return_value = {
            "post_id": ["LI-001", "LI-002"],
            "dedup_key": [
                "linkedin:other-topic:2026-06-17",
                "linkedin:queues-for-ai-agents:2026-06-18",
            ],
            "status": ["POSTED", "READY"],
            "topic": ["Other", "Queues for AI Agents"],
        }
        result = find_duplicate("linkedin", "Queues for AI Agents!", "2026-06-18")
        self.assertIsNotNone(result)
        self.assertEqual(result["post_id"], "LI-002")
        self.assertEqual(result["status"], "READY")

    @patch("pammi_dedup._read_sheet_columns")
    def test_skips_skipped_status(self, mock_read):
        mock_read.return_value = {
            "post_id": ["LI-001"],
            "dedup_key": ["linkedin:queues-for-ai-agents:2026-06-18"],
            "status": ["SKIPPED"],
            "topic": ["Queues for AI Agents"],
        }
        result = find_duplicate("linkedin", "Queues for AI Agents!", "2026-06-18")
        self.assertIsNone(result)

    @patch("pammi_dedup._read_sheet_columns")
    def test_skips_archived_status(self, mock_read):
        mock_read.return_value = {
            "post_id": ["LI-001"],
            "dedup_key": ["linkedin:queues-for-ai-agents:2026-06-18"],
            "status": ["ARCHIVED"],
            "topic": ["Queues"],
        }
        result = find_duplicate("linkedin", "Queues for AI Agents!", "2026-06-18")
        self.assertIsNone(result)

    @patch("pammi_dedup._read_sheet_columns")
    def test_includes_posted_status(self, mock_read):
        # POSTED counts as duplicate (don't re-post)
        mock_read.return_value = {
            "post_id": ["LI-001"],
            "dedup_key": ["linkedin:queues-for-ai-agents:2026-06-18"],
            "status": ["POSTED"],
            "topic": ["Queues"],
        }
        result = find_duplicate("linkedin", "Queues for AI Agents!", "2026-06-18")
        self.assertIsNotNone(result)

    @patch("pammi_dedup._read_sheet_columns")
    def test_different_date_no_match(self, mock_read):
        mock_read.return_value = {
            "post_id": ["LI-001"],
            "dedup_key": ["linkedin:queues-for-ai-agents:2026-06-17"],
            "status": ["POSTED"],
            "topic": ["Queues"],
        }
        result = find_duplicate("linkedin", "Queues for AI Agents!", "2026-06-18")
        self.assertIsNone(result)

    @patch("pammi_dedup._read_sheet_columns")
    def test_includes_row_number(self, mock_read):
        mock_read.return_value = {
            "post_id": ["LI-001"],
            "dedup_key": ["linkedin:topic:2026-06-18"],
            "status": ["READY"],
            "topic": ["Topic"],
        }
        result = find_duplicate("linkedin", "Topic", "2026-06-18")
        self.assertEqual(result["row"], 2)  # Row 2 in sheet (1-indexed, skip header)

    def test_unsupported_platform(self):
        with self.assertRaises(ValueError):
            find_duplicate("myspace", "Topic", "2026-06-18")


class TestActiveStatuses(unittest.TestCase):
    """Sanity check on active status set."""

    def test_contains_key_statuses(self):
        self.assertIn("DRAFT", ACTIVE_STATUSES)
        self.assertIn("READY", ACTIVE_STATUSES)
        self.assertIn("POSTED", ACTIVE_STATUSES)

    def test_does_not_contain_inactive(self):
        self.assertNotIn("SKIPPED", ACTIVE_STATUSES)
        self.assertNotIn("ARCHIVED", ACTIVE_STATUSES)


class TestPlatformMapping(unittest.TestCase):
    """Sanity check on platform → tab mappings."""

    def test_linkedin_mapped(self):
        self.assertEqual(PLATFORM_TO_TAB["linkedin"], "LinkedIn")


class TestCLI(unittest.TestCase):
    """Test CLI interface."""

    def _run_cli(self, args):
        import io
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            result = main(args)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_compute_basic(self):
        result, stdout, stderr = self._run_cli([
            "compute", "--platform", "linkedin",
            "--topic", "Queues for AI Agents!",
            "--date", "2026-06-18",
        ])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.strip(), "linkedin:queues-for-ai-agents:2026-06-18")

    def test_compute_no_date(self):
        result, stdout, stderr = self._run_cli([
            "compute", "--platform", "linkedin", "--topic", "Hello World",
        ])
        self.assertEqual(result, 0)
        # Should end with today's date
        today = datetime.date.today().isoformat()
        self.assertTrue(stdout.strip().endswith(f":{today}"))

    def test_compute_invalid_date(self):
        result, stdout, stderr = self._run_cli([
            "compute", "--platform", "linkedin", "--topic", "Topic",
            "--date", "06/18/2026",
        ])
        self.assertEqual(result, 1)
        self.assertIn("Error", stderr)

    def test_normalize(self):
        result, stdout, stderr = self._run_cli([
            "normalize", "Hello, World!",
        ])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.strip(), "hello-world")

    @patch("pammi_dedup._read_sheet_columns")
    def test_check_no_duplicate(self, mock_read):
        mock_read.return_value = {
            "post_id": [], "dedup_key": [], "status": [], "topic": [],
        }
        result, stdout, stderr = self._run_cli([
            "check", "--platform", "linkedin",
            "--topic", "New Topic", "--date", "2026-06-18",
        ])
        self.assertEqual(result, 0)
        self.assertEqual(stdout.strip(), "null")

    @patch("pammi_dedup._read_sheet_columns")
    def test_check_found(self, mock_read):
        mock_read.return_value = {
            "post_id": ["LI-042"],
            "dedup_key": ["linkedin:new-topic:2026-06-18"],
            "status": ["READY"],
            "topic": ["New Topic"],
        }
        result, stdout, stderr = self._run_cli([
            "check", "--platform", "linkedin",
            "--topic", "New Topic", "--date", "2026-06-18",
        ])
        self.assertEqual(result, 0)
        self.assertIn("LI-042", stdout)
        self.assertIn("READY", stdout)


if __name__ == "__main__":
    unittest.main()
