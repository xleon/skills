---
name: repo-folder-sync
description: "Set up automatic bidirectional sync between a Git repo and a local folder on macOS"
argument-hint: "<repo-path> <destination-path-required> [launchagent-label]"
---

# Repo Folder Sync

Installs a reusable sync stack in any repository:

- Bidirectional sync using `unison`
- Automatic file watching using `fswatch`
- Persistent auto-sync with `launchd` enabled by default after successful setup
- Static Git exclusions (`.git`, `.gitignore`, `.gitattributes`, `.gitmodules`, `.github`)
- Dynamic exclusions from `.gitignore` via `git check-ignore --no-index`
- Automatically ensures `.gitignore` includes runtime paths for `.tools/repo-folder-sync/state/` and `.tools/repo-folder-sync/logs/`
- LaunchAgent runs with process name `repo-folder-sync-[folder]` where folder is sanitized (a-z, 0-9, '-') and shortened for readability
- Installer/uninstaller performs best-effort cleanup of legacy `*-dropbox-sync` launchd entries
- Launcher file name follows the same pattern: `repo-folder-sync-[folder]`

## Canonical path

`repo-folder-sync`

## Mandatory interaction rule

- The destination path must always be provided explicitly by the user.
- Never infer, auto-complete, or propose a default destination path and execute it without user confirmation.
- If destination path is missing or ambiguous, ask the user for the exact folder and wait for the answer before running any setup command.
- If proposing examples, present them only as examples and explicitly request the real destination path to use.

## Activation policy

- After a successful bootstrap and initial sync validation, activate persistent auto-sync by running `.tools/repo-folder-sync/install-launchagent.sh` without asking for extra confirmation.
- Do not ask the user whether to enable auto-sync unless the user explicitly requested manual mode or asked to decide later.
- If activation fails, report the error and leave manual sync available via `.tools/repo-folder-sync/sync.sh` and `.tools/repo-folder-sync/watch.sh`.

## Usage

```bash
bash repo-folder-sync/setup-repo-sync.sh <repo-path> <destination-path> [launchagent-label]
```

Examples:

```bash
bash repo-folder-sync/setup-repo-sync.sh ../Coches ../Sync/Coches

bash repo-folder-sync/setup-repo-sync.sh ../MyRepo ../Sync/MyRepo com.user.myrepo-folder-sync
```

## After bootstrap

Run in target repo:

```bash
.tools/repo-folder-sync/sync.sh --dry-run
.tools/repo-folder-sync/sync.sh
.tools/repo-folder-sync/install-launchagent.sh
.tools/repo-folder-sync/status.sh
```

Manual/on-demand mode (only when explicitly requested):

```bash
.tools/repo-folder-sync/watch.sh
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
