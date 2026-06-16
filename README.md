# Pammi Tools

Shared Python utilities for the Pammi Content System. Currently includes:

- **`pammi_ids`** — Deterministic, human-readable ID generator
- **`pammi_drive`** — Google Drive upload helper
- **`pammi_dedup`** — Content deduplication

## pammi_ids

Generates IDs like `CP-001`, `LI-042`, `AS-1234` for the Pammi content pipeline.

### ID Prefixes

| Prefix | Type | Notes |
|--------|------|-------|
| `CP-###` | Content Packages | |
| `LI-###` | LinkedIn posts | |
| `AS-###` | Assets | **Globally unique** across all packages and platforms |
| `LOG-###` | Publishing Log entries | |
| `VR-###` | Visual Requests | Handoff from Content → Visual Pammi |

### Format

`PREFIX-NNN` where:
- `PREFIX` is uppercase letters
- `NNN` is zero-padded to at least 3 digits (e.g., `CP-001`, `AS-1234`)

### How It Works

The generator has two sources for the "next available" number:
1. **Primary:** Reads existing IDs from the `Pammi Content Calendar` Google Sheet via Composio
2. **Fallback:** Local JSON cache at `~/.pammi-tools/counters.json`

It takes the max of both, increments by 1, and returns the new ID.

### Usage

#### Python API

```python
from pammi_ids import get_next, validate_id, reserve

# Get the next available ID (reads Google Sheet)
new_id = get_next("CP")  # "CP-001"
print(new_id)

# Validate an ID format
assert validate_id("CP-001") == True
assert validate_id("cp-001") == False
assert validate_id("CP-1") == False

# Reserve multiple consecutive IDs
ids = reserve("LI", count=3)
# ["LI-001", "LI-002", "LI-003"]
```

#### CLI

```bash
# Get next available ID for a prefix (reads Google Sheet)
./pammi-ids next cp
# Output: CP-001

# Without reading the sheet (use local cache only)
./pammi-ids next cp --no-sheet

# Validate an ID format
./pammi-ids validate CP-001
# Output: ✓ CP-001 is valid

./pammi-ids validate bad
# Output: ✗ bad is invalid (expected format: PREFIX-NNN)
# Exit code: 1

# Reserve multiple consecutive IDs
./pammi-ids reserve as 3
# Output:
#   AS-001
#   AS-002
#   AS-003

# List all valid prefixes
./pammi-ids list
# Output:
#   Valid prefixes:
#     CP     Content Packages
#     LI     LinkedIn posts
#     AS     Assets (globally unique)
#     LOG    Publishing Log entries
#     VR     Visual Requests
```

### Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `SPREADSHEET_ID` | `1rHM6bHIsq8h8a0jG83afWdlZs6wHV25yANutPdkhODk` | The Pammi Content Calendar |
| `COUNTERS_PATH` | `~/.pammi-tools/counters.json` | Local counter cache |

### Install

```bash
# Add to PYTHONPATH or install as a package
export PYTHONPATH=/data/workspace-dev/pammi-tools:$PYTHONPATH
./pammi-ids next cp
```

### Tests

```bash
cd /data/workspace-dev/pammi-tools
python3 -m unittest tests.test_pammi_ids
```

43 tests covering:
- ID format validation (valid, invalid, edge cases)
- ID parsing and formatting
- Counter persistence
- Sheet-based max-number extraction
- Global uniqueness of `AS-###`
- Reserve multiple consecutive IDs
- CLI interface

## Repository Structure

```
pammi-tools/
├── pammi_ids/
│   └── __init__.py         # ID generator library
├── pammi_drive/
│   └── __init__.py         # Drive upload helper
├── pammi_dedup/
│   └── __init__.py         # Dedup key library
├── pammi-ids               # ID generator CLI
├── pammi-drive             # Drive upload CLI
├── pammi-dedup             # Dedup CLI
├── drive-config.json       # Drive folder ID cache
├── tests/
│   ├── test_pammi_ids.py
│   ├── test_pammi_drive.py
│   └── test_pammi_dedup.py
├── SETUP.md                # Drive setup instructions
└── README.md
```

## Adding New Tools

To add a new tool to this monorepo:

1. Create a new directory under `pammi_tools/` (note underscore for module name)
2. Add an `__init__.py` with your library
3. Optionally add a CLI script at the repo root
4. Add tests under `tests/`
5. Update this README

## Requirements

- Python 3.11+
- `composio` CLI installed and authenticated (for Google Sheet reads)

## pammi_drive

Google Drive helper for uploading visual assets to the Pammi Content System folder structure.

### Folder Structure

```
Pammi Content System/                    (root)
├── source/                              (source files)
└── exports/                             (final exports)
    ├── linkedin/
    ├── blogs/
    ├── shorts/
    ├── reels/
    └── x/
```

### Setup (One-time)

1. Authorize Google Drive with Composio:
   ```bash
   composio link googledrive
   ```
   This opens a browser. Sign in with `pammibot6@gmail.com` and authorize.

2. Create all the folders:
   ```bash
   ./pammi-drive setup
   ```
   This will:
   - Find or create `/Pammi Content System/`
   - Create the `source/`, `exports/`, and 5 platform subfolders
   - Save all folder IDs to `drive-config.json`

### Usage

#### Python API

```python
from pammi_drive import upload_file, get_target_folder, load_config

# Get a folder reference
folder = get_target_folder("linkedin")
print(folder["id"], folder["webViewLink"])

# Upload a local file
result = upload_file("my_image.png", "linkedin")
print(result)
# {
#   "file_id": "abc123",
#   "drive_url": "https://drive.google.com/file/d/abc123/view",
#   "name": "my_image.png",
#   "mime_type": "image/png"
# }
```

#### CLI

```bash
# Set up folders (one-time)
./pammi-drive setup

# Show current folder configuration
./pammi-drive show

# Upload a file (flag-based)
./pammi-drive upload --platform linkedin --file my_image.png
# Output:
# {
#   "file_id": "abc123",
#   "drive_url": "https://drive.google.com/file/d/abc123/view",
#   "name": "my_image.png",
#   "mime_type": "image/png"
# }
```

### Supported Platforms

| Platform | Config key | Folder |
|----------|-----------|--------|
| `linkedin` | `exports_linkedin` | `/Pammi Content System/exports/linkedin/` |
| `blog`, `blogs` | `exports_blogs` | `/Pammi Content System/exports/blogs/` |
| `short`, `shorts` | `exports_shorts` | `/Pammi Content System/exports/shorts/` |
| `reel`, `reels` | `exports_reels` | `/Pammi Content System/exports/reels/` |
| `x`, `twitter` | `exports_x` | `/Pammi Content System/exports/x/` |

### Configuration

| File | Description |
|------|-------------|
| `drive-config.json` | Folder ID cache (auto-generated by `pammi-drive setup`) |

### Tests

```bash
python3 -m unittest tests.test_pammi_drive
```

24 tests covering:
- Config file read/write
- Folder structure definitions
- Find / create / get-or-create folder
- Platform → folder key mapping
- File upload with MIME type detection
- CLI interface

## pammi_dedup

Content deduplication for the Pammi Content System. Before Content Pammi creates a new platform row, it checks for duplicates using a `dedup_key`.

### Format

```
platform:normalized_topic:yyyy-mm-dd
```

Example: `linkedin:queues-for-ai-agents:2026-06-18`

### Normalization Rules

When normalizing a topic:
1. Lowercase
2. Strip leading/trailing whitespace
3. Collapse multiple spaces
4. Replace underscores with spaces (then with dashes)
5. Remove punctuation (keep alphanumerics, spaces, dashes)
6. Replace spaces with dashes
7. Trim leading/trailing dashes

### Usage

#### Python API

```python
from pammi_dedup import compute_dedup_key, normalize_topic, find_duplicate

# Compute a key
key = compute_dedup_key("linkedin", "Queues for AI Agents!", "2026-06-18")
print(key)  # "linkedin:queues-for-ai-agents:2026-06-18"

# Just normalize
topic = normalize_topic("Hello, World!")
print(topic)  # "hello-world"

# Check for duplicates (reads Google Sheet)
existing = find_duplicate("linkedin", "Queues for AI Agents!", "2026-06-18")
if existing:
    print(f"DUPLICATE: {existing['post_id']} (status: {existing['status']})")
else:
    print("No duplicate, safe to create")
```

#### CLI

```bash
# Compute a dedup_key
./pammi-dedup compute --platform linkedin --topic "Queues for AI Agents!" --date 2026-06-18
# Output: linkedin:queues-for-ai-agents:2026-06-18

# Just normalize a topic
./pammi-dedup normalize "Hello, World!!"
# Output: hello-world

# Check for existing duplicates
./pammi-dedup check --platform linkedin --topic "Queues for AI Agents!" --date 2026-06-18
# Output: {"post_id": "LI-042", "dedup_key": "linkedin:...", "status": "READY", ...}
# (or "null" if no duplicate)
```

### Duplicate Detection

`find_duplicate` reads the relevant tab in the `Pammi Content Calendar` Google Sheet and looks for any row with the same `dedup_key`. It **excludes** rows with these statuses:
- `SKIPPED`
- `ARCHIVED`
- Empty/missing status

All other statuses (DRAFT, ASSET_READY, READY, APPROVED, SCHEDULED, POSTED) count as duplicates.

### Tests

```bash
python3 -m unittest tests.test_pammi_dedup
```

48 tests covering:
- Normalization edge cases (punctuation, whitespace, dashes, emojis, unicode)
- Dedup key computation (date formats, platform lowercasing, defaults)
- Duplicate detection (status filtering, row matching, edge cases)
- CLI interface
