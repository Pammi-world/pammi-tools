"""pammi_mermaid - Mermaid diagram rendering for Visual Content Pammi.

Renders Mermaid diagrams to PNG or SVG using the @mermaid-js/mermaid-cli
(mmdc) command-line tool.

Requires:
    - Node.js and npm
    - @mermaid-js/mermaid-cli installed globally: `npm install -g @mermaid-js/mermaid-cli`
    - Chrome/Chromium dependencies installed (libnspr4, libnss3, etc.)
    - Puppeteer config to disable sandbox when running as root
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

__all__ = [
    "DEFAULT_PUPPETEER_CONFIG",
    "PNG",
    "SVG",
    "PDF",
    "find_mmdc",
    "create_puppeteer_config",
    "render_diagram",
    "main",
]

PNG = "png"
SVG = "svg"
PDF = "pdf"

DEFAULT_PUPPETEER_CONFIG = {
    "args": ["--no-sandbox", "--disable-setuid-sandbox"]
}


def find_mmdc() -> Optional[str]:
    """Find the mmdc executable in PATH."""
    return shutil.which("mmdc")


def create_puppeteer_config(config_path: Optional[Path] = None) -> Path:
    """Create a puppeteer config file (needed for sandbox disabling on root).

    Returns the path to the config file.
    """
    import json
    if config_path is None:
        config_path = Path(tempfile.gettempdir()) / "pammi_puppeteer_config.json"
    config_path.write_text(json.dumps(DEFAULT_PUPPETEER_CONFIG))
    return config_path


def render_diagram(mermaid_code: str, output_path: str,
                   format: Optional[str] = None,
                   theme: str = "default",
                   background_color: str = "white",
                   width: Optional[int] = None,
                   height: Optional[int] = None,
                   scale: int = 1,
                   puppeteer_config: Optional[Path] = None) -> dict:
    """Render a Mermaid diagram to an image file.

    Args:
        mermaid_code: Mermaid diagram source (e.g., 'flowchart LR\\nA --> B')
        output_path: Path to save the rendered image
        format: 'png', 'svg', or 'pdf' (inferred from output_path extension if not specified)
        theme: Mermaid theme ('default', 'dark', 'forest', 'neutral', 'base')
        background_color: Background color (CSS color)
        width: Width in pixels (optional)
        height: Height in pixels (optional)
        scale: Puppeteer scale factor (default 1)
        puppeteer_config: Path to puppeteer config file (auto-created if not provided)

    Returns:
        Dict with: {output_path, format, size, width_px, height_px}

    Raises:
        RuntimeError: If mmdc is not installed or rendering fails
    """
    mmdc_path = find_mmdc()
    if mmdc_path is None:
        raise RuntimeError(
            "mmdc (Mermaid CLI) not found in PATH. "
            "Install with: npm install -g @mermaid-js/mermaid-cli"
        )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine format from extension if not provided
    if format is None or format == "":
        ext = output_path.suffix.lower().lstrip(".")
        if ext in (PNG, SVG, PDF):
            format = ext
        else:
            format = PNG

    format = format.lower()
    if format not in (PNG, SVG, PDF):
        raise ValueError(f"Unsupported format: {format!r}. Must be one of: png, svg, pdf")

    # Create puppeteer config if needed
    if puppeteer_config is None:
        puppeteer_config = create_puppeteer_config()

    # Write mermaid code to a temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".mmd", delete=False) as f:
        f.write(mermaid_code)
        input_file = f.name

    # Build mmdc command
    cmd = [
        mmdc_path,
        "-i", input_file,
        "-o", str(output_path),
        "-t", theme,
        "-b", background_color,
        "-s", str(scale),
        "-p", str(puppeteer_config),
    ]
    if width is not None:
        cmd.extend(["-w", str(width)])
    if height is not None:
        cmd.extend(["-H", str(height)])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Mermaid rendering failed (exit {result.returncode}): {result.stderr}"
            )

        if not output_path.exists():
            raise RuntimeError(
                f"Mermaid rendering failed: output file not created. stderr: {result.stderr}"
            )

        file_size = output_path.stat().st_size

        return {
            "output_path": str(output_path),
            "format": format,
            "size_bytes": file_size,
            "theme": theme,
            "background_color": background_color,
        }
    finally:
        # Clean up temp input file
        try:
            os.unlink(input_file)
        except OSError:
            pass


def render_diagram_from_file(input_file: str, output_path: str,
                             format: Optional[str] = None, **kwargs) -> dict:
    """Render a Mermaid diagram from a .mmd file."""
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")
    mermaid_code = input_path.read_text()
    return render_diagram(mermaid_code, output_path, format=format, **kwargs)


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pammi-mermaid",
        description="Pammi Mermaid - render Mermaid diagrams to images",
    )
    subparsers = parser.add_subparsers(dest="command", help="Command")

    # render command
    render_parser = subparsers.add_parser("render", help="Render a Mermaid diagram")
    render_parser.add_argument(
        "--input", "-i",
        required=True,
        help="Input .mmd file or inline mermaid code (prefix with 'mmd:' for inline)",
    )
    render_parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output image path (.png, .svg, or .pdf)",
    )
    render_parser.add_argument(
        "--theme", "-t",
        default="default",
        choices=["default", "dark", "forest", "neutral", "base"],
        help="Mermaid theme",
    )
    render_parser.add_argument(
        "--background", "-b",
        default="white",
        help="Background color (CSS)",
    )
    render_parser.add_argument(
        "--scale", "-s",
        type=int,
        default=2,
        help="Scale factor (default 2 for higher quality)",
    )

    # check command
    check_parser = subparsers.add_parser("check", help="Check if mmdc is installed")

    args = parser.parse_args(argv)

    try:
        if args.command == "check":
            mmdc = find_mmdc()
            if mmdc:
                result = subprocess.run([mmdc, "--version"], capture_output=True, text=True)
                print(f"mmdc found at: {mmdc}")
                print(f"Version: {result.stdout.strip()}")
                return 0
            else:
                print("mmdc NOT found. Install with: npm install -g @mermaid-js/mermaid-cli")
                return 1
        elif args.command == "render":
            # Allow inline mermaid code
            input_arg = args.input
            if input_arg.startswith("mmd:"):
                mermaid_code = input_arg[4:]
            else:
                mermaid_code = Path(input_arg).read_text()

            result = render_diagram(
                mermaid_code=mermaid_code,
                output_path=args.output,
                theme=args.theme,
                background_color=args.background,
                scale=args.scale,
            )
            print(json.dumps(result, indent=2))
            return 0
        else:
            parser.print_help()
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


# Lazy import json to avoid making json a hard dep at top
import json  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
