# Development Notes

## Pinyin Handling

The tool tracks both CC-CEDICT and pypinyin readings and flags differences — useful for spotting tone sandhi:

| Characters | Dictionary | Pypinyin | Why |
|------------|------------|----------|-----|
| 不客气 | bù kè qi | bú kè qì | 不 → bú before 4th tone |
| 你好 | nǐ hǎo | ní hǎo | Two 3rd tones in sequence |

Supported pinyin input formats:

| Input | Behaviour |
|-------|-----------|
| `zai` | Shows all "zai" entries |
| `zai4` | Shows only 4th tone entries |
| `nǐ hǎo` | Toned vowels work in search |
| `ni3 hao3` | Numbered tones filter results |

## CLI

There's a command-line interface alongside the web app:

```bash
python vocab.py add "hello" --chars "你好"   # Add with characters
python vocab.py add "at" --pinyin "zai4"     # Add with pinyin (4th tone)
python vocab.py lookup hello                  # Search vocabulary
python vocab.py lookup 你好                   # Search by characters
python vocab.py list                          # List all entries
python vocab.py quiz --mode cn2en --count 10  # Quiz
```

## Data Files

All user data lives in `data/` and `audio/` (gitignored):

| File | Description |
|------|-------------|
| `data/vocabulary.json` | Your vocabulary (auto-created) |
| `data/config.json` | Settings incl. API key (auto-created) |
| `data/cedict.txt` | CC-CEDICT dictionary (auto-downloaded) |
| `data/pinyin_tones.json` | Syllable-to-character mapping (tracked) |
| `data/pinyin_stats.json` | Tone practice statistics (auto-created) |
| `audio/` | Generated pronunciation files |

## Quiz Modes

| Show | Answer with | Use case |
|------|-------------|----------|
| English | Pinyin | Learn pronunciation |
| English | Characters | Learn to write |
| Characters | English | Reading comprehension |
| Pinyin | English | Listening prep |
| Pinyin + Characters | English | Disambiguate homophones (e.g. 住 vs 祝) |
| Audio | English | Pure listening |

## TTS Options

| Option | Status | Notes |
|--------|--------|-------|
| **espeak-ng** (cmn-latn-pinyin) | Fallback | Synthetic quality but accurate tones, offline |
| **gTTS** (character-based) | Primary | Natural quality, uses real characters, needs network |

## Architecture

Single-file Flask backend (`vocab_web.py`) serving a single-page frontend (`templates/index.html` + `static/app.js`). Vocabulary stored as flat JSON. CC-CEDICT indexed in memory at startup.

The conversation trainer calls the Anthropic API from the backend — the API key never reaches the frontend.
