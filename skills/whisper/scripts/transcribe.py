#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "openai-whisper>=20250625",
# ]
# ///
"""
Transcribe or translate audio using OpenAI Whisper.

Usage:
    uv run transcribe.py <audio_file> [options]

Examples:
    uv run transcribe.py meeting.mp3
    uv run transcribe.py meeting.mp3 --model turbo --format json
    uv run transcribe.py speech.wav --language Japanese --task translate
    uv run transcribe.py podcast.mp3 --model small --timestamps
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe or translate audio using OpenAI Whisper"
    )
    parser.add_argument(
        "audio",
        help="Path to audio file (mp3, wav, flac, m4a, ogg, etc.)"
    )
    parser.add_argument(
        "--model", "-m",
        default="turbo",
        choices=["tiny", "tiny.en", "base", "base.en", "small", "small.en",
                 "medium", "medium.en", "large", "turbo"],
        help="Model size (default: turbo)"
    )
    parser.add_argument(
        "--language", "-l",
        default=None,
        help="Language of the audio (auto-detected if not set)"
    )
    parser.add_argument(
        "--task", "-t",
        default="transcribe",
        choices=["transcribe", "translate"],
        help="Task: transcribe (default) or translate to English"
    )
    parser.add_argument(
        "--format", "-f",
        default="text",
        choices=["text", "json", "srt", "vtt", "tsv"],
        help="Output format (default: text)"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file path (prints to stdout if not set)"
    )
    parser.add_argument(
        "--timestamps",
        action="store_true",
        help="Include word-level timestamps (json/srt/vtt formats)"
    )
    parser.add_argument(
        "--initial-prompt",
        default=None,
        help="Optional text to guide the model's style or continue a previous segment"
    )

    args = parser.parse_args()

    # Validate input file
    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"Error: Audio file not found: {args.audio}", file=sys.stderr)
        sys.exit(1)

    # Import whisper after arg validation
    import whisper

    # Load model
    print(f"Loading model '{args.model}'...", file=sys.stderr)
    model = whisper.load_model(args.model)

    # Transcribe
    print(f"Processing '{audio_path.name}'...", file=sys.stderr)
    result = model.transcribe(
        str(audio_path),
        language=args.language,
        task=args.task,
        word_timestamps=args.timestamps,
        initial_prompt=args.initial_prompt,
    )

    # Format output
    if args.format == "json":
        output = json.dumps({
            "text": result["text"],
            "language": result.get("language"),
            "segments": [
                {
                    "id": seg["id"],
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"],
                    **({"words": seg["words"]} if args.timestamps and "words" in seg else {}),
                }
                for seg in result["segments"]
            ],
        }, indent=2, ensure_ascii=False)
    elif args.format == "srt":
        lines = []
        for seg in result["segments"]:
            start = _format_timestamp_srt(seg["start"])
            end = _format_timestamp_srt(seg["end"])
            lines.append(f"{seg['id'] + 1}")
            lines.append(f"{start} --> {end}")
            lines.append(seg["text"].strip())
            lines.append("")
        output = "\n".join(lines)
    elif args.format == "vtt":
        lines = ["WEBVTT", ""]
        for seg in result["segments"]:
            start = _format_timestamp_vtt(seg["start"])
            end = _format_timestamp_vtt(seg["end"])
            lines.append(f"{start} --> {end}")
            lines.append(seg["text"].strip())
            lines.append("")
        output = "\n".join(lines)
    elif args.format == "tsv":
        lines = ["start\tend\ttext"]
        for seg in result["segments"]:
            lines.append(f"{seg['start']:.3f}\t{seg['end']:.3f}\t{seg['text'].strip()}")
        output = "\n".join(lines)
    else:
        output = result["text"].strip()

    # Write or print output
    if args.output:
        import os as _os
        out_path = Path(args.output).resolve()
        cwd = Path.cwd().resolve()
        if not (str(out_path).startswith(str(cwd) + _os.sep) or out_path == cwd):
            print(f"Error: Output path '{args.output}' is outside the current working directory.", file=sys.stderr)
            sys.exit(1)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Output saved: {out_path.resolve()}", file=sys.stderr)
    else:
        print(output)

    # Print detected language to stderr for agent consumption
    if result.get("language"):
        print(f"Detected language: {result['language']}", file=sys.stderr)


def _format_timestamp_srt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_timestamp_vtt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


if __name__ == "__main__":
    main()
