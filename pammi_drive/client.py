"""Pammi Drive client — Google Drive operations via Composio.

Uses Composio's GOOGLEDRIVE_CREATE_FOLDER and GOOGLEDRIVE_CREATE_FILE
actions to manage the Pammi Content System folder structure.
"""

import base64
import json
import mimetypes
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional


# Default config path (sibling of pammi_drive package)
DEFAULT_CONFIG = Path(__file__).parent.parent / "drive-config.json"

# Folder structure: (path_components, key_in_config)
FOLDER_STRUCTURE = [
    (["Pammi Content System"], "root"),
    (["Pammi Content System", "source"], "source"),
    (["Pammi Content System", "exports"], "exports"),
    (["Pammi Content System", "exports", "linkedin"], "linkedin"),
    (["Pammi Content System", "exports", "blogs"], "blogs"),
    (["Pammi Content System", "exports", "shorts"], "shorts"),
    (["Pammi Content System", "exports", "reels"], "reels"),
    (["Pammi Content System", "exports", "x"], "x"),
]

# Map CLI platform name → config key
PLATFORM_TO_KEY = {
    "linkedin": "linkedin",
    "blog": "blogs",
    "blogs": "blogs",
    "short": "shorts",
    "shorts": "shorts",
    "reel": "reels",
    "reels": "reels",
    "x": "x",
    "twitter": "x",
}

# Map config key → MIME type hint
MIME_HINTS = {
    "image/png": "image/png",
    "image/jpeg": "image/jpeg",
    "image/svg+xml": "image/svg+xml",
    "image/gif": "image/gif",
    "image/webp": "image/webp",
}


def _composio_env() -> dict:
    """Build env dict with Composio bin in PATH."""
    env = os.environ.copy()
    composio_bin = Path.home() / ".composio"
    if composio_bin.exists():
        env["PATH"] = f"{composio_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def _run_composio(slug: str, data: dict, timeout: int = 60) -> dict:
    """Run a Composio action and return the parsed response."""
    cmd = [
        "composio", "execute", slug, "-d", json.dumps(data)
    ]
    result = subprocess.run(
        cmd,
        env=_composio_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Composio {slug} failed (exit {result.returncode}): {result.stderr}"
        )

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Invalid JSON from Composio: {result.stdout[:200]}") from e

    if not response.get("successful"):
        error = response.get("error", "Unknown error")
        raise RuntimeError(f"Composio {slug} failed: {error}")

    return response.get("data", {})


def load_config(config_path: Path = DEFAULT_CONFIG) -> dict:
    """Load drive-config.json. Returns empty dict if file doesn't exist."""
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text())


def save_config(config: dict, config_path: Path = DEFAULT_CONFIG) -> None:
    """Save drive-config.json. Creates parent directories if needed."""
    config_path = Path(config_path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2, default=str))


def find_folder(name: str, parent_id: Optional[str] = None) -> Optional[dict]:
    """Find a folder by name. Optionally scope to a parent."""
    data = {
        "query": f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false",
    }
    if parent_id:
        data["query"] += f" and '{parent_id}' in parents"

    try:
        response = _run_composio("GOOGLEDRIVE_FIND_FOLDER", data)
    except RuntimeError:
        return None

    folders = response.get("files", [])
    return folders[0] if folders else None


def create_folder(name: str, parent_id: Optional[str] = None) -> dict:
    """Create a folder. Returns dict with id, name, etc."""
    data = {"name": name}
    if parent_id:
        data["parent_id"] = parent_id

    response = _run_composio("GOOGLEDRIVE_CREATE_FOLDER", data)
    return response


def get_or_create_folder(name: str, parent_id: Optional[str] = None) -> dict:
    """Find a folder by name, or create it if it doesn't exist.

    Idempotent helper.
    """
    existing = find_folder(name, parent_id)
    if existing:
        return existing
    return create_folder(name, parent_id)


def setup_folders(config_path: Path = DEFAULT_CONFIG) -> dict:
    """Create all folders in FOLDER_STRUCTURE. Saves IDs to config_path.

    Idempotent: if a folder already exists, reuses its ID.
    Smart: tracks in-memory cache to avoid re-creating parents walked through.
    """
    config = load_config(config_path)
    # In-memory cache: {folder_name: folder_id} for this run
    cache = {}

    print("Setting up Drive folder structure...")

    for path_parts, key in FOLDER_STRUCTURE:
        current_parent_id = None

        # Walk down the path
        for i, part in enumerate(path_parts):
            if part in cache:
                # Already created in this run
                folder_id = cache[part]
                print(f"  ✓ {part} (cached): {folder_id}")
            else:
                if i == 0:
                    existing = find_folder(part)
                else:
                    existing = find_folder(part, current_parent_id)

                if existing:
                    folder_id = existing.get("id")
                    print(f"  ✓ {part} (exists): {folder_id}")
                else:
                    folder = create_folder(part, current_parent_id)
                    folder_id = folder.get("id")
                    print(f"  + {part} (created): {folder_id}")

                cache[part] = folder_id

            current_parent_id = folder_id

        # Save the deepest folder
        config[key] = {"id": current_parent_id, "name": path_parts[-1]}

    save_config(config, config_path)
    print(f"\n✓ Configuration saved to {config_path}")
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
        raise ValueError(
            f"Unknown platform: {platform!r}. Valid: {list(PLATFORM_TO_KEY.keys())}"
        )

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
    folder_id = target["id"]

    # Read file as base64
    with open(local_path, "rb") as f:
        file_bytes = f.read()
    file_b64 = base64.b64encode(file_bytes).decode("ascii")

    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(str(local_path))
    if not mime_type:
        mime_type = "application/octet-stream"

    # Upload via Composio
    response = _run_composio("GOOGLEDRIVE_CREATE_FILE", {
        "name": local_path.name,
        "content_base64": file_b64,
        "mime_type": mime_type,
        "parent_folder_id": folder_id,
    })

    # Extract file_id from response
    file_id = response.get("id") or response.get("file_id")
    if not file_id:
        raise RuntimeError(f"No file_id in response: {response}")

    return {
        "file_id": file_id,
        "drive_url": f"https://drive.google.com/file/d/{file_id}/view",
        "name": local_path.name,
        "mime_type": mime_type,
        "folder_id": folder_id,
        "platform": target_platform,
    }
