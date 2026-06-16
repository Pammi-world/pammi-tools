"""Tests for pammi_drive library."""

import base64
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pammi_drive import (
    FOLDER_STRUCTURE,
    PLATFORM_TO_KEY,
    load_config,
    save_config,
    find_folder,
    create_folder,
    get_or_create_folder,
    get_target_folder,
    upload_file,
    main,
)


class TestConfigIO(unittest.TestCase):
    """Test config file read/write."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = Path(self.tmpdir) / "drive-config.json"

    def test_load_missing_returns_empty(self):
        result = load_config(self.config_path)
        self.assertEqual(result, {})

    def test_save_and_load(self):
        data = {"root": {"id": "abc123", "name": "Root"}}
        save_config(data, self.config_path)
        loaded = load_config(self.config_path)
        self.assertEqual(loaded, data)

    def test_load_corrupt_returns_empty(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w") as f:
            f.write("not json")
        result = load_config(self.config_path)
        self.assertEqual(result, {})


class TestFolderStructure(unittest.TestCase):
    """Test folder structure definitions."""

    def test_has_root(self):
        keys = [key for _, key in FOLDER_STRUCTURE]
        self.assertIn("root", keys)
        self.assertIn("source", keys)
        self.assertIn("exports", keys)
        self.assertIn("exports_linkedin", keys)
        self.assertIn("exports_blogs", keys)
        self.assertIn("exports_shorts", keys)
        self.assertIn("exports_reels", keys)
        self.assertIn("exports_x", keys)

    def test_platform_to_key(self):
        self.assertEqual(PLATFORM_TO_KEY["linkedin"], "exports_linkedin")
        self.assertEqual(PLATFORM_TO_KEY["blog"], "exports_blogs")
        self.assertEqual(PLATFORM_TO_KEY["blogs"], "exports_blogs")
        self.assertEqual(PLATFORM_TO_KEY["short"], "exports_shorts")
        self.assertEqual(PLATFORM_TO_KEY["reel"], "exports_reels")
        self.assertEqual(PLATFORM_TO_KEY["x"], "exports_x")
        self.assertEqual(PLATFORM_TO_KEY["twitter"], "exports_x")


class TestFindFolder(unittest.TestCase):
    @patch("pammi_drive._run_composio")
    def test_find_folder_found(self, mock_run):
        mock_run.return_value = {
            "successful": True,
            "data": {"files": [{"id": "abc", "name": "Pammi"}]},
        }
        result = find_folder("Pammi")
        self.assertEqual(result["id"], "abc")
        mock_run.assert_called_once()
        call_data = mock_run.call_args[0][1]
        self.assertEqual(call_data["name_exact"], "Pammi")

    @patch("pammi_drive._run_composio")
    def test_find_folder_with_parent(self, mock_run):
        mock_run.return_value = {
            "successful": True,
            "data": {"files": [{"id": "abc", "name": "exports"}]},
        }
        result = find_folder("exports", parent_id="root123")
        call_data = mock_run.call_args[0][1]
        self.assertEqual(call_data["parent_folder_id"], "root123")

    @patch("pammi_drive._run_composio")
    def test_find_folder_not_found(self, mock_run):
        mock_run.return_value = {"successful": True, "data": {"files": []}}
        result = find_folder("Pammi")
        self.assertIsNone(result)

    @patch("pammi_drive._run_composio")
    def test_find_folder_failed(self, mock_run):
        mock_run.return_value = {"successful": False}
        result = find_folder("Pammi")
        self.assertIsNone(result)


class TestCreateFolder(unittest.TestCase):
    @patch("pammi_drive._run_composio")
    def test_create_folder(self, mock_run):
        mock_run.return_value = {
            "successful": True,
            "data": {"id": "new123", "name": "Test", "webViewLink": "https://drive.google.com/..."},
        }
        result = create_folder("Test")
        self.assertEqual(result["id"], "new123")
        self.assertEqual(result["name"], "Test")

    @patch("pammi_drive._run_composio")
    def test_create_folder_nested_id(self, mock_run):
        # Sometimes the id is nested
        mock_run.return_value = {
            "successful": True,
            "data": {"folder": {"id": "nested123", "name": "Test"}},
        }
        result = create_folder("Test")
        self.assertEqual(result["id"], "nested123")

    @patch("pammi_drive._run_composio")
    def test_create_folder_failed(self, mock_run):
        mock_run.return_value = {"successful": False, "error": "Permission denied"}
        with self.assertRaises(RuntimeError):
            create_folder("Test")


class TestGetOrCreateFolder(unittest.TestCase):
    @patch("pammi_drive.find_folder")
    def test_get_existing(self, mock_find):
        mock_find.return_value = {"id": "existing", "name": "Pammi"}
        result = get_or_create_folder("Pammi")
        self.assertEqual(result["id"], "existing")
        mock_find.assert_called_once()

    @patch("pammi_drive.create_folder")
    @patch("pammi_drive.find_folder")
    def test_create_when_missing(self, mock_find, mock_create):
        mock_find.return_value = None
        mock_create.return_value = {"id": "new", "name": "Pammi"}
        result = get_or_create_folder("Pammi")
        self.assertEqual(result["id"], "new")
        mock_create.assert_called_once()


class TestGetTargetFolder(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = Path(self.tmpdir) / "drive-config.json"

    def test_get_linkedin(self):
        config = {"exports_linkedin": {"id": "li123", "name": "linkedin"}}
        save_config(config, self.config_path)
        result = get_target_folder("linkedin", self.config_path)
        self.assertEqual(result["id"], "li123")

    def test_get_blog(self):
        config = {"exports_blogs": {"id": "blog123"}}
        save_config(config, self.config_path)
        result = get_target_folder("blog", self.config_path)
        self.assertEqual(result["id"], "blog123")

    def test_get_twitter_aliases_to_x(self):
        config = {"exports_x": {"id": "x123"}}
        save_config(config, self.config_path)
        result = get_target_folder("twitter", self.config_path)
        self.assertEqual(result["id"], "x123")

    def test_unknown_platform_raises(self):
        with self.assertRaises(ValueError):
            get_target_folder("myspace", self.config_path)

    def test_unconfigured_raises(self):
        with self.assertRaises(RuntimeError):
            get_target_folder("linkedin", self.config_path)


class TestUploadFile(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = Path(self.tmpdir) / "drive-config.json"
        self.test_file = Path(self.tmpdir) / "test.png"
        self.test_file.write_bytes(b"fake png content")

        config = {"exports_linkedin": {"id": "li123", "name": "linkedin"}}
        save_config(config, self.config_path)

    @patch("pammi_drive._run_composio")
    def test_upload_success(self, mock_run):
        mock_run.return_value = {
            "successful": True,
            "data": {
                "id": "file_abc",
                "webViewLink": "https://drive.google.com/file/file_abc",
                "name": "test.png",
            },
        }
        result = upload_file(str(self.test_file), "linkedin", self.config_path)
        self.assertEqual(result["file_id"], "file_abc")
        self.assertIn("drive_url", result)
        self.assertEqual(result["mime_type"], "image/png")

    def test_upload_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            upload_file("/nonexistent.png", "linkedin", self.config_path)

    @patch("pammi_drive._run_composio")
    def test_upload_handles_unknown_mime(self, mock_run):
        # Create file with no extension
        weird_file = Path(self.tmpdir) / "weirdfile"
        weird_file.write_bytes(b"data")
        mock_run.return_value = {
            "successful": True,
            "data": {"id": "file_xyz", "webViewLink": "https://..."},
        }
        result = upload_file(str(weird_file), "linkedin", self.config_path)
        # Default mime type
        self.assertEqual(result["mime_type"], "application/octet-stream")


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = Path(self.tmpdir) / "drive-config.json"

    def _run_cli(self, args):
        import io
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), \
             patch("sys.stderr", stderr), \
             patch("pammi_drive.DEFAULT_CONFIG", self.config_path):
            result = main(args)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_show_empty(self):
        result, stdout, stderr = self._run_cli(["show"])
        self.assertEqual(result, 0)
        # Config has placeholder entries, so it should not be literally "{}"
        # but should be valid JSON
        import json
        data = json.loads(stdout.strip())
        self.assertIsInstance(data, dict)

    def test_upload_missing_file(self):
        result, stdout, stderr = self._run_cli([
            "upload", "--file", "/nonexistent.png", "--platform", "linkedin"
        ])
        self.assertEqual(result, 1)
        self.assertIn("Error", stderr)


if __name__ == "__main__":
    unittest.main()
