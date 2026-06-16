"""Tests for pammi_mermaid, pammi_quickchart, pammi_bannerbear libraries."""

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mermaid tests - skip if mmdc not installed
try:
    from pammi_mermaid import render_diagram, find_mmdc, PNG, SVG, PDF
    HAS_MMDC = find_mmdc() is not None
except ImportError:
    HAS_MMDC = False

from pammi_quickchart import (
    build_chart_url, render_chart, render_chart_to_file,
    DEFAULT_API_URL, DEFAULT_WIDTH, DEFAULT_HEIGHT,
)
from pammi_bannerbear import (
    BannerbearClient, BannerbearError, is_configured, ENV_VAR,
)


@unittest.skipUnless(HAS_MMDC, "mmdc not installed")
class TestMermaid(unittest.TestCase):
    """Test pammi_mermaid library (requires mmdc installed)."""

    def setUp(self):
        self.output_dir = Path("/tmp/pammi_mermaid_test")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        # Clean up
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)

    def test_find_mmdc(self):
        path = find_mmdc()
        self.assertIsNotNone(path)
        self.assertIn("mmdc", path)

    def test_render_simple_png(self):
        code = "flowchart LR\n    A --> B"
        output = self.output_dir / "test.png"
        result = render_diagram(code, str(output), format=PNG, scale=1)
        self.assertEqual(result["format"], "png")
        self.assertTrue(output.exists())
        self.assertGreater(output.stat().st_size, 0)
        # Check it's a real PNG
        with open(output, "rb") as f:
            self.assertEqual(f.read(8)[:8], b"\x89PNG\r\n\x1a\n")

    def test_render_svg(self):
        code = "flowchart LR\n    A --> B"
        output = self.output_dir / "test.svg"
        result = render_diagram(code, str(output), format=SVG, scale=1)
        self.assertEqual(result["format"], "svg")
        self.assertTrue(output.exists())
        content = output.read_text()
        self.assertIn("<svg", content)

    def test_render_with_theme(self):
        code = "flowchart LR\n    A --> B"
        output = self.output_dir / "dark.png"
        result = render_diagram(code, str(output), format=PNG, theme="dark", scale=1)
        self.assertEqual(result["theme"], "dark")
        self.assertTrue(output.exists())

    def test_render_state_diagram(self):
        code = """stateDiagram-v2
    [*] --> Still
    Still --> [*]
    Still --> Moving
    Moving --> Still
    Moving --> Crash
    Crash --> [*]"""
        output = self.output_dir / "state.png"
        result = render_diagram(code, str(output), format=PNG, scale=1)
        self.assertTrue(output.exists())

    def test_render_from_file(self):
        from pammi_mermaid import render_diagram_from_file
        input_file = self.output_dir / "test.mmd"
        input_file.write_text("flowchart LR\n    X --> Y")
        output = self.output_dir / "from-file.png"
        result = render_diagram_from_file(str(input_file), str(output), format=PNG, scale=1)
        self.assertTrue(output.exists())

    def test_format_from_extension(self):
        # Should auto-detect format from .svg extension
        code = "flowchart LR\n    A --> B"
        output = self.output_dir / "auto.svg"
        result = render_diagram(code, str(output), scale=1)
        self.assertEqual(result["format"], "svg")

    def test_invalid_format_raises(self):
        code = "flowchart LR\n    A --> B"
        output = self.output_dir / "test.bmp"
        with self.assertRaises(ValueError):
            render_diagram(code, str(output), format="bmp")

    def test_nonexistent_mmdc_path(self):
        # Simulate mmdc not in PATH
        with patch("pammi_mermaid.find_mmdc", return_value=None):
            with self.assertRaises(RuntimeError) as ctx:
                render_diagram("A --> B", "/tmp/test.png")
            self.assertIn("mmdc", str(ctx.exception))


class TestQuickChart(unittest.TestCase):
    """Test pammi_quickchart library."""

    def test_build_chart_url(self):
        config = {"type": "bar", "data": {"labels": ["A"], "datasets": [{"data": [1]}]}}
        url = build_chart_url(config)
        self.assertTrue(url.startswith("https://quickchart.io/chart?"))
        self.assertIn("w=500", url)
        self.assertIn("h=300", url)
        self.assertIn("bkg=white", url)
        self.assertIn("f=png", url)
        # The config should be URL-encoded
        self.assertIn("%7B", url)  # {

    def test_build_chart_url_with_string_config(self):
        config_str = '{"type":"bar","data":{"labels":["A"],"datasets":[{"data":[1]}]}}'
        url = build_chart_url(config_str)
        self.assertIn("quickchart.io", url)

    def test_build_chart_url_custom_dimensions(self):
        config = {"type": "bar"}
        url = build_chart_url(config, width=800, height=400)
        self.assertIn("w=800", url)
        self.assertIn("h=400", url)

    def test_build_chart_url_svg(self):
        config = {"type": "bar"}
        url = build_chart_url(config, format="svg")
        self.assertIn("f=svg", url)

    def test_build_chart_url_custom_api(self):
        config = {"type": "bar"}
        url = build_chart_url(config, api_url="http://localhost:3400")
        self.assertTrue(url.startswith("http://localhost:3400/chart?"))

    @patch("pammi_quickchart.urllib.request.urlopen")
    def test_render_chart_validates(self, mock_urlopen):
        # Mock successful HEAD response
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.status = 200
        mock_urlopen.return_value = mock_resp

        config = {"type": "bar"}
        result = render_chart(config, width=500, height=300)
        self.assertEqual(result["width"], 500)
        self.assertEqual(result["height"], 300)
        self.assertEqual(result["status"], 200)
        self.assertIn("image_url", result)

    @patch("pammi_quickchart.urllib.request.urlopen")
    def test_render_chart_rejects_invalid(self, mock_urlopen):
        # Mock 400 response
        mock_urlopen.side_effect = __import__("urllib.error").error.HTTPError(
            "url", 400, "Bad Request", {}, None
        )
        with self.assertRaises(RuntimeError) as ctx:
            render_chart({"bad": "config"})
        self.assertIn("rejected", str(ctx.exception).lower())

    @patch("pammi_quickchart.urllib.request.urlopen")
    def test_render_chart_to_file(self, mock_urlopen):
        # Mock successful GET with PNG data
        import urllib.request
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = b"\x89PNG\r\n\x1a\n fake png data"
        mock_urlopen.return_value = mock_resp

        output_dir = Path("/tmp/pammi_qc_test")
        output_dir.mkdir(parents=True, exist_ok=True)
        try:
            output = output_dir / "test.png"
            config = {"type": "bar"}
            result = render_chart_to_file(config, str(output), width=500, height=300)
            self.assertTrue(output.exists())
            self.assertGreater(output.stat().st_size, 0)
            self.assertIn("image_url", result)
        finally:
            shutil.rmtree(output_dir)


class TestBannerbear(unittest.TestCase):
    """Test pammi_bannerbear library (STUB - no live API calls)."""

    def setUp(self):
        # Ensure BANNERBEAR_API_KEY is NOT set for stub tests
        self._saved_key = os.environ.pop(ENV_VAR, None)

    def tearDown(self):
        if self._saved_key is not None:
            os.environ[ENV_VAR] = self._saved_key
        else:
            os.environ.pop(ENV_VAR, None)

    def test_is_configured_false(self):
        self.assertFalse(is_configured())

    def test_is_configured_true(self):
        os.environ[ENV_VAR] = "test-key"
        self.assertTrue(is_configured())

    def test_client_is_configured_false(self):
        bb = BannerbearClient()
        self.assertFalse(bb.is_configured())

    def test_client_is_configured_true(self):
        bb = BannerbearClient(api_key="test-key")
        self.assertTrue(bb.is_configured())

    def test_get_api_key_raises(self):
        with self.assertRaises(BannerbearError) as ctx:
            from pammi_bannerbear import _get_api_key
            _get_api_key()
        self.assertIn("BANNERBEAR_API_KEY", str(ctx.exception))

    @patch("pammi_bannerbear._api_request")
    def test_create_image_calls_api(self, mock_request):
        os.environ[ENV_VAR] = "test-key"
        mock_request.return_value = {
            "uid": "img-123",
            "status": "completed",
            "image_url": "https://cdn.bannerbear.com/test.png",
        }
        bb = BannerbearClient()
        result = bb.create_image(
            template_id="tpl-123",
            modifications=[{"name": "title", "text": "Hello"}],
        )
        self.assertEqual(result["uid"], "img-123")
        self.assertEqual(result["image_url"], "https://cdn.bannerbear.com/test.png")

        # Verify the API was called with correct payload
        mock_request.assert_called_once()
        args, kwargs = mock_request.call_args
        self.assertEqual(args[0], "POST")
        self.assertEqual(args[1], "/images")
        payload = args[2]
        self.assertEqual(payload["template"], "tpl-123")
        self.assertEqual(len(payload["modifications"]), 1)

    @patch("pammi_bannerbear._api_request")
    def test_create_video_calls_api(self, mock_request):
        os.environ[ENV_VAR] = "test-key"
        mock_request.return_value = {
            "uid": "vid-123",
            "status": "completed",
            "video_url": "https://cdn.bannerbear.com/test.mp4",
        }
        bb = BannerbearClient()
        result = bb.create_video(
            template_id="vid-tpl-123",
            modifications=[{"name": "title", "text": "Hello"}],
        )
        self.assertEqual(result["uid"], "vid-123")

    @patch("pammi_bannerbear._api_request")
    def test_list_templates(self, mock_request):
        os.environ[ENV_VAR] = "test-key"
        mock_request.return_value = [
            {"id": "tpl-1", "name": "Template 1"},
            {"id": "tpl-2", "name": "Template 2"},
        ]
        bb = BannerbearClient()
        templates = bb.list_templates()
        self.assertEqual(len(templates), 2)
        self.assertEqual(templates[0]["id"], "tpl-1")

    @patch("pammi_bannerbear._api_request")
    def test_get_template(self, mock_request):
        os.environ[ENV_VAR] = "test-key"
        mock_request.return_value = {"id": "tpl-1", "name": "My Template"}
        bb = BannerbearClient()
        template = bb.get_template("tpl-1")
        self.assertEqual(template["name"], "My Template")


class TestCLIIntegration(unittest.TestCase):
    """Integration tests for all three CLIs."""

    def test_mermaid_cli_status(self):
        from pammi_mermaid import main as mermaid_main
        import io
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            result = mermaid_main(["check"])
        self.assertEqual(result, 0)
        self.assertIn("mmdc", stdout.getvalue())

    def test_bannerbear_cli_no_key(self):
        from pammi_bannerbear import main as bb_main
        import io
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(ENV_VAR, None)
            with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
                result = bb_main(["status"])
        self.assertEqual(result, 1)
        self.assertIn("NOT set", stdout.getvalue())

    def test_quickchart_cli_url(self):
        from pammi_quickchart import main as qc_main
        import io
        config = '{"type":"bar","data":{"labels":["A"],"datasets":[{"data":[1]}]}}'
        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("sys.stdout", stdout), patch("sys.stderr", stderr):
            result = qc_main(["url", "--config", config, "--width", "600"])
        self.assertEqual(result, 0)
        url = stdout.getvalue().strip()
        self.assertIn("w=600", url)


if __name__ == "__main__":
    unittest.main()
