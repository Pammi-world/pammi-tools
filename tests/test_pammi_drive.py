"""Tests for pammi_drive library (mocks Composio, no real Drive calls)."""

import base64
import io
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
    get_target_folder,
    upload_file,
    main,
)
from pammi_drive.client import (
    find_folder,
    create_folder,
    setup_folders,
    get_or_create_folder,
)


class TestConfigIO(unittest.TestCase):
    """Test config file read/write."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = Path(self.tmpdir) / "drive-config.json"

    def test_load_nonexistent_returns_empty(self):
        result = load_config(self.config_path)
        self.assertEqual(result, {})

    def test_save_and_load(self):
        config = {"root": {"id": "abc", "name": "Pammi"}}
        save_config(config, self.config_path)
        result = load_config(self.config_path)
        self.assertEqual(result, config)

    def test_load_existing(self):
        self.config_path.write_text(json.dumps({"linkedin": {"id": "x"}}))
        result = load_config(self.config_path)
        self.assertEqual(result, {"linkedin": {"id": "x"}})

    def test_save_creates_parent_dirs(self):
        nested = Path(self.tmpdir) / "deep" / "nested" / "config.json"
        save_config({"k": "v"}, nested)
        self.assertTrue(nested.exists())


class TestPlatformMapping(unittest.TestCase):
    """Test platform → config key mapping."""

    def test_linkedin(self):
        self.assertEqual(PLATFORM_TO_KEY["linkedin"], "linkedin")

    def test_blog_aliases(self):
        self.assertEqual(PLATFORM_TO_KEY["blog"], "blogs")
        self.assertEqual(PLATFORM_TO_KEY["blogs"], "blogs")

    def test_short_aliases(self):
        self.assertEqual(PLATFORM_TO_KEY["short"], "shorts")
        self.assertEqual(PLATFORM_TO_KEY["shorts"], "shorts")

    def test_reel_aliases(self):
        self.assertEqual(PLATFORM_TO_KEY["reel"], "reels")
        self.assertEqual(PLATFORM_TO_KEY["reels"], "reels")

    def test_x_aliases(self):
        self.assertEqual(PLATFORM_TO_KEY["x"], "x")
        self.assertEqual(PLATFORM_TO_KEY["twitter"], "x")


class TestFolderStructure(unittest.TestCase):
    """Test FOLDER_STRUCTURE definition."""

    def test_has_8_folders(self):
        self.assertEqual(len(FOLDER_STRUCTURE), 8)

    def test_root_folder_first(self):
        path_parts, key = FOLDER_STRUCTURE[0]
        self.assertEqual(path_parts, ["Pammi Content System"])
        self.assertEqual(key, "root")

    def test_5_platform_folders(self):
        platform_keys = ["linkedin", "blogs", "shorts", "reels", "x"]
        for key in platform_keys:
            found = any(k == key for _, k in FOLDER_STRUCTURE)
            self.assertTrue(found, f"Missing platform folder: {key}")


class TestFindFolder(unittest.TestCase):
    """Test find_folder (mocks Composio)."""

    @patch("pammi_drive.client._run_composio")
    def test_find_folder_found(self, mock_run):
        mock_run.return_value = {
            "files": [{"id": "abc", "name": "Pammi"}]
        }
        result = find_folder("Pammi")
        self.assertEqual(result["id"], "abc")
        # Verify it called the right slug
        mock_run.assert_called_once()
        args, _ = mock_run.call_args
        self.assertEqual(args[0], "GOOGLEDRIVE_FIND_FOLDER")

    @patch("pammi_drive.client._run_composio")
    def test_find_folder_with_parent(self, mock_run):
        mock_run.return_value = {"files": []}
        find_folder("exports", parent_id="root123")
        # Verify the parent filter was used
        args, _ = mock_run.call_args
        data = args[1]
        self.assertIn("root123", data["query"])

    @patch("pammi_drive.client._run_composio")
    def test_find_folder_not_found(self, mock_run):
        mock_run.return_value = {"files": []}
        result = find_folder("Pammi")
        self.assertIsNone(result)

    @patch("pammi_drive.client._run_composio")
    def test_find_folder_failed_returns_none(self, mock_run):
        mock_run.side_effect = RuntimeError("API down")
        result = find_folder("Pammi")
        self.assertIsNone(result)


class TestCreateFolder(unittest.TestCase):
    """Test create_folder (mocks Composio)."""

    @patch("pammi_drive.client._run_composio")
    def test_create_folder(self, mock_run):
        mock_run.return_value = {"id": "new_folder", "name": "Pammi"}
        result = create_folder("Pammi")
        self.assertEqual(result["id"], "new_folder")
        # Verify it called CREATE_FOLDER
        args, _ = mock_run.call_args
        self.assertEqual(args[0], "GOOGLEDRIVE_CREATE_FOLDER")

    @patch("pammi_drive.client._run_composio")
    def test_create_folder_with_parent(self, mock_run):
        mock_run.return_value = {"id": "child", "name": "exports"}
        create_folder("exports", parent_id="root_id")
        args, _ = mock_run.call_args
        data = args[1]
        self.assertEqual(data["parent_id"], "root_id")
        self.assertEqual(data["name"], "exports")


class TestGetOrCreateFolder(unittest.TestCase):
    """Test get_or_create_folder (idempotent helper)."""

    @patch("pammi_drive.client.find_folder")
    def test_get_existing(self, mock_find):
        mock_find.return_value = {"id": "existing", "name": "Pammi"}
        result = get_or_create_folder("Pammi")
        self.assertEqual(result["id"], "existing")
        mock_find.assert_called_once()

    @patch("pammi_drive.client.create_folder")
    @patch("pammi_drive.client.find_folder")
    def test_create_when_missing(self, mock_find, mock_create):
        mock_find.return_value = None
        mock_create.return_value = {"id": "new", "name": "Pammi"}
        result = get_or_create_folder("Pammi")
        self.assertEqual(result["id"], "new")
        mock_create.assert_called_once()


class TestGetTargetFolder(unittest.TestCase):
    """Test get_target_folder."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = Path(self.tmpdir) / "drive-config.json"

    def test_get_linkedin(self):
        config = {"linkedin": {"id": "li123", "name": "linkedin"}}
        save_config(config, self.config_path)
        result = get_target_folder("linkedin", self.config_path)
        self.assertEqual(result["id"], "li123")

    def test_get_blog_alias(self):
        config = {"blogs": {"id": "blog123", "name": "blogs"}}
        save_config(config, self.config_path)
        result = get_target_folder("blog", self.config_path)
        self.assertEqual(result["id"], "blog123")

    def test_get_x_via_twitter_alias(self):
        config = {"x": {"id": "x123", "name": "x"}}
        save_config(config, self.config_path)
        result = get_target_folder("twitter", self.config_path)
        self.assertEqual(result["id"], "x123")

    def test_unknown_platform_raises(self):
        with self.assertRaises(ValueError) as ctx:
            get_target_folder("myspace", self.config_path)
        self.assertIn("myspace", str(ctx.exception))

    def test_unconfigured_folder_raises(self):
        # Config doesn't have linkedin
        save_config({}, self.config_path)
        with self.assertRaises(RuntimeError) as ctx:
            get_target_folder("linkedin", self.config_path)
        self.assertIn("not configured", str(ctx.exception).lower())


class TestUploadFile(unittest.TestCase):
    """Test upload_file (mocks Composio)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.test_file = Path(self.tmpdir) / "test.png"
        self.test_file.write_bytes(b"\x89PNG\r\n\x1a\n fake png data")
        self.config_path = Path(self.tmpdir) / "drive-config.json"

    def _setup_config(self):
        config = {"linkedin": {"id": "li123", "name": "linkedin"}}
        save_config(config, self.config_path)

    @patch("pammi_drive.client._run_composio")
    def test_upload_success(self, mock_run):
        self._setup_config()
        mock_run.return_value = {"id": "file_abc", "webViewLink": "https://..."}
        result = upload_file(str(self.test_file), "linkedin", self.config_path)
        self.assertEqual(result["file_id"], "file_abc")
        self.assertIn("drive.google.com", result["drive_url"])
        self.assertEqual(result["mime_type"], "image/png")
        self.assertEqual(result["folder_id"], "li123")
        self.assertEqual(result["name"], "test.png")

    def test_upload_file_not_found(self):
        self._setup_config()
        with self.assertRaises(FileNotFoundError):
            upload_file("/nonexistent.png", "linkedin", self.config_path)

    @patch("pammi_drive.client._run_composio")
    def test_upload_default_mime(self, mock_run):
        self._setup_config()
        # No extension
        weird_file = Path(self.tmpdir) / "noext"
        weird_file.write_bytes(b"data")
        mock_run.return_value = {"id": "file_xyz"}
        result = upload_file(str(weird_file), "linkedin", self.config_path)
        self.assertEqual(result["mime_type"], "application/octet-stream")

    @patch("pammi_drive.client._run_composio")
    def test_upload_sends_base64(self, mock_run):
        self._setup_config()
        mock_run.return_value = {"id": "file_q"}
        upload_file(str(self.test_file), "linkedin", self.config_path)
        args, _ = mock_run.call_args
        data = args[1]
        self.assertIn("content_base64", data)
        # Verify the base64 decodes to the original
        decoded = base64.b64decode(data["content_base64"])
        self.assertEqual(decoded, self.test_file.read_bytes())

    @patch("pammi_drive.client._run_composio")
    def test_upload_sends_parent_folder_id(self, mock_run):
        self._setup_config()
        mock_run.return_value = {"id": "file_x"}
        upload_file(str(self.test_file), "linkedin", self.config_path)
        args, _ = mock_run.call_args
        data = args[1]
        self.assertEqual(data["parent_folder_id"], "li123")

    @patch("pammi_drive.client._run_composio")
    def test_upload_no_file_id_in_response_raises(self, mock_run):
        self._setup_config()
        mock_run.return_value = {"name": "test.png"}  # No id field
        with self.assertRaises(RuntimeError):
            upload_file(str(self.test_file), "linkedin", self.config_path)


class TestCLI(unittest.TestCase):
    """Test CLI commands."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = Path(self.tmpdir) / "drive-config.json"

    def _run_cli(self, args, config_in_path=True):
        stdout = io.StringIO()
        stderr = io.StringIO()
        cli_args = []
        if config_in_path:
            cli_args.extend(["--config", str(self.config_path)])
        cli_args.extend(args)
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            result = main(cli_args)
        return result, stdout.getvalue(), stderr.getvalue()

    def test_list_folders_shows_keys(self):
        # Save a config
        config = {
            "root": {"id": "r1", "name": "Pammi Content System"},
            "source": {"id": "s1", "name": "source"},
            "exports": {"id": "e1", "name": "exports"},
            "linkedin": {"id": "li1", "name": "linkedin"},
            "blogs": {"id": "b1", "name": "blogs"},
            "shorts": {"id": "sh1", "name": "shorts"},
            "reels": {"id": "re1", "name": "reels"},
            "x": {"id": "x1", "name": "x"},
        }
        save_config(config, self.config_path)

        result, stdout, stderr = self._run_cli(["list-folders"])
        self.assertEqual(result, 0)
        self.assertIn("root", stdout)
        self.assertIn("linkedin", stdout)
        self.assertIn("li1", stdout)

    def test_list_folders_show_alias(self):
        config = {"linkedin": {"id": "li1", "name": "linkedin"}}
        save_config(config, self.config_path)
        result, stdout, _ = self._run_cli(["show"])
        self.assertEqual(result, 0)
        self.assertIn("linkedin", stdout)

    def test_list_folders_no_config(self):
        result, stdout, stderr = self._run_cli(["list-folders"])
        self.assertEqual(result, 1)
        self.assertIn("not found", stdout.lower())

    @patch("pammi_drive.client._run_composio")
    def test_cli_upload(self, mock_run):
        self.test_file = Path(self.tmpdir) / "test.png"
        self.test_file.write_bytes(b"\x89PNG fake")
        config = {"linkedin": {"id": "li1", "name": "linkedin"}}
        save_config(config, self.config_path)
        mock_run.return_value = {"id": "file_123"}

        result, stdout, stderr = self._run_cli([
            "upload", "--platform", "linkedin", "--file", str(self.test_file)
        ])
        self.assertEqual(result, 0)
        data = json.loads(stdout)
        self.assertEqual(data["file_id"], "file_123")
        self.assertEqual(data["platform"], "linkedin")

    def test_cli_upload_missing_file(self):
        config = {"linkedin": {"id": "li1"}}
        save_config(config, self.config_path)
        result, stdout, stderr = self._run_cli([
            "upload", "--platform", "linkedin", "--file", "/nonexistent.png"
        ])
        self.assertEqual(result, 1)
        self.assertIn("Error", stderr)

    def test_no_command_prints_help(self):
        result, stdout, stderr = self._run_cli([])
        # No command should not crash; may print help and return 1
        self.assertIn(result, [0, 1])


class TestSetupFolders(unittest.TestCase):
    """Test setup_folders (mocks Composio, idempotent)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = Path(self.tmpdir) / "drive-config.json"

    @patch("pammi_drive.client.create_folder")
    @patch("pammi_drive.client.find_folder")
    def test_setup_creates_all_8_folders(self, mock_find, mock_create):
        # All folders missing initially
        mock_find.return_value = None
        mock_create.side_effect = lambda name, parent_id=None: {
            "id": f"id_{name}", "name": name
        }

        setup_folders(self.config_path)

        # Should have called create_folder 8 times
        self.assertEqual(mock_create.call_count, 8)

        # Config should be saved
        config = load_config(self.config_path)
        self.assertEqual(len(config), 8)
        for key in ["root", "source", "exports", "linkedin", "blogs", "shorts", "reels", "x"]:
            self.assertIn(key, config)

    @patch("pammi_drive.client.create_folder")
    @patch("pammi_drive.client.find_folder")
    def test_setup_idempotent_no_duplicates(self, mock_find, mock_create):
        # All folders exist
        def fake_find(name, parent_id=None):
            return {"id": f"existing_{name}", "name": name}
        mock_find.side_effect = fake_find
        mock_create.return_value = {"id": "new", "name": "X"}

        setup_folders(self.config_path)

        # Should NOT call create_folder if all exist
        self.assertEqual(mock_create.call_count, 0)


if __name__ == "__main__":
    unittest.main()
