# semantic-organizer

Skill to classify, rename, and reorganize documents safely with dry-run controls.

## What it does

- Scans documents in a full project or selected folder.
- Extracts text from supported file types.
- Compares file names with detected content.
- Proposes classification and optional reorganization.
- Supports incremental mode to process only new or changed files.
- Can optionally generate a README index of analyzed files.

## Safety model

- Default behavior is non-destructive.
- Dry-run style preview is expected before applying changes.
- Move/rename actions require explicit user confirmation.

## Required input

- source_scope.mode: project or folder
- source_scope.root: required when mode is folder

## Optional input (defaults)

- incremental_mode: true
- force_full_rescan: false
- generate_readme_index: false
- apply_changes: false
- report_language: auto

## Typical flow

1. Confirm scan scope.
2. Confirm incremental behavior.
3. Confirm whether reorganization should be applied.
4. Confirm README index generation.
5. Run extraction and classification.
6. Present report with traceability details.

## Capability checks

At runtime, the workflow can check for tools such as:

- pdftotext
- tesseract
- rg, sed, awk, shasum

If tools are missing, continue in reduced mode or stop, based on user choice.

## Notes

- Folder naming and taxonomy language should stay consistent within each run.
- Existing project naming conventions should be preserved whenever possible.
