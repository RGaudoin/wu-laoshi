# Mandarin Vocabulary Learning Tool

## Environment

Use conda environment `mandarin`:
```bash
conda activate mandarin
```

Dependencies: `pypinyin`, `gTTS`, `flask`

## Project Structure

```
wu-laoshi/
├── vocab.py           # CLI tool for vocabulary management
├── vocab_web.py       # Flask web application
├── templates/
│   └── index.html     # Main web interface
├── static/
│   ├── app.js         # Frontend JavaScript
│   └── style.css      # Styles
├── schemas/
│   └── extraction_schema.json  # JSON Schema for lesson imports
├── data/
│   ├── vocabulary.json    # User vocabulary (gitignored)
│   ├── config.json        # User settings (gitignored)
│   ├── pinyin_tones.json  # Pinyin syllable → character mapping
│   ├── pinyin_stats.json  # Tone practice statistics (gitignored)
│   ├── cedict.txt         # CC-CEDICT dictionary (gitignored)
│   ├── backup/            # For user backups (gitignored)
│   └── import/            # For import files (gitignored)
└── audio/                 # Generated MP3 files (gitignored)
```

## Key Design Decisions

- Supports words AND phrases (multi-character entries)
- Three input modes:
  1. Characters provided → auto-generate pinyin
  2. Pinyin without tones → lookup in CC-CEDICT dictionary
  3. Pinyin with tone numbers → convert to tone marks
- Audio generated via Google TTS (gTTS)
- CC-CEDICT dictionary (~124k entries) for lookups

## Common Commands

```bash
# Run web app
python vocab_web.py

# CLI: Add with characters (pinyin auto-generated)
python vocab.py add "hello" --chars "你好"

# CLI: Add with pinyin (characters looked up)
python vocab.py add "hello" --pinyin "ni hao"

# CLI: Lookup
python vocab.py lookup hello
python vocab.py lookup 你好

# CLI: List all
python vocab.py list

# CLI: Quiz
python vocab.py quiz
python vocab.py quiz --mode cn2en --count 10
```

## Technical Notes

### Tone Practice Audio

The tone practice feature uses **espeak-ng** with the `cmn-latn-pinyin` voice to generate accurate tones directly from pinyin notation (e.g., `ma1`, `ma2`, `ma3`, `ma4`). This approach:

- Generates correct tones directly without character lookup
- Works offline (no API calls required)
- Supports all valid pinyin syllables

**Dependency:** `espeak-ng` must be installed:
```bash
sudo apt install espeak-ng
```

### TTS Options Reference

| Option | Status | Notes |
|--------|--------|-------|
| **espeak-ng** (cmn-latn-pinyin) | ✅ In use | Synthetic quality but accurate tones |
| **gTTS** | ❌ Replaced | Natural but no tone control |
| **Azure Speech TTS** | Alternative | Natural + tone control, requires API key |
| **ranchlai/mandarin-tts** | Alternative | High quality, requires PyTorch |

**References:**
- [espeak-ng GitHub](https://github.com/espeak-ng/espeak-ng)
- [Azure SSML Phonetic Sets](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-ssml-phonetic-sets)

## Future Enhancements
- Mobile-responsive design
- Spaced repetition algorithm
- Export to Anki format
- Import from course materials (PDF/image OCR)
