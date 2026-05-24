# Repository bidirectional sync (repo <-> destination folder)

This setup synchronizes a git repository with any local destination folder using `unison`.

## Behavior

- Bidirectional synchronization.
- Deletions are propagated.
- Static exclusions for Git-related paths.
- `.vscode` and `.tools` are excluded from sync.
- Dynamic exclusions for any path matched by `.gitignore`.

## Quick start

```bash
.tools/repo-folder-sync/sync.sh --dry-run
.tools/repo-folder-sync/sync.sh
.tools/repo-folder-sync/watch.sh
.tools/repo-folder-sync/status.sh
.tools/repo-folder-sync/install-launchagent.sh
```

## Disable or re-enable automatic sync

Disable background auto-sync (keeps toolkit files and manual sync commands):

```bash
.tools/repo-folder-sync/uninstall-launchagent.sh
```

Re-enable background auto-sync:

```bash
.tools/repo-folder-sync/install-launchagent.sh
```

You can still run one-off syncs manually while auto-sync is disabled:

```bash
.tools/repo-folder-sync/sync.sh
```

## Requirements

```bash
brew install unison fswatch
```

## Git ignore defaults

The bootstrap script adds these entries to `.gitignore` (if missing):

```text
.tools/repo-folder-sync/state/
.tools/repo-folder-sync/logs/
```

## Background process identity

- LaunchAgent starts a launcher named `repo-folder-sync`, so it is easier to identify in macOS background activity.
- Install/uninstall scripts also perform best-effort cleanup of legacy `*-dropbox-sync` launchd entries.

## Dynamic `.gitignore` resolution

Each sync cycle rebuilds dynamic ignore rules by running:

```bash
git -C <repo> check-ignore --no-index --stdin
```

over candidate relative paths from both sides.

## Logs

- `.tools/repo-folder-sync/logs/sync-*.log`
- `.tools/repo-folder-sync/logs/launchd.out.log`
- `.tools/repo-folder-sync/logs/launchd.err.log`
