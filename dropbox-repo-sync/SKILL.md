---
name: dropbox-repo-sync
description: "Set up automatic bidirectional sync between a Git repo and a local Dropbox folder on macOS, excluding Git-related paths and everything matched by .gitignore."
argument-hint: "<repo-path> <dropbox-path> [launchagent-label]"
---

# Dropbox Repo Sync

Installs a reusable sync stack in any repository:

- Bidirectional sync using `unison`
- Automatic file watching using `fswatch`
- Optional persistence with `launchd`
- Static Git exclusions (`.git`, `.gitignore`, `.gitattributes`, `.gitmodules`, `.github`)
- Dynamic exclusions from `.gitignore` via `git check-ignore --no-index`

## Canonical path

`/Users/xleon/Projects/.skills/dropbox-repo-sync`

## Usage

```bash
bash /Users/xleon/Projects/.skills/dropbox-repo-sync/setup-repo-sync.sh <repo-path> <dropbox-path> [launchagent-label]
```

Examples:

```bash
bash /Users/xleon/Projects/.skills/dropbox-repo-sync/setup-repo-sync.sh /Users/xleon/Projects/Coches /Users/xleon/Library/CloudStorage/Dropbox/Backups/Coches

bash /Users/xleon/Projects/.skills/dropbox-repo-sync/setup-repo-sync.sh /Users/xleon/Projects/MyRepo /Users/xleon/Library/CloudStorage/Dropbox/Backups/MyRepo com.user.myrepo-dropbox-sync
```

## After bootstrap

Run in target repo:

```bash
.tools/dropbox-sync/sync.sh --dry-run
.tools/dropbox-sync/sync.sh
.tools/dropbox-sync/watch.sh
.tools/dropbox-sync/status.sh
.tools/dropbox-sync/install-launchagent.sh
```

## Requirements

```bash
brew install unison fswatch
```

## Notes

- This skill is tailored for macOS (`launchd`).
- Destination must be a local Dropbox folder already managed by Dropbox Desktop.
