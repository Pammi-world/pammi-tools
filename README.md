# Pammi Tools

Shared Python utilities for the Pammi Content System. Currently includes:

- **`pammi_ids`** — Deterministic, human-readable ID generator
- **`pammi_drive`** — Google Drive upload helper
- **`pammi_dedup`** — Content deduplication
- **`pammi_timezone`** — Timezone handling (UTC/Eastern with DST)
- **`pammi_mermaid`** — Mermaid diagram rendering (PNG/SVG)
- **`pammi_quickchart`** — QuickChart chart generation
- **`pammi_bannerbear`** — Bannerbear API client (stub - needs API key)

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
├── pammi_timezone/
│   └── __init__.py         # Timezone handling library
├── pammi_mermaid/
│   └── __init__.py         # Mermaid rendering library
├── pammi_quickchart/
│   └── __init__.py         # QuickChart library
├── pammi_bannerbear/
│   └── __init__.py         # Bannerbear API stub
├── pammi-ids               # ID generator CLI
├── pammi-drive             # Drive upload CLI
├── pammi-dedup             # Dedup CLI
├── pammi-timezone          # Timezone CLI
├── pammi-mermaid           # Mermaid CLI
├── pammi-quickchart        # QuickChart CLI
├── pammi-bannerbear        # Bannerbear CLI
├── drive-config.json       # Drive folder ID cache
├── tests/
│   ├── test_pammi_ids.py
│   ├── test_pammi_drive.py
│   ├── test_pammi_dedup.py
│   ├── test_pammi_timezone.py
│   └── test_visual_tools.py
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
existing = find_duplicate(
    sheet_id="1rHM6bHIsq8h8a0jG83afWdlZs6wHV25yANutPdkhODk",
    platform="linkedin",
    topic="Queues for AI Agents!",
    scheduled_date="2026-06-18",
)
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

# Or use python -m
python -m pammi_dedup compute --platform linkedin --topic "Queues for AI Agents!" --date 2026-06-18

# Just normalize a topic
./pammi-dedup normalize "Hello, World!!"
# Output: hello-world

# Check for existing duplicates
./pammi-dedup check --platform linkedin --topic "Queues for AI Agents!" --date 2026-06-18
# Output: {"post_id": "LI-042", "dedup_key": "linkedin:...", "status": "READY", ...}
# (or "null" if no duplicate)

# Custom sheet ID
./pammi-dedup check --sheet-id <other-sheet-id> --platform linkedin --topic "X" --date 2026-06-18
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

## pammi_timezone

Timezone handling for the Pammi Content System. The user is in NYC (Eastern time), but we store all times internally in UTC and convert at the boundary.

### Strategy

- **Internal storage/computation:** UTC
- **Display:** America/New_York (with EDT/EST abbreviation)
- **User input:** Naive datetimes assumed to be Eastern
- **DST:** Automatically handled via `zoneinfo` (Python 3.9+)

### Usage

#### Python API

```python
from pammi_timezone import (
    now_utc, now_eastern,
    eastern_to_utc, utc_to_eastern,
    parse_user_datetime, format_for_display,
)

# Current time
utc = now_utc()         # 2026-06-16 03:30:00+00:00
eastern = now_eastern() # 2026-06-15 23:30:00-04:00 (EDT)

# Convert
eastern_to_utc("2026-06-18 09:00")  # 2026-06-18 13:00:00+00:00 (EDT)
utc_to_eastern("2026-06-18T13:00:00Z")  # 2026-06-18 09:00:00-04:00 (EDT)

# Parse user input
utc = parse_user_datetime("tomorrow 9am")        # 2026-06-16 13:00:00+00:00
utc = parse_user_datetime("2026-06-18 14:00")     # 2026-06-18 18:00:00+00:00
utc = parse_user_datetime("Jun 18, 2026 9am EST") # 2026-06-18 14:00:00+00:00
utc = parse_user_datetime("in 2 hours")           # 2 hours from now

# Format for display
format_for_display(parse_user_datetime("tomorrow 9am"))
# "Jun 16, 2026 9:00 AM EDT"
```

#### CLI

```bash
# Show current time
./pammi-timezone now
# Output:
#   UTC:    2026-06-16T03:30:00+00:00
#   Eastern: 2026-06-15T23:30:00-04:00
#   Display: Jun 15, 2026 11:30 PM EDT

# Convert timezones
./pammi-timezone convert --input "2026-06-18 09:00" --from eastern --to utc
# 2026-06-18T13:00:00+00:00

./pammi-timezone convert --input "2026-06-18T13:00:00Z" --from utc --to eastern
# 2026-06-18T09:00:00-04:00

# Format UTC as Eastern display
./pammi-timezone format --input "2026-06-18T13:00:00Z"
# Jun 18, 2026 9:00 AM EDT

# Parse user input
./pammi-timezone parse --input "tomorrow 9am"
# UTC:  2026-06-16T13:00:00+00:00
# Display: Jun 16, 2026 9:00 AM EDT

# Module invocation
python -m pammi_timezone now
```

### Supported Input Formats

`parse_user_datetime` handles:
- ISO 8601: `2026-06-18T09:00:00-04:00`, `2026-06-18T13:00:00Z`
- Date+time: `2026-06-18 09:00`, `2026-06-18 09:00:00`
- Date only: `2026-06-18`
- US format: `06/18/2026`
- Long form: `Jun 18, 2026 9:00 AM`
- With TZ: `2026-06-18 09:00 EST`, `2026-06-18 09:00 EDT`, `2026-06-18 09:00 ET`
- Natural: `tomorrow 9am`, `today 14:00`, `next friday 2pm`
- Relative: `in 2 hours`, `in 30 minutes`, `in 3 days`

### DST Handling

Eastern time is either EST (UTC-5, winter) or EDT (UTC-4, summer). The library:
- Detects DST automatically via `zoneinfo`
- Transitions correctly at 2 AM on the second Sunday of March (spring forward) and first Sunday of November (fall back)
- Always returns UTC, which has no DST

```python
# Summer (EDT, UTC-4)
eastern_to_utc("2026-06-18 09:00")  # 2026-06-18 13:00:00+00:00
format_for_display(...)  # "...EDT"

# Winter (EST, UTC-5)
eastern_to_utc("2026-01-18 09:00")  # 2026-01-18 14:00:00+00:00
format_for_display(...)  # "...EST"
```

### Tests

```bash
python3 -m unittest tests.test_pammi_timezone
```

58 tests covering:
- Basic now_utc / now_eastern
- Eastern ↔ UTC conversions
- DST spring forward (March) and fall back (November)
- Naive datetime handling (assumed Eastern or UTC depending on function)
- ISO 8601 with and without offsets
- All natural language patterns (tomorrow, today, next X, in N hours)
- Timezone suffixes (EST, EDT, ET, UTC, Z)
- Leap year handling (Feb 29)
- Display format consistency
- CLI commands

## Visual Content Tools

### pammi_mermaid

Renders Mermaid diagrams to PNG/SVG/PDF using `@mermaid-js/mermaid-cli`.

**Setup (one-time):**

```bash
# Install Mermaid CLI globally
npm install -g @mermaid-js/mermaid-cli

# Install Chrome dependencies (Debian/Ubuntu)
apt-get install -y libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 \
  libpango-1.0-0 libcairo2 fonts-liberation

# The library auto-creates a Puppeteer config with --no-sandbox (for root)
# Or create your own:
cat > puppeteer.json << 'JSON'
{ "args": ["--no-sandbox", "--disable-setuid-sandbox"] }
JSON
```

**Python API:**
```python
from pammi_mermaid import render_diagram

code = "flowchart LR\n    A[Start] --> B[Process]\n    B --> C[End]"
result = render_diagram(code, "/tmp/diagram.png", format="png", scale=2)
print(result)  # {output_path, format, size_bytes, theme, ...}
```

**CLI:**
```bash
./pammi-mermaid check                                # Verify mmdc is installed
./pammi-mermaid render --input ./flow.mmd --output ./flow.png
./pammi-mermaid render --input "mmd:graph TD; A-->B" --output ./inline.png
./pammi-mermaid render --input ./state.mmd --output ./state.svg --theme dark
python -m pammi_mermaid render --input ./flow.mmd --output ./flow.png
```

**Themes:** `default`, `dark`, `forest`, `neutral`, `base`

### pammi_quickchart

Generates chart images (bar, line, pie, radar, etc.) via QuickChart.

**Setup (one-time):**
No setup needed - uses the public API at https://quickchart.io

For self-hosted QuickChart, set `--api-url http://localhost:3400` per call or pass `api_url=` to functions.

**Python API:**
```python
from pammi_quickchart import render_chart, render_chart_to_file

config = {
    "type": "bar",
    "data": {
        "labels": ["Q1", "Q2", "Q3", "Q4"],
        "datasets": [{"label": "Revenue", "data": [12, 19, 8, 15]}]
    }
}

# Just get the URL
result = render_chart(config, width=800, height=400)
print(result["image_url"])

# Download to file
result = render_chart_to_file(config, "/tmp/chart.png", width=800, height=400)
```

**CLI:**
```bash
# From a config file
./pammi-quickchart render --config ./chart.json --output ./chart.png

# Inline config
./pammi-quickchart render --config '{"type":"pie","data":{"labels":["A","B"],"datasets":[{"data":[60,40]}]}}' --output ./pie.png

# Just get URL
./pammi-quickchart url --config ./chart.json --width 800

# python -m
python -m pammi_quickchart render --config ./chart.json --output ./chart.png
```

**Self-hosted QuickChart:** install via Docker or npm, then pass `--api-url http://localhost:3400`.

### pammi_bannerbear (STUB)

Renders branded templates (concept cards, quote cards) via the Bannerbear API.

**Setup (one-time):**
1. Sign up at https://www.bannerbear.com/
2. Get an API key from https://app.bannerbear.com/
3. Set: `export BANNERBEAR_API_KEY=bb_pr_xxxxx`
4. Create templates in the dashboard
5. Use the template IDs when calling

**Status check:**
```bash
./pammi-bannerbear status
# ✗ BANNERBEAR_API_KEY is NOT set
#   Set with: export BANNERBEAR_API_KEY=your_key_here
```

**Python API:**
```python
from pammi_bannerbear import BannerbearClient, BannerbearError, is_configured

if not is_configured():
    raise RuntimeError("Set BANNERBEAR_API_KEY first")

bb = BannerbearClient()
templates = bb.list_templates()
for t in templates:
    print(t["id"], t["name"])

# Create an image
result = bb.create_image(
    template_id="abc123",
    modifications=[
        {"name": "title", "text": "Hello World"},
        {"name": "subtitle", "text": "Subtitle"},
    ],
    sync=True,  # Wait for completion
)
print(result["image_url"])
```

**CLI:**
```bash
# Check setup
./pammi-bannerbear status

# List templates
./pammi-bannerbear list

# Get template details
./pammi-bannerbear get --template-id abc123

# Create image
./pammi-bannerbear create-image \
  --template-id abc123 \
  --modifications '[{"name":"title","text":"Hello"}]' \
  --output ./output.png
```

**Note:** This is a STUB. The API client is fully functional but not yet exercised against the live API. Once the user provides an API key, the client works as documented.
