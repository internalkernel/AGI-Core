---
name: sag
description: High-quality text-to-speech using ElevenLabs API. Like macOS `say` but with modern AI voices. Supports streaming, file output, voice selection, speed control, and multiple models (v3, v2, v2.5 Flash/Turbo).
---

# SAG - ElevenLabs Text-to-Speech

High-quality TTS via the ElevenLabs API. Wraps the [steipete/sag](https://github.com/steipete/sag) Go binary.

## Usage

Run the wrapper script (maps `SAG_API_KEY` automatically):

**Speak text (streams to speakers):**
```bash
~/.openclaw/skills/sag/scripts/sag.sh "Hello world"
```

**Save to file (MP3/WAV/etc inferred from extension):**
```bash
~/.openclaw/skills/sag/scripts/sag.sh -o output.mp3 "Save this to a file"
```

**Choose a voice:**
```bash
~/.openclaw/skills/sag/scripts/sag.sh -v Roger "Hello in Roger's voice"
```

**List available voices:**
```bash
~/.openclaw/skills/sag/scripts/sag.sh -v ?
```

**Pipe input:**
```bash
echo "Piped text" | ~/.openclaw/skills/sag/scripts/sag.sh
```

## Options

| Flag | Description |
|------|-------------|
| `-v`, `--voice` | Voice name (default: auto). Use `-v ?` to list voices |
| `-o`, `--output` | Output file path (format inferred from extension: .mp3, .wav, etc.) |
| `--speed` | Speed multiplier (0.5-2.0, default: 1.0) |
| `-r`, `--rate` | Speech rate in words per minute |
| `--model-id` | Model: `eleven_v3` (default), `eleven_multilingual_v2`, `eleven_flash_v2_5`, `eleven_turbo_v2_5` |

## Voice Discovery

```bash
# List all voices
~/.openclaw/skills/sag/scripts/sag.sh voices

# Search voices by language or name
~/.openclaw/skills/sag/scripts/sag.sh voices --search english
~/.openclaw/skills/sag/scripts/sag.sh voices --search english --limit 10

# Quick voice picker
~/.openclaw/skills/sag/scripts/sag.sh -v ?
```

## Models

| Model | Best For |
|-------|----------|
| `eleven_v3` | Default, highest quality, supports audio tags |
| `eleven_multilingual_v2` | Stable, good for non-English |
| `eleven_flash_v2_5` | Fast and cheap |
| `eleven_turbo_v2_5` | Balanced speed/quality |

## v3 Audio Tags

The `eleven_v3` model supports inline audio tags for expressive speech:

- `[whispers]text[/whispers]` — whispering
- `[short pause]` — brief pause
- `[long pause]` — longer pause
- `[laughs]` — laughter
- `[sighs]` — sighing

Example:
```bash
~/.openclaw/skills/sag/scripts/sag.sh "[whispers]This is a secret[/whispers] [short pause] Just kidding!"
```

## Prompting Tips

Run `sag prompting` for model-specific prompting guidance from the binary itself.

## Environment

- **`SAG_API_KEY`** — Your ElevenLabs API key (set in `~/.bashrc`)
- The wrapper maps this to `ELEVENLABS_API_KEY` which the binary expects

## Examples

```bash
# Basic TTS
~/.openclaw/skills/sag/scripts/sag.sh "Good morning!"

# Save narration to file
~/.openclaw/skills/sag/scripts/sag.sh -v Roger -o narration.mp3 "Once upon a time..."

# Fast model for quick responses
~/.openclaw/skills/sag/scripts/sag.sh --model-id eleven_flash_v2_5 "Quick response"

# Slow dramatic reading
~/.openclaw/skills/sag/scripts/sag.sh --speed 0.8 -v Roger "The night was dark and stormy..."
```

## Notes

- Requires internet access (calls ElevenLabs API)
- Audio streaming to speakers requires audio output device
- On headless servers, use `-o file.mp3` to save to file instead
- First argument without a subcommand is treated as text to speak
