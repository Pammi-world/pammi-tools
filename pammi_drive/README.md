# pammi_drive

Google Drive helper for the Pammi Content System. Uploads files to the right
subfolder based on the target platform.

## Folder Structure

```
Pammi Content System/                  (root)
├── source/                            (source files)
└── exports/                           (final exports)
    ├── linkedin/
    ├── blogs/
    ├── shorts/
    ├── reels/
    └── x/
```

## Setup (one-time)

1. **Authorize Google Drive via Composio** (browser-based OAuth):

   ```bash
   composio link googledrive
   ```
   Sign in with `pammibot6@gmail.com` when prompted.

2. **Create the folder structure**:

   ```bash
   ./pammi-drive setup
   ```
   This creates all 8 folders and saves their IDs to `drive-config.json`.

3. **Verify the setup**:

   ```bash
   ./pammi-drive list-folders
   ```

## Usage

### Python API

```python
from pammi_drive import upload_file, get_target_folder, load_config

# Look up a folder
folder = get_target_folder("linkedin")
print(f"LinkedIn folder: {folder['id']}")

# Upload a file
result = upload_file("./my_image.png", "linkedin")
print(f"Uploaded: {result['drive_url']}")
print(f"File ID: {result['file_id']}")
```

### CLI

```bash
# Upload a file
./pammi-drive upload --platform linkedin --file ./test.png

# Set up folders (idempotent)
./pammi-drive setup

# Show folder IDs from config
./pammi-drive list-folders
./pammi-drive show  # alias

# Module invocation
python -m pammi_drive upload --platform linkedin --file ./test.png
```

## Configuration

Folder IDs are stored in `drive-config.json` (sibling of `pammi_drive/`):

```json
{
  "root": { "id": "...", "name": "Pammi Content System" },
  "source": { "id": "...", "name": "source" },
  "exports": { "id": "...", "name": "exports" },
  "linkedin": { "id": "...", "name": "linkedin" },
  "blogs": { "id": "...", "name": "blogs" },
  "shorts": { "id": "...", "name": "shorts" },
  "reels": { "id": "...", "name": "reels" },
  "x": { "id": "...", "name": "x" }
}
```

## Module Structure

- `pammi_drive/__init__.py` — Public API (re-exports)
- `pammi_drive/client.py` — Drive client (folder/file operations)
- `pammi_drive/cli.py` — Command-line interface

## Tests

```bash
python -m unittest tests.test_pammi_drive
```

Tests mock all Composio calls — no real Drive access needed.
