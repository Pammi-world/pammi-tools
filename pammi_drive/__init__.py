"""pammi_drive - Google Drive helper for the Pammi Content System.

Module structure:
- pammi_drive/__init__.py — Public API (re-exports)
- pammi_drive/client.py — Drive client (folder/file operations)
- pammi_drive/cli.py — Command-line interface

Folder structure (configured in drive-config.json):
- /Pammi Content System/                   (root)
- /Pammi Content System/source/            (source files)
- /Pammi Content System/exports/           (final exports)
- /Pammi Content System/exports/linkedin/
- /Pammi Content System/exports/blogs/
- /Pammi Content System/exports/shorts/
- /Pammi Content System/exports/reels/
- /Pammi Content System/exports/x/
"""

from pammi_drive.client import (
    DEFAULT_CONFIG,
    FOLDER_STRUCTURE,
    PLATFORM_TO_KEY,
    load_config,
    save_config,
    get_target_folder,
    upload_file,
    setup_folders,
)

__all__ = [
    "DEFAULT_CONFIG",
    "FOLDER_STRUCTURE",
    "PLATFORM_TO_KEY",
    "load_config",
    "save_config",
    "get_target_folder",
    "upload_file",
    "setup_folders",
    "main",
]


def main(argv=None):
    """CLI entry point — re-exported from cli module."""
    from pammi_drive.cli import main as _main
    return _main(argv)
