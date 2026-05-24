---
name: solvency-study
description: "Use this skill to assess rental applicant solvency from project documents, with incremental analysis, public data cross-checking, and traffic-light risk output."
---

# Solvency Study

This skill evaluates rental solvency from documents and generates a reproducible report.

## Goal

- Extract data from documents (PDF, images, and markdown).
- Cross-link evidence within the project.
- Contrast company/activity data against public sources.
- Emit a solvency conclusion with traffic-light status (green, amber, red).
- Recommend additional checks (employment history, debt checks, etc.).

## Mandatory Flow

1. Ask scope before analyzing:
   - Scan the whole project.
   - Scan a specific folder.
   - Incremental mode (only new/changed files since the latest report).
2. Ask whether the user wants logical folder reorganization:
   - Default is DO NOT move files.
   - Offer dry-run preview first.
   - Move files only after explicit confirmation.
3. Detect available tools on the machine.
4. Run extraction by document type.
5. Cross-link entities (person, company, CIF/NIF, income, dates).
6. Run web cross-checks when useful.
7. Produce one full report (no separate summary report).

## Parameter Intake (User-Friendly Mode)

If the user does not provide required parameters, ask concise questions and continue after answers.

Required parameters to resolve before execution:

- `source_scope.mode`: `project` or `folder`.
- `source_scope.root`: required when mode is `folder`.

Optional parameters with defaults:

- `report_language`: default `auto`.
- `incremental_mode`: default `true`.
- `force_full_rescan`: default `false`.

Question order when missing values:

1. Scope (`project` or `folder`).
2. Folder path (only if `folder`).
3. Incremental options (`incremental_mode`, `force_full_rescan`).
4. Output language (`report_language`).

Rules:

- Ask only for missing values; do not re-ask already provided values.
- If user says "default" or gives no preference, apply defaults.
- Do not ask for `subject_id`.
- Derive incremental continuity key automatically:
  - If `source_scope.mode: folder`, use a normalized slug/hash from `source_scope.root`.
  - If `source_scope.mode: project`, use the workspace root slug/hash.
  - If user explicitly provides `subject_id`, use it as override without asking.
- Before execution, show resolved configuration in 5-8 lines and request one confirmation.
- If user denies confirmation, edit only requested fields and re-confirm.

## Language Policy (Auto)

- Skill instructions are written in English.
- Report output language is configurable through `report_language`:
  - `auto` (default): detect from user prompt language first, then local machine language, then fallback to English.
  - `es` or `en`: force output language.
- Keep technical keys in English in the technical metadata block, but localize all user-facing headings and prose.

Localization rules for final report output:

- Section titles must be in the resolved output language.
- Labels like "Reviewed files", "Incremental state", and manifest/delta headings must be localized.
- Only technical keys inside the metadata block remain in English.

Detection order when `report_language: auto`:

1. Prompt language (latest user prompt in this run).
2. Local language from environment (`LC_ALL`, `LC_MESSAGES`, `LANG`).
3. Fallback: `en`.

## System Capability Detection

Check these tools at startup:

- `pdftotext` (Poppler).
- OCR for scanned image/PDF (for example `tesseract`).
- Basic shell tools (`rg`, `sed`, `awk`).

Notes:

- `pdftotext` is NOT a Python library. It is a Poppler binary.
- Do not install dependencies by default.
- If a tool is missing, ask whether to install it or continue in reduced mode.

## Extraction Strategy

1. PDF with embedded text:
   - Prefer `pdftotext`.
2. Scanned PDF:
   - Use available OCR.
3. Images (invoices, transfers, WhatsApp):
   - OCR + financial entity extraction (date, amount, sender, recipient, reference).
4. Unreadable document:
   - Mark as unreadable and log required follow-up.

## Document Classification

Classify each file into one category:

- Payslip.
- Employment/commercial contract.
- Transfer/proof of payment.
- Debt/default report.
- Employment history report.
- Invoice.
- Informal evidence (screenshot/chat).
- Other.

## Evidence Rules

- Keep traceability from fact -> source file.
- Do not mix verified facts with inference.
- Tag confidence per extracted fact:
  - High: signed official document or primary source.
  - Medium: business/commercial directories.
  - Low: screenshots or unsupported claims.

## Solvency Traffic Light

- Green:
  - Verified stable income.
  - Consistent employer/company identity.
  - No known debt/default incidents.
- Amber:
  - Variable income or incomplete documents.
  - Partial consistency or missing key proofs.
- Red:
  - Serious inconsistencies or relevant risk incidents.

Always include:

- Final color.
- Reasons.
- Conditions to improve one level.

## Recommended Additional Checks

Suggest these where applicable:

- Updated employment history report.
- Debt/default report (BDMI/Idealista or equivalent).
- Latest payslips or bank statements (3-6 months).
- Invoices and payment proofs (freelancers/contractors).
- Current contract.
- Tax evidence when relevant.

## Report Output

Recommended names:

- `solvency_report_{subject}_{YYYY-MM-DD}.md`

Report must include:

1. Executive summary.
2. Findings by person.
3. Company analysis.
4. Traffic-light conclusion.
5. Recommendations.
6. Reviewed files list with links.
7. Technical metadata block at the end.

Metadata placement rules:

- Do not place metadata in frontmatter at the top.
- Place all operational metadata at the bottom in a fenced code block (recommended `yaml`).
- Keep this block compact and clearly titled (for example: "Technical metadata").

## Incremental Mode (required when previous report exists)

Use technical metadata block for incremental state:

```yaml
report_type: solvency_assessment
report_version: 1
subject_id: auto-derived-or-user-override
generated_at_utc: 2026-05-22T18:40:00Z
report_language: auto
incremental_mode: true
incremental_state_version: 1
incremental_checkpoint_at: 2026-05-22T18:40:00Z
incremental_manifest_hash: "sha256:..."
force_full_rescan: false
source_scope:
  mode: folder
  root: "analyzed/path"
```

Rules:

1. If `force_full_rescan: true`, run full scan.
2. Otherwise, load latest report by resolved continuity key (`subject_id` auto-derived unless overridden).
3. Compare inventory by `sha256` (fallback `size + mtime`).
4. Process only new/modified files.
5. Update manifest and delta block.

## Processed Files Manifest

Include table columns:

- path
- sha256
- size_bytes
- mtime_utc
- status
- extracted_at_utc

Also include delta summary:

- new_files
- modified_files
- unchanged_files
- deleted_files
- skipped_files

## Folder Reorganization (optional)

If user confirms reorganization, suggested structure:

- Use the user's report language for folder names, unless the user asks for a specific language.
- Preserve existing project naming language when adding folders into an established structure.
- Default examples:
  - `01_identity_and_contracts/`
  - `02_income/`
  - `03_debt_and_default_risk/`
  - `04_company_support/`
  - `05_generated_reports/`
  - `99_pending_review/`

Rules:

- Do not delete originals.
- Record before/after mapping.
- By default, do not create standalone files like reorganization dry-run or movement audit.
- Show dry-run preview inline in the response, and keep any technical reorganization metadata inside the final report metadata block.
- Only create separate reorganization files if the user explicitly asks to export them.
- If temporary helper files are created during execution, remove them before finishing.

## Guardrails

- Do not provide binding legal advice.
- Do not expose full sensitive identifiers in public summaries.
- If authenticity is uncertain, state uncertainty and avoid definitive claims.
