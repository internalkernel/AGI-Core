# nano-pdf

AI-powered PDF slide editor using Google Gemini 3 Pro Image.

Edit existing slides or generate new ones using natural language prompts. Preserves searchable text layers via OCR re-hydration.

## Installation

```bash
pip install nano-pdf
apt-get install poppler-utils tesseract-ocr
export GEMINI_API_KEY="your_api_key_here"
```

## Usage

### Edit existing slides

```bash
# Single page
nano-pdf edit deck.pdf 2 "Change the title to 'Q3 Results'"

# Multiple pages
nano-pdf edit deck.pdf 1 "Update date to Oct 2025" 5 "Add company logo" 10 "Fix typo in footer"
```

### Add new slides

```bash
# Insert at beginning
nano-pdf add deck.pdf 0 "Title slide with 'Q3 2025 Review'"

# Insert after page 5
nano-pdf add deck.pdf 5 "Summary slide with key takeaways"
```

### Options

| Flag | Description |
|------|-------------|
| `--use-context` / `--no-use-context` | Include full PDF text as context |
| `--style-refs "1,5"` | Pages to analyze for visual style matching |
| `--output "filename.pdf"` | Custom output filename |
| `--resolution "4K\|2K\|1K"` | Image quality (default: 4K) |
| `--disable-google-search` | Prevent model from using Google Search |

## Requirements

- Python 3.10+
- `GEMINI_API_KEY` env var (paid tier required for image generation)
- poppler-utils, tesseract-ocr
