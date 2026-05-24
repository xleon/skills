---
name: semantic-organizer
description: "Use this skill to classify, rename, and reorganize documents into logical folders with dry-run safety, optional README indexing, and incremental processing."
---

# Semantic Organizer

This skill organizes document files safely and traceably, with incremental validation and explicit confirmation before applying changes.

## Goal

- Classify documents into logical folders.
- Rename document files when the name does not match the actual content.
- Keep safe mode by default (no moves or deletions without confirmation).
- Support incremental mode to process only new or modified files.
- Optionally generate an indexed `README.md` with critical data per document.

## Mandatory flow

1. Ask for scope before analysis:
   - Scan the whole project.
   - Scan a specific folder.
   - Incremental mode (only new/changed files since the latest report).
2. Ask whether logical folder reorganization is desired:
   - Default is DO NOT move files.
   - Offer dry-run preview first.
   - Move/rename only after explicit confirmation.
3. Ask whether to generate a quick-read index:
   - Parameter `generate_readme_index`.
   - Default value: `false`.
4. Detect available tools on the machine.
5. Run extraction by document type.
6. Compare file name versus content (documents and document-like images only).
7. Produce final output with traceability and technical metadata.

## Parameter intake (user-friendly mode)

If parameters are missing, ask concise questions and continue.

Required parameters:

- `source_scope.mode`: `project` or `folder`.
- `source_scope.root`: required if `mode=folder`.

Optional parameters with defaults:

- `incremental_mode`: `true`.
- `force_full_rescan`: `false`.
- `generate_readme_index`: `false`.
- `apply_changes`: `false`.
- `report_language`: `auto`.

Question order when values are missing:

1. Scope (`project` or `folder`).
2. Folder path (if applicable).
3. Incremental options (`incremental_mode`, `force_full_rescan`).
4. Reorganization (`apply_changes`, default `false`).
5. README index (`generate_readme_index`, default `false`).
6. Output language (`report_language`).

Rules:

- Ask only for missing values.
- If the user says "default", apply defaults.
- Before execution, show the resolved configuration in 5-8 lines and request one confirmation.

## Language policy

- New folder naming MUST follow the dominant language of the project.
- Folder naming convention: Title Case and no numeric prefix.
- Do not mix folder languages in the same run.
- If language cannot be inferred, use `report_language` and keep it consistent across the created structure.

## Local capability detection

Check at startup:

- `pdftotext`.
- `tesseract`.
- Shell tools: `rg`, `sed`, `awk`, `shasum` (or hash alternative).

Rules:

- Do not install dependencies by default.
- If a key tool is missing, offer reduced mode or stop.

## Extraction strategy by type

1. PDF with embedded text:
   - Prefer `pdftotext`.
2. Scanned PDF:
   - Use OCR when available.
3. Document-like images (transfer screenshots, invoices, certificates):
   - OCR + key entity extraction.
4. Text documents (`.md`, `.txt`, etc.):
   - Direct text parsing.
5. Unreadable document:
   - Mark as `unreadable` and log follow-up.

## Document classification (adaptive)

Taxonomy is adaptive. Create folders based on detected types, keeping names clear and in Title Case.

Taxonomy language rule:

- If the project is in Spanish, use Spanish folder names.
- If the project is in English, use English folder names.
- If a previous structure exists, preserve its language when adding new folders.

Base category template (simple and optional):

- Use a small set of broad categories.
- Keep a review category for ambiguous cases.
- Keep a residual category for documents that cannot be classified with confidence.

Confusion-avoidance rules:

- Prefer fewer broad categories before many specific ones.
- Do not create new categories unless there is enough volume and a clear criterion.
- If ambiguous, classify temporarily as `Pending Review`.
- If the document does not fit with confidence, classify as `Other`.

Folder rules:

- Do not use numeric prefixes.
- Use Title Case for each folder name.
- Avoid unnecessary empty folders.
- Keep naming language consistent with the project.

## Name-content contrast rule

Apply semantic contrast only to:

- Documents (PDF, text, scanned files).
- Images that represent documents.

Do not apply to:

- Context photos (property, people, objects).
- Videos.

If name does not match content:

- Propose semantic rename in dry-run.
- Apply rename only after explicit confirmation.
- Keep origin -> destination traceability.

Recommended destination naming pattern (adaptable):

- Use a stable and readable semantic pattern.
- Include entity, document type, and date when available.
- Add a key field only when it improves disambiguation.

## Safety and deletion rules

- Never delete files by default.
- Do not move or rename without explicit confirmation.
- Allow deletion only for exact duplicates and only with user confirmation.

Duplicate check:

1. Hash comparison (preferred).
2. Fallback to `size + mtime` when hash is unavailable.
3. Show evidence before requesting deletion confirmation.

## Dry-run preview (mandatory before applying)

Show a proposal table with:

- `source`
- `proposed_destination`
- `action` (`move`, `rename`, `keep`, `duplicate_candidate`)
- `reason`
- `confidence`

Do not execute changes until explicit confirmation is received.

## Incremental mode

Incremental state based on continuity by scope:

- If `mode=folder`, use a key derived from `source_scope.root`.
- If `mode=project`, use a key derived from workspace root.

Rules:

1. If `force_full_rescan=true`, run full scan.
2. Otherwise, load previous continuity state.
3. Compare inventory by hash (fallback `size+mtime`).
4. Process only new/modified files.
5. Record delta (`new`, `modified`, `unchanged`, `deleted`, `skipped`).

## Indexed README (optional)

Only when `generate_readme_index=true`.

Output:

- Create or update `README.md` at the analyzed scope root.
- Goal: quick lookup of critical data without opening each file.

Recommended README structure:

1. Scope and date summary.
2. Index of detected document types.
3. Per-document cards with key fields.
4. Keywords for text search.
5. Recent changes (if incremental).

Minimum fields per document card:

- File
- Document type
- Main entities
- Relevant dates
- Amounts (if applicable)
- Key identifiers (DNI/NIF/CIF/VIN/policy/license plate/invoice)
- Short summary
- Confidence level (`high`, `medium`, `low`)

Generic extraction by type:

- Extract critical fields specific to each detected document.
- Prioritize entities, dates, amounts, and verifiable identifiers.
- For uncertain document types, extract detected fields dynamically.

## Final output

The skill must produce one main result with:

1. Resolved configuration.
2. Detected tools and limitations.
3. Classification summary.
4. Dry-run preview or applied changes.
5. Detected duplicates and final decision.
6. Reviewed files list.
7. Technical metadata block at the end.

## Technical metadata (at the end, not frontmatter)

Recommended format:

```yaml
report_type: semantic_organization
report_version: 1
generated_at_utc: 2026-05-25T00:00:00Z
report_language: auto
source_scope:
  mode: folder
  root: "path/analyzed"
incremental_mode: true
force_full_rescan: false
generate_readme_index: false
apply_changes: false
incremental_manifest_hash: "sha256:..."
delta:
  new_files: 0
  modified_files: 0
  unchanged_files: 0
  deleted_files: 0
  skipped_files: 0
```

## Validation criteria

1. Without explicit confirmation: no moves, renames, or deletes.
2. New folders in Title Case and no numbering prefixes.
3. Semantic rename only for documents and document-like images.
4. Non-document photos/videos are not renamed by content.
5. Deletion only for verified duplicates and only after confirmation.
6. Incremental behavior is correct across runs.
7. If `generate_readme_index=true`, `README.md` must be useful, complete, and search-friendly.
