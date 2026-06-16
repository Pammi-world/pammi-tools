"""Pammi Drive Helper

Upload files to the Pammi Content System Google Drive folders.

Folder structure:
- /Pammi Content System/                   (root)
- /Pammi Content System/source/            (source files)
- /Pammi Content System/exports/           (final exports)
- /Pammi Content System/exports/linkedin/
- /Pammi Content System/exports/blogs/
- /Pammi Content System/exports/shorts/
- /Pammi Content System/exports/reels/
- /Pammi Content System/exports/x/
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Default config path
DEFAULT_CONFIG = Path(__file__).parent.parent / "drive-config.json"

# Folder structure: (path_components, key_in_config)
FOLDER_STRUCTURE = [
    (["Pammi Content System"], "root"),
    (["Pammi Content System", "source"], "source"),
    (["Pammi Content System", "exports"], "exports"),
    (["Pammi Content System", "exports", "linkedin"], "exports_linkedin"),
    (["Pammi Content System", "exports", "blogs"], "exports_blogs"),
    (["Pammi Content System", "exports", "shorts"], "exports_shorts"),
    (["Pammi Content System", "exports", "reels"], "exports_reels"),
    (["Pammi Content System", "exports", "x"], "exports_x"),
]

# Map platforms to config keys
PLATFORM_TO_KEY = {
    "linkedin": "exports_linkedin",
    "blog": "exports_blogs",
    "blogs": "exports_blogs",
    "short": "exports_shorts",
    "shorts": "exports_shorts",
    "reel": "exports_reels",
    "reels": "exports_reels",
    "x": "exports_x",
    "twitter": "exports_x",
}


def _composio_env() -> dict:
    """Build env with composio on PATH."""
    return {**os.environ, "PATH": "/root/.composio:" + os.environ.get("PATH", "")}


def _run_composio(slug: str, data: dict, timeout: int = 60) -> dict:
    """Run a Composio tool and return parsed JSON response."""
    result = subprocess.run(
        ["composio", "execute", slug, "-d", json.dumps(data)],
        env=_composio_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Composio {slug} failed (exit {result.returncode}): {result.stderr}")

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from {slug}: {result.stdout[:200]}") from e


def load_config(config_path: Path = DEFAULT_CONFIG) -> dict:
    """Load Drive folder config from JSON file."""
    if not config_path.exists():
        return {}
    try:
        with open(config_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(config: dict, config_path: Path = DEFAULT_CONFIG) -> None:
    """Save Drive folder config to JSON file."""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)


def find_folder(name: str, parent_id: Optional[str] = None) -> Optional[dict]:
    """Find a folder by name. Returns dict with id, name, webViewLink, etc., or None."""
    data = {"name_exact": name}
    if parent_id:
        data["parent_folder_id"] = parent_id

    try:
        response = _run_composio("GOOGLEDRIVE_FIND_FOLDER", data)
    except Exception:
        return None

    if not response.get("successful"):
        return None

    # Response can have different shapes; find the files
    response_data = response.get("data", {})
    if isinstance(response_data, dict):
        # Try common keys
        for key in ("files", "items", "results", "data"):
            items = response_data.get(key)
            if isinstance(items, list) and items:
                return items[0]
        # Maybe the dict itself is the file
        if "id" in response_data:
            return response_data

    return None


def create_folder(name: str, parent_id: Optional[str] = None) -> dict:
    """Create a folder. Returns dict with id, name, etc.

    Raises RuntimeError on failure.
    """
    data = {"name": name}
    if parent_id:
        data["parent_id"] = parent_id

    response = _run_composio("GOOGLEDRIVE_CREATE_FOLDER", data)

    if not response.get("successful"):
        raise RuntimeError(f"Failed to create folder: {response.get('error')}")

    response_data = response.get("data", {})

    # Find the folder ID in the response
    if isinstance(response_data, dict):
        for key in ("id", "folder_id", "file_id"):
            if key in response_data:
                return {
                    "id": response_data[key],
                    "name": response_data.get("name", name),
                    "webViewLink": response_data.get("webViewLink", response_data.get("url")),
                }
        # Sometimes nested under 'folder' or 'data'
        for key in ("folder", "data"):
            nested = response_data.get(key)
            if isinstance(nested, dict) and "id" in nested:
                return {
                    "id": nested["id"],
                    "name": nested.get("name", name),
                    "webViewLink": nested.get("webViewLink", nested.get("url")),
                }

    raise RuntimeError(f"Could not find folder ID in response: {response_data}")


def get_or_create_folder(name: str, parent_id: Optional[str] = None) -> dict:
    """Find a folder by name, or create it if it doesn't exist."""
    existing = find_folder(name, parent_id)
    if existing:
        return existing
    return create_folder(name, parent_id)


def setup_folders(config_path: Path = DEFAULT_CONFIG) -> dict:
    """Set up the full folder structure. Idempotent.

    Returns the config dict with all folder IDs.
    """
    config = load_config(config_path)

    for path_parts, key in FOLDER_STRUCTURE:
        # Skip if we already have this key cached
        if key in config and config[key].get("id"):
            print(f"✓ {key} (cached): {config[key]['id']}")
            continue

        # Walk down the path, creating as needed
        parent_id = config.get("root", {}).get("id") if key != "root" else None

        # Special case: first folder is the root
        if key == "root":
            existing = find_folder(path_parts[0])
            if existing:
                config["root"] = existing
                print(f"✓ root (found): {existing.get('id')}")
                continue
            folder = create_folder(path_parts[0])
            config["root"] = folder
            print(f"✓ root (created): {folder.get('id')}")
            continue

        # For nested folders, walk the path
        # Re-walk from root to get the correct parent ID
        current_parent_id = config["root"]["id"]
        for i, part in enumerate(path_parts[1:], start=1):  # skip root
            # Find the corresponding config key
            partial_path = path_parts[:i+1]
            partial_key = "_".join(partial_path[1:])  # skip "Pammi Content System"
            partial_key = partial_key.replace(" ", "_") + ("_" if i == 1 else "")
            if partial_key not in config:
                partial_key = "_".join(partial_path[1:]).replace(" ", "_")
            if partial_key not in config:
                # Find by walking through
                child = find_folder(part, current_parent_id)
                if child:
                    config[partial_key] = child
                    current_parent_id = child["id"]
                else:
                    child = create_folder(part, current_parent_id)
                    config[partial_key] = child
                    current_parent_id = child["id"]
            else:
                current_parent_id = config[partial_key]["id"]

        if key not in config:
            # Save the deepest one
            config[key] = config[path_parts[-1].replace(" ", "_")]

        print(f"✓ {key}: {config[key].get('id')}")

    # Save config
    save_config(config, config_path)
    return config


def get_target_folder(platform: str, config_path: Path = DEFAULT_CONFIG) -> dict:
    """Get the Drive folder for a target platform.

    Args:
        platform: linkedin, blog, short, reel, x, etc.
        config_path: Path to drive-config.json

    Returns:
        Dict with 'id', 'name', 'webViewLink'
    """
    config = load_config(config_path)
    key = PLATFORM_TO_KEY.get(platform.lower())

    if not key:
        raise ValueError(f"Unknown platform: {platform!r}. Valid: {list(PLATFORM_TO_KEY.keys())}")

    if key not in config or not config[key].get("id"):
        raise RuntimeError(
            f"Folder for {platform!r} not configured. Run setup_folders() first."
        )

    return config[key]


def upload_file(local_path: str, target_platform: str,
                config_path: Path = DEFAULT_CONFIG) -> dict:
    """Upload a local file to the right Drive subfolder.

    Args:
        local_path: Path to local file
        target_platform: linkedin, blog, short, reel, x, etc.
        config_path: Path to drive-config.json

    Returns:
        Dict with 'file_id', 'drive_url', 'name', 'mime_type'
    """
    local_path = Path(local_path)
    if not local_path.exists():
        raise FileNotFoundError(f"File not found: {local_path}")

    target = get_target_folder(target_platform, config_path)

    # Read file as base64
    import base64
    with open(local_path, "rb") as f:
        file_bytes = f.read()
    file_b64 = base64.b64encode(file_bytes).decode("ascii")

    # Determine MIME type
    import mimetypes
    mime_type, _ = mimetypes.guess_type(str(local_path))
    if not mime_type:
        mime_type = "application/octet-stream"

    # Upload via Composio
    response = _run_composio("GOOGLEDRIVE_CREATE_FILE", {
        "name": local_path.name,
        "parent_id": target["id"],
        "mime_type": mime_type,
        "content_base64": file_b64,
    }, timeout=120)

    if not response.get("successful"):
        raise RuntimeError(f"Upload failed: {response.get('error')}")

    response_data = response.get("data", {})

    # Find file_id in response
    file_id = None
    drive_url = None
    for key in ("id", "file_id"):
        if key in response_data:
            file_id = response_data[key]
            break
    for key in ("webViewLink", "url", "drive_url"):
        if key in response_data:
            drive_url = response_data[key]
            break

    if not file_id:
        raise RuntimeError(f"Could not find file_id in response: {response_data}")

    return {
        "file_id": file_id,
        "drive_url": drive_url,
        "name": local_path.name,
        "mime_type": mime_type,
    }


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="pammi-drive",
        description="Pammi Drive helper - upload files to Google Drive folders",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # setup command
    subparsers.add_parser("setup", help="Set up the folder structure")

    # upload command
    upload_parser = subparsers.add_parser("upload", help="Upload a file")
    upload_parser.add_argument("file", help="Local file path to upload")
    upload_parser.add_argument(
        "platform",
        choices=list(PLATFORM_TO_KEY.keys()),
        help="Target platform",
    )

    # show command
    subparsers.add_parser("show", help="Show folder configuration")

    args = parser.parse_args(argv)

    if args.command == "setup":
        try:
            config = setup_folders()
            print(f"\nConfig saved to: {DEFAULT_CONFIG}")
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "upload":
        try:
            result = upload_file(args.file, args.platform)
            print(json.dumps(result, indent=2))
            return 0
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    elif args.command == "show":
        config = load_config()
        print(json.dumps(config, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
