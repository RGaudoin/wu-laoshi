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
| **espeak-ng** (cmn-latn-pinyin) | ✅ Fallback | Synthetic quality but accurate tones, offline |
| **gTTS** (character-based) | 🔜 Planned | Natural quality, uses real characters, needs network |
| **Azure Speech TTS** | Alternative | Natural + tone control, requires API key |

**References:**
- [espeak-ng GitHub](https://github.com/espeak-ng/espeak-ng)
- [Azure SSML Phonetic Sets](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-ssml-phonetic-sets)

### Design: gTTS for Tone Practice Audio

**Problem:** espeak-ng produces synthetic/tinny audio. Azure requires an API key. gTTS already produces natural audio for vocabulary words.

**Idea:** Use gTTS with real characters instead of espeak-ng with raw pinyin. `pinyin_tones.json` already maps each syllable+tone to a representative character (e.g., ma1→妈, ma2→麻, ma3→马, ma4→骂). Feed that character to gTTS for natural pronunciation.

**Benefits:**
- Natural audio quality matching vocabulary TTS
- No new dependencies (gTTS already in use)
- Real-word examples reinforce vocabulary learning
- Could show character + English meaning alongside tone practice

**Implementation approach:**
1. Pre-generate audio for all syllable+tone combinations (~1200 files) as a one-time setup, stored in a dedicated directory (e.g., `audio/tones/`)
2. Curate `pinyin_tones.json` to ensure chosen characters are common and pronounce cleanly as single characters via gTTS
3. Fall back to espeak-ng for any syllable+tone combos where gTTS produces poor results or character is unavailable
4. Add a "generate tone audio" button in Settings (like existing audio rebuild)

**Risks to test:**
- gTTS with single characters may sometimes produce odd results (context-dependent pronunciation)
- Some rare syllable+tone combos may not have good representative characters
- Network dependency (mitigated by pre-generation and espeak-ng fallback)

## Future Enhancements
- gTTS-based tone practice audio (see design note above)
- Azure TTS as premium option
- Mobile-responsive design
- Spaced repetition algorithm
- Export to Anki format
