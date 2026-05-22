# solvency_report

Date: YYYY-MM-DD
Scope: folder or full project

Output language: resolved from `report_language` (auto | es | en)

Note: all user-facing headings in this report must be written in the resolved output language.

## 1) Executive Summary

- Key conclusions.
- Final solvency color: GREEN | AMBER | RED.

## 2) Findings by Person

### Person A

- Employment status.
- Verified income.
- Observed risks.

### Person B

- Employment status.
- Verified income.
- Observed risks.

## 3) Company Analysis

- Legal name.
- CIF/NIF.
- Business activity and CNAE (if available).
- Seniority or relevant milestones.
- Consistency with submitted documents.

## 4) Solvency Traffic Light

- Color: GREEN | AMBER | RED.
- Reasons.
- Conditions required to improve level.

## 5) Recommended Additional Checks

1. Updated employment history report.
2. Debt/default report.
3. Additional payslips/bank statements.
4. Invoices and payment proofs.
5. Any other missing documents.

## 6) Reviewed Files

- [path/to/file1.pdf](path/to/file1.pdf)
- [path/to/file2.jpeg](path/to/file2.jpeg)

## Technical metadata

```yaml
report_type: solvency_assessment
report_version: 1
subject_id: auto-derived-or-user-override
generated_at_utc: 2026-05-22T18:40:00Z
report_language: auto
incremental_mode: true
incremental_state_version: 1
incremental_checkpoint_at: 2026-05-22T18:40:00Z
incremental_manifest_hash: "sha256:REPLACE_ME"
force_full_rescan: false
source_scope:
  mode: folder
  root: "analyzed/path"
processed_files_manifest:
  - path: path/to/file1.pdf
    sha256: sha256:...
    size_bytes: 12345
    mtime_utc: 2026-05-22T17:00:00Z
    status: ok
    extracted_at_utc: 2026-05-22T18:40:00Z
delta_summary:
  new_files: 0
  modified_files: 0
  unchanged_files: 0
  deleted_files: 0
  skipped_files: 0
changed_files:
  - path/to/changed-file.pdf
skipped_files:
  - reason: unsupported_format
    path: path/to/file.bin
```
