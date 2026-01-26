# Mandarin Vocabulary Tool

A CLI and web tool for learning Mandarin vocabulary with audio pronunciation.

## Setup

```bash
conda activate mandarin
# Dependencies: pypinyin, gTTS, pygame, flask
```

## Web App (Recommended)

```bash
python vocab_web.py
# Open http://localhost:5000
```

### Features

**Lookup tab**
- Search vocabulary and dictionary by English, Chinese characters, or pinyin
- Vocabulary: substring match for English and pinyin (`hao` finds `nihao`)
- Dictionary: exact pinyin match (to avoid overwhelming results)
- Supports toned pinyin input (e.g., `nǐ hǎo` or `ni3 hao3`)
- Shows pypinyin vs dictionary pinyin when they differ (tone sandhi)
- 10 results per page with "Load More" button

**Add tab**
- Search dictionary by pinyin or English definitions
- Auto-fills English from first dictionary definition
- Choose between dictionary pinyin (base tones) or pypinyin (with tone sandhi)
- Tone filtering: `zai4` shows only 4th tone matches
- Audio preview: play button on each match (uses gTTS)
- Duplicate detection: warns if characters already in vocabulary, offers "Add Anyway" or "Update Existing"
- 10 results per page with "Load More" button

**List tab**
- View all vocabulary entries
- Click any entry to edit (English, pinyin) or delete
- Focus star toggle: mark words for focused practice
- Optional quiz stats display (quiz and character stats separately)
- 10 results per page with "Load More" button

**Quiz tab**
- Configurable: show English/characters/pinyin/audio
- Answer with: characters/pinyin/English
- Order options: Random, Weighted (mistakes appear more often), In Order
- Focus only mode: practice only starred words from the List tab
- Pinyin answers accept both toned (`nǐ hǎo`) and numbered (`ni3 hao3`) formats
- Play Audio button available during quiz (for any mode)
- Manual "Next" button to control pacing
- After each answer, shows full entry with pypinyin/dictionary comparison when they differ
- Separate stats for meaning learning (`stats`) and character learning (`char_stats`)
  - Quiz modes involving characters use `char_stats`
  - English ↔ Pinyin modes use `stats`

**Quiz weighting (Settings → Quiz)**
- Formula: `weight = 1 + wrong_weight × log(1+wrong) − correct_weight × log(1+correct)`
- **Wrong weight** (default 1.0): Higher = more focus on mistakes
- **Correct weight** (default 0.5): Higher = faster reduction of priority
- **Max count** (default 20): Cap for correct/wrong counts per entry
- **Decay** (default 1): Correct answers reduce wrong count (and vice versa)

Example configurations:
- Focus on difficult: wrong_weight=2.0, correct_weight=0.3
- Balanced review: wrong_weight=0.5, correct_weight=0.5
- No decay: decay=0 (counts don't affect each other)

**English answer matching**
- Splits definitions by `/,;` - any part matches
- Strips "to " prefix (e.g., "go" matches "to go")
- Fuzzy matching fallback (80% similarity threshold)
- Particle definitions: accepts "particle" or keywords from definition

### Pinyin: Dictionary vs Pypinyin

The tool shows both pinyin versions when they differ:

| Characters | Dictionary | Pypinyin | Reason |
|------------|------------|----------|--------|
| 谢谢 | xiè xie | xiè xiè | Neutral tone in dict |
| 不客气 | bù kè qi | bú kè qì | Tone sandhi: 不→bú before 4th tone |
| 你好 | nǐ hǎo | ní hǎo | Tone sandhi: two 3rd tones |

- **Dictionary**: Base tones as listed in CC-CEDICT
- **Pypinyin**: Actual pronunciation with tone sandhi rules applied
- **Audio**: Always uses gTTS which applies natural pronunciation (pypinyin-style)

### Multiple Definitions

Use semicolons for multiple English meanings:
- `to thank; thanks` - searchable by either term

## CLI Usage

### Adding vocabulary

```bash
# With Chinese characters (pinyin auto-generated via pypinyin)
python vocab.py add "hello" --chars "你好"

# With pinyin (no tones) - shows all matches for selection
python vocab.py add "at" --pinyin "zai"

# With tone numbers - filters to matching tones only
python vocab.py add "at" --pinyin "zai4"          # 4th tone only
python vocab.py add "thank you" --pinyin "xie4 xie4"  # multi-syllable
```

### Looking up words

```bash
python vocab.py lookup hello           # substring match in English
python vocab.py lookup 你好            # exact character match
python vocab.py lookup "ni hao"        # pinyin (tones ignored)
python vocab.py lookup hello --exact   # exact English match only
```

### Listing and deleting

```bash
python vocab.py list
python vocab.py delete "at"      # by English
python vocab.py delete "在"       # by characters
python vocab.py delete 4         # by list number
```

### Quiz

```bash
python vocab.py quiz                    # English → Chinese (default)
python vocab.py quiz --mode cn2en       # Chinese → English
python vocab.py quiz --count 10         # 10 questions
```

## Pinyin Input Formats

| Input | Behaviour |
|-------|-----------|
| `zai` | Shows all "zai" entries |
| `zai4` | Shows only 4th tone entries |
| `nǐ hǎo` | Toned vowels work in search |
| `ni3 hao3` | Numbered tones filter results |

## Mandarin Tones

Mandarin has 4 tones plus a neutral tone:

| Tone | Number | Mark | Sound | Example |
|------|--------|------|-------|---------|
| 1st | 1 | ā | High, flat | mā (mother) |
| 2nd | 2 | á | Rising (like asking "what?") | má (hemp) |
| 3rd | 3 | ǎ | Dip (falling-rising) | mǎ (horse) |
| 4th | 4 | à | Falling (like a command) | mà (scold) |
| Neutral | 5 | a | Light, unstressed | ma (question particle) |

The neutral tone (5) appears in unstressed syllables and has no tone mark.

## Data

- Vocabulary: `data/vocabulary.json` (auto-created if missing)
- Config: `data/config.json` (quiz settings, auto-created with defaults)
- Audio files: `audio/` (generated via gTTS, can rebuild from Settings)
- Dictionary: `data/cedict.txt` (~124k entries from CC-CEDICT, auto-downloaded if missing)

### Configuration

Settings are stored in `data/config.json`:
```json
{
  "quiz": {
    "wrongWeight": 1.0,
    "correctWeight": 0.5,
    "maxCount": 20,
    "decay": 1
  }
}
```

### API Keys

For LLM-powered features (future), set the API key via environment variable:
```bash
export CLAUDE_API_KEY="sk-ant-..."
python vocab_web.py
```

The API key is never stored in config files for security.

**Audio rebuild modes (Settings → Audio)**
- **Smart rebuild**: Reuse existing audio where possible, generate only for missing entries
- **Renumber only**: Rename files to match current indices, no gTTS calls
- **Force rebuild**: Regenerate all audio from scratch (for corruption/quality issues)

## TODO

### Tone learning
**Pinyin chart with audio**
- Interactive grid: consonants × vowel combinations (ma, mao, mei, etc.)
- Each cell shows all 4 tones with audio playback
- Could filter by consonant group or vowel

**Tone recognition practice**
- Listen and identify the tone (1-4)
- Filter options:
  - Consonant groups (b/p/m/f, d/t/n/l, z/c/s, zh/ch/sh/r, j/q/x, g/k/h)
  - Vowel types (a, o, e, i, u, ü combinations)
  - Tone subsets (e.g., just tones 2 vs 3 for focused practice)
- Difficulty options:
  - Play comparison audio first (hear both tones before guessing)
  - Multiple choice vs free recall (show options or not)
- Track accuracy per tone/syllable combination

**Pronunciation practice (speech-to-text)**
- Use Web Speech API (browser-built-in, supports `zh-CN`) for basic testing
- Could upgrade to Whisper for better accuracy
- Test: play target audio → user records → compare transcription
- Track pronunciation accuracy over time

### Interactive conversation practice (LLM-powered)
- Use Claude API (Sonnet) for interactive Mandarin dialogue
- Focus on current class topics (configurable context/theme)
- Help functionality: click/ask about any word for explanation
- Audio playback via gTTS for bot responses
- Could include: simple dialogues, fill-in-the-blank, sentence correction
- Low traffic expected, minimal API costs

### Course material import (LLM-powered)
- Parse images/photos of textbook pages using Claude's vision
- Extract vocabulary lists → structured JSON → import to vocab app
- Extract exercises (fill-in-blank, translations, etc.) → generate quiz content
- PDF support: direct text extraction for digital materials
- Could batch-process multiple pages

### Other improvements
- Weighting formula refinements
- Subset/tag-based filtering for vocab
