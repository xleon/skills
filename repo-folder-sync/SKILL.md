---
name: repo-folder-sync
description: "Set up automatic bidirectional sync between a Git repo and a local folder on macOS"
argument-hint: "<repo-path> <destination-path> [launchagent-label]"
---

# Repo Folder Sync

Installs a reusable sync stack in any repository:

- Bidirectional sync using `unison`
- Automatic file watching using `fswatch`
- Optional persistence with `launchd`
- Static Git exclusions (`.git`, `.gitignore`, `.gitattributes`, `.gitmodules`, `.github`)
- Dynamic exclusions from `.gitignore` via `git check-ignore --no-index`
- Automatically ensures `.gitignore` includes runtime paths for `.tools/repo-folder-sync/state/` and `.tools/repo-folder-sync/logs/`
- LaunchAgent runs with process name `repo-folder-sync-[folder]` where folder is sanitized (a-z, 0-9, '-') and shortened for readability
- Installer/uninstaller performs best-effort cleanup of legacy `*-dropbox-sync` launchd entries
- Launcher file name follows the same pattern: `repo-folder-sync-[folder]`

## Canonical path

`/Users/xleon/Projects/.skills/repo-folder-sync`

## Usage

```bash
bash /Users/xleon/Projects/.skills/repo-folder-sync/setup-repo-sync.sh <repo-path> <destination-path> [launchagent-label]
```

Examples:

```bash
bash /Users/xleon/Projects/.skills/repo-folder-sync/setup-repo-sync.sh /Users/xleon/Projects/Coches /Users/xleon/Sync/Coches

bash /Users/xleon/Projects/.skills/repo-folder-sync/setup-repo-sync.sh /Users/xleon/Projects/MyRepo /Users/xleon/Sync/MyRepo com.user.myrepo-folder-sync
```

## After bootstrap

Run in target repo:

```bash
.tools/repo-folder-sync/sync.sh --dry-run
.tools/repo-folder-sync/sync.sh
.tools/repo-folder-sync/watch.sh
.tools/repo-folder-sync/status.sh
.tools/repo-folder-sync/install-launchagent.sh
```

Disable background auto-sync when needed:

```bash
.tools/repo-folder-sync/uninstall-launchagent.sh
```

Re-enable it later with:

```bash
.tools/repo-folder-sync/install-launchagent.sh
```

## Requirements

```bash
brew install unison fswatch
```

## Notes

- This skill is tailored for macOS (`launchd`).
- Destination can be any local folder.
