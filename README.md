# Pammi Tools

Shared Python utilities for the Pammi Content System. Currently includes:

- **`pammi_ids`** — Deterministic, human-readable ID generator

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
│   └── __init__.py         # Main library
├── pammi-ids               # CLI entry point
├── tests/
│   └── test_pammi_ids.py   # Unit tests
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
