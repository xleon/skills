#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Uso: minimax-generate.sh --prompt "<texto>" [--out <ruta>] [--aspect 1:1|16:9|9:16|4:3|3:4] [--model image-01] [--ref <url>]

Variables de entorno:
  MINIMAX_API_KEY   API key (si no está, se lee de ~/.config/kilo/.env)

Si no se pasa --out, la imagen se guarda en <directorio del proyecto>/image-gen/<slug>.jpg
EOF
}

prompt=""
out=""
aspect="1:1"
model="image-01"
ref=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt) prompt="$2"; shift 2 ;;
    --out)    out="$2"; shift 2 ;;
    --aspect) aspect="$2"; shift 2 ;;
    --model)  model="$2"; shift 2 ;;
    --ref)    ref="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Argumento desconocido: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$prompt" ]]; then
  echo "Falta --prompt" >&2
  usage
  exit 1
fi

if [[ -z "${MINIMAX_API_KEY:-}" ]]; then
  env_file="${MINIMAX_ENV_FILE:-$HOME/.config/kilo/.env}"
  if [[ -f "$env_file" ]]; then
    MINIMAX_API_KEY="$(grep -E '^MINIMAX_API_KEY=' "$env_file" | cut -d= -f2-)"
    export MINIMAX_API_KEY
  fi
fi

if [[ -z "${MINIMAX_API_KEY:-}" ]]; then
  echo "MINIMAX_API_KEY no encontrada (ni en env ni en ~/.config/kilo/.env)" >&2
  exit 1
fi

if [[ -z "$out" ]]; then
  default_dir="${IMAGE_GEN_DIR:-$PWD/image-gen}"
  mkdir -p "$default_dir"
  slug="$(echo "$prompt" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g' | cut -c1-60)"
  [[ -z "$slug" ]] && slug="image"
  out="$default_dir/$slug.jpg"
fi

mkdir -p "$(dirname "$out")"

payload=$(python3 -c "
import json, sys
p = {
  'model': '$model',
  'prompt': sys.argv[1],
  'aspect_ratio': '$aspect',
  'response_format': 'base64',
}
if '$ref':
    p['subject_reference'] = [{'type': 'character', 'image_file': '$ref'}]
print(json.dumps(p))
" "$prompt")

resp_file="$(mktemp -t minimax-img.XXXXXX.json)"
http_code=$(curl -s -o "$resp_file" -w '%{http_code}' \
  -X POST 'https://api.minimax.io/v1/image_generation' \
  -H "Authorization: Bearer $MINIMAX_API_KEY" \
  -H 'Content-Type: application/json' \
  -d "$payload")

if [[ "$http_code" != "200" ]]; then
  echo "Error HTTP $http_code" >&2
  head -c 400 "$resp_file" >&2
  echo >&2
  rm -f "$resp_file"
  exit 1
fi

python3 -c "
import json, base64, sys
d = json.load(open('$resp_file'))
img = d['data']['image_base64'][0]
open(sys.argv[1], 'wb').write(base64.b64decode(img))
print('saved:', sys.argv[1], 'bytes=', len(base64.b64decode(img)))
" "$out"

rm -f "$resp_file"
