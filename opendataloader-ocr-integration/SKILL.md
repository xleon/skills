---
name: opendataloader-ocr-integration
description: Install and run opendataloader-pdf as a high-accuracy OCR/PDF extraction backend in any uv-managed Python project. Use as a fallback when pdfplumber/pypdf/tesseract produce unacceptable quality on scanned documents.
argument-hint: "[command: install|start|verify|diagnose]"
---

# OpenDataLoader PDF — OCR Integration

Generic, project-agnostic guide to install and operate `opendataloader-pdf` as an OCR backend. Works in any Python project that uses `uv` for dependency management (pyproject.toml with optional dependency groups).

This skill is **interactive**: it detects the environment and asks the user only for values that cannot be inferred.

## When to use

- Faster paths (pdfplumber → pypdf → tesseract) miss fiscal fields in noisy scans or thermal receipts.
- You need stronger OCR and can accept a slower runtime.
- You need help diagnosing Java / `uv` / architecture / backend startup failures.

## When NOT to use

- Default extraction works fine. Stay with pdfplumber/pypdf/tesseract — OpenDataLoader pulls ~2 GB of transitive deps.
- Project doesn't use `uv` (this skill assumes pyproject.toml + uv dependency groups).

## Baseline performance

| Engine | Speed | Quality on noisy/thermal scans | Dependencies |
|---|---|---|---|
| Tesseract | ~2 s/image | Medium | Light |
| OpenDataLoader hybrid | ~50 s/image | High | Heavy (~2 GB) |

## Commands

The skill supports a sub-command via argument-hint:

- `install` (default) — install the OCR dep group and verify the backend starts.
- `start` — start the hybrid backend in the foreground.
- `verify` — run the verification checklist only (no install).
- `diagnose` — print environment + connectivity diagnostics; suggest fixes.

If the user does not specify a command, default to `install`.

---

## Workflow

### Step 0 — Detect environment

Run from the project root:

```bash
uname -sm              # OS + arch (e.g. "Darwin arm64", "Linux x86_64")
java -version 2>&1     # Java availability
which uv && file "$(which uv)"   # uv binary location + arch
uv --version
```

Record: `OS`, `ARCH`, `JAVA_OK`, `UV_PATH`, `UV_ARCH`.

> ⚠️ **Rosetta trap on macOS arm64:** if `ARCH=Darwin arm64` but `UV_ARCH=x86_64`, your `uv` is running under Rosetta. OCR dependency resolution will install the wrong wheels. Stop and ask the user for the path to a native arm64 `uv` (commonly `/opt/homebrew/opt/uv/bin/uv` or `$(brew --prefix uv)/bin/uv`). Don't proceed until `UV_ARCH` matches `ARCH`.

### Step 1 — Ask for any required inputs

The skill is interactive. Use the `question` tool to collect **only what cannot be detected**:

1. **Project root path** — required if `pwd` is not the project you want to set up.
   - Question: "¿Cuál es la ruta del proyecto donde instalar el backend?"
   - Default: current working directory.
2. **OCR dependency group name** in pyproject.toml.
   - Question: "¿Cómo se llama el dependency group que instala opendataloader-pdf?"
   - Default: `ocr`. Confirm by reading `pyproject.toml` first; fall back to `ocr` if absent and warn the user.
3. **Hybrid backend port** (free TCP port).
   - Question: "¿En qué puerto quieres correr el backend híbrido?"
   - Default: `5002`. Verify it's free: `lsof -iTCP:5002 -sTCP:LISTEN`.
4. **OCR languages** (comma-separated BCP-47).
   - Question: "¿Qué idiomas quieres habilitar para OCR?"
   - Default: `es,en`. Mention that the model will download language packs on first run.
5. **Java path** (only if `JAVA_OK` is false).
   - Question: "¿Dónde está tu JDK 11+? (ruta absoluta a JAVA_HOME)"
   - Common candidates: `/Applications/Android Studio.app/Contents/jbr/Contents/Home`, `$(brew --prefix openjdk@11)/libexec/openjdk.jdk/Contents/Home`, `/usr/lib/jvm/java-11-openjdk-amd64`.
6. **uv binary path** (only if `UV_ARCH != ARCH` on macOS).
   - Question: "Indica la ruta al binario uv nativo (arm64 en Apple Silicon)."

Never ask for everything at once — only what's missing or ambiguous.

### Step 2 — Install (`install` command)

Confirm with the user before running each potentially destructive step:

```bash
# Activate the chosen Java (only if it was missing or wrong)
export JAVA_HOME="<JAVA_HOME>"
export PATH="$JAVA_HOME/bin:$PATH"
java -version

# Sync the project with the OCR group
<UV_PATH> sync
<UV_PATH> sync --group <GROUP_NAME>

# Verify imports
uv run python -c "import opendataloader_pdf; print('odl ok')"
uv run python -c "import numpy, pandas, PIL; print('deps ok')"
```

### Step 3 — Configure runtime

Ask the user where to store the OCR config. Common options:

- Environment variables in the user's shell rc (`~/.zshrc` / `~/.bashrc`).
- A project-local `.env` file (e.g. `configs/secrets.env` — adjust path/name per project).
- Process manager config (systemd unit, launchd plist, docker-compose).

Write whichever location the user prefers. Suggested values:

```env
OCR_ENGINE=opendataloader
ODL_HYBRID_PORT=<PORT>
ODL_BACKEND_AUTO_START=false
ODL_OCR_LANG=<LANG_CSV>
```

### Step 4 — Start backend (`start` command)

```bash
opendataloader-pdf-hybrid --port <PORT> --force-ocr --ocr-lang "<LANG_CSV>"
```

Tell the user that the first startup can take several minutes due to model download/load. In another shell:

```bash
curl -s http://localhost:<PORT>/health
```

If the health endpoint is not ready immediately, wait and retry. Do NOT assume a startup failure until 2–3 minutes have elapsed.

### Step 5 — Verify (`verify` command)

Run the full checklist (non-destructive):

```bash
uname -sm
java -version
<UV_PATH> --version
file "$(which uv)"
uv run python -c "import opendataloader_pdf; print('odl ok')"
uv run python -c "import numpy, pandas, PIL; print('deps ok')"
lsof -iTCP:<PORT> -sTCP:LISTEN
curl -s http://localhost:<PORT>/health
```

Report each step as PASS / FAIL with the relevant excerpt of output.

---

## Processing flow (generic)

```text
JPG/PNG
  → convert to PDF (Pillow)
  → opendataloader-pdf --hybrid docling-fast --hybrid-mode full
  → plain text output
  → project-specific extractor (regex / parsers / etc.)
```

When integrating this flow into project code, follow these conventions (the user's project must implement the actual extractor — this skill does NOT touch any source file):

1. Keep the fast path (pdfplumber/pypdf/tesseract) as the default.
2. Use OpenDataLoader only as a fallback when key fields are missing.
3. Require `--hybrid-mode full` and server-side `--force-ocr`.
4. Convert images to PDF before calling OpenDataLoader.

## Minimal manual test

After the backend is up:

```bash
# In another shell
python -c "from PIL import Image; Image.open('receipt.jpg').convert('RGB').save('/tmp/receipt.pdf', 'PDF', resolution=300)"
opendataloader-pdf --hybrid docling-fast --hybrid-mode full --format text -o /tmp/out /tmp/receipt.pdf
cat /tmp/out/receipt.txt
```

Substitute `receipt.jpg` for the actual test image.

---

## Troubleshooting (generic — apply with the values collected in Step 1)

### Java exists but the command fails in the user's shell

**Symptoms:** `java -version` fails; works in another terminal or IDE.

**Cause:** JDK not exported in the current shell's `PATH` / `JAVA_HOME`.

**Fix:** Export the JDK path before running OpenDataLoader commands (see Step 2).

### Mixed-architecture binaries (x86_64 vs arm64)

**Symptoms:** `mach-o file, but is an incompatible architecture` import errors for `numpy`, `pandas`, `PIL`, `torch`, `rpds`.

**Cause:** Rosetta / mixed installs.

**Fix:** Use a native `uv` (see Step 0). Rebuild from lock:

```bash
<UV_PATH> sync
<UV_PATH> sync --group <GROUP_NAME>
```

Avoid partial manual recovery with random `pip install` commands.

### `docling-parse` build appears stuck

**Cause:** Native build + heavy dep setup.

**Fix:** Let the build finish. Don't interrupt with Ctrl+C. If interrupted, retry from clean state.

### `uv sync --group <GROUP_NAME>` installs the wrong target

**Cause:** `uv` is running under Rosetta on Apple Silicon.

**Fix:** Verify with `file "$(which uv)"`. Use the native arm64 binary.

### Backend starts then exits on ImportError

**Cause:** Inconsistent dep state.

**Fix:** Reset and reinstall. Re-check imports:

```bash
uv run python -c "import opendataloader_pdf"
uv run python -c "import numpy, pandas, PIL"
```

### Health endpoint not ready immediately

**Cause:** Model init delay on first run.

**Fix:** Wait 2–3 minutes and retry.

### Port already in use

**Cause:** Another process holds the port.

**Fix:** Run `lsof -iTCP:<PORT>` and stop the offending process, or pick a different port in Step 1.

### Excluded platform (e.g. macOS x86_64)

**Cause:** `torch` wheels for that target may be unavailable.

**Fix:** Confirm with the user whether to switch to a supported target (arm64 / Linux) or drop the OCR dependency group. Do not silently change platform.

---

## Important constraints

- Never modify project source files (extractors, parsers, configs) without explicit user approval.
- Never run `uv sync --group <NAME>` without first confirming the dep group exists in `pyproject.toml`. If it doesn't exist, **ask** the user how to add it before proceeding.
- Always surface the final list of env vars the user needs to export in their shell session; don't assume the user's rc file will be edited automatically.
- The skill is read-only with respect to source code; it only runs install/start commands the user has approved.