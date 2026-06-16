# Pammi Drive Setup

## One-time setup

To set up the Google Drive folder structure for the Pammi Content System:

### 1. Authorize Google Drive with Composio

```bash
composio link googledrive
```

This opens a browser. Sign in with **`pammibot6@gmail.com`** and grant the requested permissions.

If you're in a headless environment, use:

```bash
composio link googledrive --no-wait
```

This will print a `redirect_url` (e.g., `https://connect.composio.dev/link/lk_xxxxx`). Open this URL in any browser and complete the authorization. Then verify with:

```bash
composio link googledrive --list
```

You should see at least one connected account.

### 2. Create the folder structure

Once Google Drive is connected, run:

```bash
./pammi-drive setup
```

This will:
1. Check if `/Pammi Content System/` exists; if not, create it
2. Create the `source/` subfolder if missing
3. Create the `exports/` subfolder if missing
4. Create `exports/linkedin/`, `exports/blogs/`, `exports/shorts/`, `exports/reels/`, `exports/x/`
5. Save all folder IDs to `drive-config.json`

The script is **idempotent** — safe to re-run.

### 3. Verify

```bash
./pammi-drive show
```

Should print the full folder config with IDs.

## After setup

Use `./pammi-drive upload <file> <platform>` to upload files, where `<platform>` is one of:

- `linkedin`
- `blog` (or `blogs`)
- `short` (or `shorts`)
- `reel` (or `reels`)
- `x` (or `twitter`)

## Folder structure

```
Pammi Content System/                 ← root
├── source/                            ← source files
└── exports/                           ← final exports
    ├── linkedin/
    ├── blogs/
    ├── shorts/
    ├── reels/
    └── x/
```

`source/` is for raw source files (PSD, Figma exports, etc.).
`exports/<platform>/` is for final published-ready assets.
