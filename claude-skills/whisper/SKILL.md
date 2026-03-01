---
name: whisper
description: Transcribe or translate audio files using OpenAI Whisper. Supports all common audio formats, multiple languages, and outputs text/json/srt/vtt. Use for speech-to-text, meeting transcription, subtitle generation, and audio translation.
---

# Whisper - Speech-to-Text Transcription & Translation

Transcribe audio files or translate foreign-language audio to English using OpenAI's Whisper model. Runs locally (no API key needed).

## Usage

Run the script using absolute path (do NOT cd to skill directory first):

**Basic transcription:**
```bash
uv run ~/.claude/skills/whisper/scripts/transcribe.py audio.mp3
```

**With options:**
```bash
uv run ~/.claude/skills/whisper/scripts/transcribe.py audio.mp3 \
  --model turbo --format json --output transcript.json
```

**Translate to English:**
```bash
uv run ~/.claude/skills/whisper/scripts/transcribe.py foreign.wav \
  --task translate --language Japanese
```

## Options

| Flag | Description |
|------|-------------|
| `--model` / `-m` | Model size: `tiny`, `tiny.en`, `base`, `base.en`, `small`, `small.en`, `medium`, `medium.en`, `large`, `turbo` (default: `turbo`) |
| `--language` / `-l` | Audio language (auto-detected if omitted) |
| `--task` / `-t` | `transcribe` (default) or `translate` (to English). Note: `turbo` doesn't support translation — use `medium` or `large` |
| `--format` / `-f` | Output: `text` (default), `json`, `srt`, `vtt`, `tsv` |
| `--output` / `-o` | Save to file (prints to stdout if omitted) |
| `--timestamps` | Include word-level timestamps (useful with json/srt/vtt) |
| `--initial-prompt` | Guide model style or provide context |

## Model Selection Guide

| Need | Model | Notes |
|------|-------|-------|
| Fast, good quality | `turbo` | Best default. ~8x speed, good accuracy |
| Maximum accuracy | `large` | Slowest but most accurate |
| English only, fast | `base.en` or `small.en` | Optimized for English |
| Translation | `medium` or `large` | `turbo` can't translate |
| Low memory | `tiny` or `base` | ~1GB VRAM |

## Supported Audio Formats

Any format ffmpeg supports: `.mp3`, `.wav`, `.flac`, `.m4a`, `.ogg`, `.wma`, `.aac`, `.webm`, etc.

## Output Formats

- **text** — plain text transcript
- **json** — structured with segments, timestamps, detected language
- **srt** — SubRip subtitle format
- **vtt** — WebVTT subtitle format
- **tsv** — tab-separated (start, end, text)

## Examples

**Transcribe a meeting:**
```bash
uv run ~/.claude/skills/whisper/scripts/transcribe.py meeting.mp3 --format json --output meeting-transcript.json
```

**Generate subtitles:**
```bash
uv run ~/.claude/skills/whisper/scripts/transcribe.py video-audio.mp3 --format srt --output subtitles.srt --timestamps
```

**Quick transcription to stdout:**
```bash
uv run ~/.claude/skills/whisper/scripts/transcribe.py voicenote.m4a
```

**Translate Spanish audio:**
```bash
uv run ~/.claude/skills/whisper/scripts/transcribe.py spanish.mp3 --task translate --model medium
```

## Notes

- Runs fully locally — no API key or internet needed after model download
- First run downloads the model (~1.5GB for turbo); subsequent runs use cached model
- Models cached in `~/.cache/whisper/`
- Status messages go to stderr; transcript goes to stdout (clean for piping)
