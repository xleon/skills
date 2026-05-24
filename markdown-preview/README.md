# markdown-preview

Skill to customize VS Code Markdown preview with a styled theme.

## What it does

- Applies a ready-to-use CSS theme to Markdown preview.
- Configures VS Code settings so preview loads the selected stylesheet.
- Supports both light and dark themes.
- Lets you switch themes by reapplying the skill with another option.

## Available themes

Light themes:

- github-light
- solarized-light
- bear
- forest

Dark themes:

- one-dark
- dracula
- nord

## Usage

Use this skill and provide:

- theme name (optional, the skill can ask if missing)
- target project root (optional, defaults to current project context)

Typical flow:

1. Choose a theme.
2. Copy theme CSS into .vscode/markdown-preview.css.
3. Ensure .vscode/settings.json includes markdown.styles with that CSS path.
4. Open preview with Shift+Cmd+V to verify.

## Files used by this skill

- assets/theme-github-light.css
- assets/theme-solarized-light.css
- assets/theme-bear.css
- assets/theme-forest.css
- assets/theme-one-dark.css
- assets/theme-dracula.css
- assets/theme-nord.css
- assets/settings.json

## Notes

- This skill targets VS Code built-in Markdown preview.
- Reapplying with a new theme overwrites .vscode/markdown-preview.css by design.
