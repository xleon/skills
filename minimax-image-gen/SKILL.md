---
name: minimax-image-gen
description: "Genera imágenes con la API de MiniMax (image-01) usando la key guardada en ~/.config/kilo/.env. Use when the user says genera una imagen, crea un dibujo, hazme un poster, render this prompt, necesito una ilustración, o quiere producir un JPG/PNG a partir de un texto descriptivo."
argument-hint: --prompt "<descripción>" [--aspect 1:1|16:9|9:16|4:3|3:4] [--out <ruta>]
user-invocable: true
---

# MiniMax Image Generation

## Cuándo usarla

Usa esta skill cuando el usuario quiera generar imágenes a partir de un texto (text-to-image) con la API de MiniMax. No es para editar una imagen existente.

Frases típicas:

- `genera una imagen de un gato tocando el berimbau`
- `hazme un poster minimalista del logo`
- `dibuja un paisaje de la Ribeira Sacra`
- `render this prompt in 16:9`

## Qué hace

Llama al endpoint `https://api.minimax.io/v1/image_generation` con el modelo `image-01`, devuelve una imagen en base64 y la guarda como JPG en el directorio configurado.

## API key

- Se busca en este orden:
  1. Variable de entorno `MINIMAX_API_KEY`.
  2. Archivo `~/.config/kilo/.env` (clave `MINIMAX_API_KEY=...`).
- Si no existe ninguna, la skill aborta con un mensaje claro.

## Directorio de salida por defecto

- Si no se pasa `--out`, se guarda en `<directorio actual del proyecto>/image-gen/<slug>.jpg`.
- El slug se deriva del prompt (lowercase, guiones, máx. 60 chars).
- Se crea `image-gen/` si no existe.
- Override con `IMAGE_GEN_DIR=/ruta/custom` o `--out ruta.jpg`.

## Procedimiento

1. Confirma el prompt con el usuario si es ambiguo.
2. Pregunta aspect ratio si importa (por defecto `1:1`).
3. Llama a `./scripts/minimax-generate.sh` con los flags adecuados.
4. Muestra la ruta del JPG resultante y, si es posible, previsualízalo con la tool de Read.

## Comandos

Generación básica (cuadrada, en image-gen/):

```bash
~/.config/kilo/skills/minimax-image-gen/scripts/minimax-generate.sh \
  --prompt "A cute cat playing a Brazilian berimbau" \
  --aspect 1:1
```

Generación con ruta explícita:

```bash
~/.config/kilo/skills/minimax-image-gen/scripts/minimax-generate.sh \
  --prompt "Mountain landscape at sunset, oil painting" \
  --aspect 16:9 \
  --out /Users/xleon/Projects/Icatú/image-gen/paisaje.jpg
```

Con referencia (conserva un sujeto):

```bash
~/.config/kilo/skills/minimax-image-gen/scripts/minimax-generate.sh \
  --prompt "The same character on a beach at sunset" \
  --ref https://example.com/character.jpg
```

## Notas

- Modelos disponibles: `image-01` (default). Cambiar con `--model`.
- Aspect ratios soportados: `1:1`, `16:9`, `9:16`, `4:3`, `3:4`.
- Respuesta siempre `response_format: base64` y guardado como `.jpg`.
- La skill NO usa internet salvo para la llamada al endpoint; la imagen se guarda localmente.
- Compatible con bash 3.2+ (default en macOS).
