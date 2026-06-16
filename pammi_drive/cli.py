"""Pammi Drive CLI - command-line interface."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from pammi_drive.client import (
    DEFAULT_CONFIG,
    FOLDER_STRUCTURE,
    PLATFORM_TO_KEY,
    load_config,
    upload_file,
    setup_folders,
)


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="pammi-drive",
        description="Pammi Drive - upload files to Google Drive folders",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Path to drive-config.json",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command")

    # upload command
    upload_parser = subparsers.add_parser("upload", help="Upload a file")
    upload_parser.add_argument(
        "--platform",
        required=True,
        choices=list(PLATFORM_TO_KEY.keys()),
        help="Target platform",
    )
    upload_parser.add_argument(
        "--file",
        required=True,
        help="Local file path to upload",
    )

    # setup command
    setup_parser = subparsers.add_parser("setup", help="Set up Drive folder structure")

    # list-folders command
    list_parser = subparsers.add_parser("list-folders", help="Show folder IDs from config")

    # show command (alias for list-folders)
    show_parser = subparsers.add_parser("show", help="Show folder IDs from config (alias)")

    args = parser.parse_args(argv)

    try:
        if args.command == "upload":
            result = upload_file(args.file, args.platform, Path(args.config))
            print(json.dumps(result, indent=2))
            return 0
        elif args.command == "setup":
            setup_folders(Path(args.config))
            return 0
        elif args.command in ("list-folders", "show"):
            config_path = Path(args.config)
            if not config_path.exists():
                print(f"Config not found: {config_path}")
                print("Run `pammi-drive setup` first.")
                return 1
            config = load_config(config_path)
            print(f"Folder configuration ({config_path}):")
            print()
            for path_parts, key in FOLDER_STRUCTURE:
                entry = config.get(key, {})
                folder_id = entry.get("id") if isinstance(entry, dict) else entry
                status = "✓" if folder_id else "✗"
                folder_name = path_parts[-1]
                print(f"  {status} {key:12s} = {folder_id or '(not set)':40s} ({folder_name})")
            return 0
        else:
            parser.print_help()
            return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
