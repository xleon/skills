# Dropbox bidirectional sync (repo <-> local Dropbox)

This setup synchronizes a git repository with a local Dropbox folder using `unison`.

## Behavior

- Bidirectional synchronization.
- Deletions are propagated.
- Static exclusions for Git-related paths.
- `.vscode` and `.tools` are excluded from sync.
- Dynamic exclusions for any path matched by `.gitignore`.

## Quick start

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

## Dynamic `.gitignore` resolution

Each sync cycle rebuilds dynamic ignore rules by running:

```bash
git -C <repo> check-ignore --no-index --stdin
```

over candidate relative paths from both sides.

## Logs

- `.tools/dropbox-sync/logs/sync-*.log`
- `.tools/dropbox-sync/logs/launchd.out.log`
- `.tools/dropbox-sync/logs/launchd.err.log`
