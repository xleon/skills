# minimax-image-gen

Skill to generate images from text prompts using the MiniMax `image-01` model.

## What it does

- Calls the MiniMax Image Generation API (`/v1/image_generation`) with text-to-image.
- Optionally accepts a reference image to preserve a subject's identity.
- Decodes the base64 response and saves a JPG file locally.
- Default output directory: `<project>/image-gen/<slug>.jpg` (created if missing).

## Script

- `scripts/minimax-generate.sh` — bash wrapper (macOS bash 3.2+ compatible).

## API key

Resolution order:

1. `MINIMAX_API_KEY` environment variable.
2. `~/.config/kilo/.env` entry `MINIMAX_API_KEY=...`.

If neither is set, the script aborts with a clear message.

## Usage

Basic (1:1, saved to `<pwd>/image-gen/<slug>.jpg`):

```bash
~/Projects/.skills/minimax-image-gen/scripts/minimax-generate.sh \
  --prompt "A cute cat playing a Brazilian berimbau"
```

Custom aspect ratio and explicit output:

```bash
~/Projects/.skills/minimax-image-gen/scripts/minimax-generate.sh \
  --prompt "Mountain landscape at sunset, oil painting" \
  --aspect 16:9 \
  --out ~/Projects/Icatú/image-gen/paisaje.jpg
```

Override default output directory:

```bash
IMAGE_GEN_DIR=~/Pictures/minimax ~/Projects/.skills/minimax-image-gen/scripts/minimax-generate.sh \
  --prompt "A red apple"
```

With reference image (subject preservation):

```bash
~/Projects/.skills/minimax-image-gen/scripts/minimax-generate.sh \
  --prompt "The same character on a beach at sunset" \
  --ref https://example.com/character.jpg
```

## Supported options

| Flag         | Default | Notes                                            |
|--------------|---------|--------------------------------------------------|
| `--prompt`   | —       | Required. Description of the desired image.      |
| `--aspect`   | `1:1`   | `1:1`, `16:9`, `9:16`, `4:3`, `3:4`.             |
| `--out`      | auto    | Absolute path. Otherwise `<IMAGE_GEN_DIR>/<slug>.jpg`. |
| `--model`    | `image-01` | MiniMax image model id.                      |
| `--ref`      | —       | URL of a reference image (single subject).       |

## Environment variables

| Var                | Default                          | Purpose                          |
|--------------------|----------------------------------|----------------------------------|
| `MINIMAX_API_KEY`  | —                                | Required (or read from .env).    |
| `IMAGE_GEN_DIR`    | `$PWD/image-gen`                 | Default output directory.        |
| `MINIMAX_ENV_FILE` | `~/.config/kilo/.env`            | Override the env file location.  |

## Output

- A `.jpg` file at the resolved path.
- Filename slug: prompt lowercased, non-alphanumerics → `-`, max 60 chars.
- Existing files are overwritten.

## Notes

- No local dependencies beyond `curl` and Python 3 (used to encode/decode JSON+base64).
- API endpoint: `https://api.minimax.io/v1/image_generation`.
- Response format is always `base64`; saved as `.jpg`.
- Internet access is required only for the API call.
