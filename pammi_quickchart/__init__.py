"""pammi_quickchart - QuickChart rendering for Visual Content Pammi.

QuickChart generates chart images (bar, line, pie, radar, etc.) via the
public QuickChart API or a self-hosted instance.

API docs: https://quickchart.io/documentation/

Two modes:
1. URL mode: Get a URL that returns a chart image (no server-side state)
2. File mode: Download the image to a local file
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional, Union

__all__ = [
    "DEFAULT_API_URL",
    "DEFAULT_WIDTH",
    "DEFAULT_HEIGHT",
    "DEFAULT_BACKGROUND_COLOR",
    "DEFAULT_DEVICE_PIXEL_RATIO",
    "build_chart_url",
    "render_chart",
    "render_chart_to_file",
    "main",
]

DEFAULT_API_URL = "https://quickchart.io"
DEFAULT_WIDTH = 500
DEFAULT_HEIGHT = 300
DEFAULT_BACKGROUND_COLOR = "white"
DEFAULT_DEVICE_PIXEL_RATIO = 2.0


def build_chart_url(config: Union[dict, str],
                    width: int = DEFAULT_WIDTH,
                    height: int = DEFAULT_HEIGHT,
                    background_color: str = DEFAULT_BACKGROUND_COLOR,
                    device_pixel_ratio: float = DEFAULT_DEVICE_PIXEL_RATIO,
                    api_url: str = DEFAULT_API_URL,
                    format: str = "png") -> str:
    """Build a QuickChart URL for a given chart config.

    Args:
        config: Chart.js config dict, or JSON string of one.
        width: Image width in pixels.
        height: Image height in pixels.
        background_color: Background color (CSS).
        device_pixel_ratio: For high-DPI rendering.
        api_url: QuickChart API base URL.
        format: 'png', 'svg', or 'pdf'.

    Returns:
        The full URL that will render the chart.

    Example:
        >>> config = {"type": "bar", "data": {"labels": ["Q1"], "datasets": [{"data": [1]}]}}
        >>> build_chart_url(config)
        'https://quickchart.io/chart?c=%7B...%7D&w=500&h=300&bkg=white&f=png'
    """
    if isinstance(config, str):
        # Already a JSON string
        config_str = config
    else:
        config_str = json.dumps(config, separators=(",", ":"))

    params = {
        "c": config_str,
        "w": str(width),
        "h": str(height),
        "bkg": background_color,
        "devicePixelRatio": str(device_pixel_ratio),
        "f": format,
    }
    query = urllib.parse.urlencode(params)
    return f"{api_url.rstrip('/')}/chart?{query}"


def render_chart(config: Union[dict, str],
                 width: int = DEFAULT_WIDTH,
                 height: int = DEFAULT_HEIGHT,
                 background_color: str = DEFAULT_BACKGROUND_COLOR,
                 device_pixel_ratio: float = DEFAULT_DEVICE_PIXEL_RATIO,
                 api_url: str = DEFAULT_API_URL,
                 format: str = "png",
                 timeout: int = 30) -> dict:
    """Render a chart via QuickChart and return URL + metadata.

    Does NOT download the image. Use render_chart_to_file() for that.

    Args:
        config: Chart.js config dict or JSON string.
        width: Image width in pixels.
        height: Image height in pixels.
        background_color: Background color (CSS).
        device_pixel_ratio: For high-DPI rendering.
        api_url: QuickChart API base URL.
        format: 'png', 'svg', or 'pdf'.
        timeout: HTTP timeout in seconds.

    Returns:
        Dict with: {image_url, width, height, format, config}

    Raises:
        RuntimeError: If the chart URL is invalid (QuickChart validates via HEAD).
    """
    url = build_chart_url(
        config=config,
        width=width,
        height=height,
        background_color=background_color,
        device_pixel_ratio=device_pixel_ratio,
        api_url=api_url,
        format=format,
    )

    # Validate by sending a HEAD request — QuickChart returns 400 for invalid configs
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"QuickChart rejected the config: {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to reach QuickChart: {e.reason}") from e

    return {
        "image_url": url,
        "width": width,
        "height": height,
        "format": format,
        "status": status,
    }


def render_chart_to_file(config: Union[dict, str],
                         output_path: str,
                         width: int = DEFAULT_WIDTH,
                         height: int = DEFAULT_HEIGHT,
                         background_color: str = DEFAULT_BACKGROUND_COLOR,
                         device_pixel_ratio: float = DEFAULT_DEVICE_PIXEL_RATIO,
                         api_url: str = DEFAULT_API_URL,
                         format: Optional[str] = None,
                         timeout: int = 30) -> dict:
    """Render a chart and download to a local file.

    Args:
        config: Chart.js config dict or JSON string.
        output_path: Path to save the image.
        width: Image width in pixels.
        height: Image height in pixels.
        background_color: Background color (CSS).
        device_pixel_ratio: For high-DPI rendering.
        api_url: QuickChart API base URL.
        format: 'png', 'svg', or 'pdf'. Auto-detected from output_path if not provided.
        timeout: HTTP timeout in seconds.

    Returns:
        Dict with: {output_path, image_url, size_bytes, width, height, format}
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if format is None or format == "":
        ext = output_path.suffix.lower().lstrip(".")
        if ext in ("png", "svg", "pdf"):
            format = ext
        else:
            format = "png"
    format = format.lower()

    url = build_chart_url(
        config=config,
        width=width,
        height=height,
        background_color=background_color,
        device_pixel_ratio=device_pixel_ratio,
        api_url=api_url,
        format=format,
    )

    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"QuickChart rejected the config: {e.code} {e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to reach QuickChart: {e.reason}") from e

    output_path.write_bytes(data)

    return {
        "output_path": str(output_path),
        "image_url": url,
        "size_bytes": len(data),
        "width": width,
        "height": height,
        "format": format,
    }


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pammi-quickchart",
        description="Pammi QuickChart - generate chart images",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # render command
    render_parser = subparsers.add_parser("render", help="Render a chart to file")
    render_parser.add_argument(
        "--config", "-c",
        required=True,
        help="Chart.js config as JSON string or path to JSON file",
    )
    render_parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output image path (.png, .svg, or .pdf)",
    )
    render_parser.add_argument(
        "--width", "-w",
        type=int,
        default=DEFAULT_WIDTH,
        help="Image width in pixels",
    )
    render_parser.add_argument(
        "--height",
        type=int,
        default=DEFAULT_HEIGHT,
        help="Image height in pixels",
    )
    render_parser.add_argument(
        "--background", "-b",
        default=DEFAULT_BACKGROUND_COLOR,
        help="Background color (CSS)",
    )
    render_parser.add_argument(
        "--device-pixel-ratio",
        type=float,
        default=DEFAULT_DEVICE_PIXEL_RATIO,
        help="Device pixel ratio (for high-DPI)",
    )
    render_parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help="QuickChart API URL (override for self-hosted)",
    )
    render_parser.add_argument(
        "--format", "-f",
        default=None,
        help="Output format (png, svg, pdf). Auto-detected from output path.",
    )

    # url command (just build URL, don't download)
    url_parser = subparsers.add_parser("url", help="Build chart URL without downloading")
    url_parser.add_argument("--config", "-c", required=True, help="Chart.js config (JSON string or file)")
    url_parser.add_argument("--width", "-w", type=int, default=DEFAULT_WIDTH)
    url_parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    url_parser.add_argument("--background", "-b", default=DEFAULT_BACKGROUND_COLOR)
    url_parser.add_argument("--api-url", default=DEFAULT_API_URL)

    args = parser.parse_args(argv)

    try:
        if args.command == "render":
            # Load config from file if path
            config = _load_config(args.config)
            result = render_chart_to_file(
                config=config,
                output_path=args.output,
                width=args.width,
                height=args.height,
                background_color=args.background,
                device_pixel_ratio=args.device_pixel_ratio,
                api_url=args.api_url,
                format=args.format,
            )
            print(json.dumps(result, indent=2))
            return 0
        elif args.command == "url":
            config = _load_config(args.config)
            url = build_chart_url(
                config=config,
                width=args.width,
                height=args.height,
                background_color=args.background,
                api_url=args.api_url,
            )
            print(url)
            return 0
        else:
            parser.print_help()
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def _load_config(config_arg: str) -> Union[dict, str]:
    """Load config from a JSON string or file path."""
    # If it looks like a file path, try to read it
    if config_arg.endswith(".json") or (os.path.exists(config_arg) and os.path.isfile(config_arg)):
        try:
            path = Path(config_arg)
            if path.is_file():
                return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            pass
    # Otherwise treat as inline JSON
    try:
        return json.loads(config_arg)
    except json.JSONDecodeError:
        # Treat as raw string (will be passed through to QuickChart)
        return config_arg


if __name__ == "__main__":
    sys.exit(main())
