# Wu Laoshi (吴老师) - Mandarin Vocabulary Tool

A web and CLI tool for learning Mandarin vocabulary with audio pronunciation, tone practice, and course material import.

## Setup

```bash
conda activate mandarin
python vocab_web.py
# Open http://localhost:5000
```

**Dependencies:** `pypinyin`, `gTTS`, `flask`, `espeak-ng` (for tone practice)

```bash
pip install pypinyin gTTS flask
sudo apt install espeak-ng  # Linux
```

## Features

### Vocabulary Management
- **Add**: Search dictionary by pinyin or English, auto-fill definitions, preview audio
- **Lookup**: Search by English, Chinese characters, or pinyin (substring matching)
- **List**: View, edit, delete entries; mark words for focused practice

### Quiz
- Multiple modes: English ↔ Pinyin ↔ Characters
- Weighted ordering (mistakes appear more often) or random
- Focus mode for starred words
- Separate stats for meaning vs character learning

### Tones
- **Pinyin Chart**: Interactive grid with audio for all syllable/tone combinations
- **Tone Practice**: Listen and identify tones with configurable difficulty
- Currently uses espeak-ng (synthetic but accurate); Azure TTS planned for natural audio

### Import
- Import vocabulary from course materials (extracted JSON)
- Sandhi detection compares textbook vs dictionary forms
- Preview and select items before importing

## Pinyin Formats

| Input | Behaviour |
|-------|-----------|
| `zai` | Shows all "zai" entries |
| `zai4` | Shows only 4th tone entries |
| `nǐ hǎo` | Toned vowels work in search |
| `ni3 hao3` | Numbered tones filter results |

## Dictionary vs Pypinyin

The tool shows both pinyin versions when they differ:

| Characters | Dictionary | Pypinyin | Reason |
|------------|------------|----------|--------|
| 不客气 | bù kè qi | bú kè qì | Tone sandhi: 不→bú before 4th tone |
| 你好 | nǐ hǎo | ní hǎo | Tone sandhi: two 3rd tones |

## CLI Usage

```bash
python vocab.py add "hello" --chars "你好"   # Add with characters
python vocab.py add "at" --pinyin "zai4"     # Add with pinyin (4th tone)
python vocab.py lookup hello                  # Search vocabulary
python vocab.py list                          # List all entries
python vocab.py quiz --mode cn2en --count 10  # Quiz
```

## Data Files

| File | Description |
|------|-------------|
| `data/vocabulary.json` | User vocabulary (auto-created) |
| `data/config.json` | Settings (auto-created) |
| `data/cedict.txt` | CC-CEDICT dictionary (~124k entries, auto-downloaded) |
| `audio/` | Generated pronunciation files |

## Documentation

- [Import System](docs/import.md) - Importing course materials
- [CLAUDE.md](CLAUDE.md) - Developer/AI assistant context
