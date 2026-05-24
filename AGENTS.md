# Agent Instructions

- All commit messages in this repository must be written in **English**.
- Before committing changes to `install.sh`, test it locally by running `bash install.sh --help` and `bash install.sh --list`.

## Rules for adding a new skill

- Update the main `README.md` Skills table with the new skill and a short description.
- Ensure `install.sh` exposes that skill description in `--list` output (sourced from the skill `SKILL.md` frontmatter `description`).
- Include a detailed `README.md` inside each skill folder.
- Consider these checks mandatory before merge.
