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

## Security

### Fixes applied (2026-03-13)

Prompted by the McKinsey Lilli breach (SQL injection via JSON keys). No SQL is used here, but a scan revealed other vulnerabilities.

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | CRITICAL | `/api/audio` accepted arbitrary file paths via `path` param — could exfiltrate `/etc/passwd`, SSH keys, API key in `data/config.json` | Validate resolved path is within `AUDIO_DIR` using `os.path.realpath()` |
| 2 | HIGH | `lesson_id` from user input joined directly into filesystem paths — directory traversal via `../` | Added `_validate_lesson_id()` helper; rejects `..`, path separators, and verifies resolved path stays within `IMPORT_DIR` |
| 3 | HIGH | All vocabulary data interpolated into HTML via template literals + `innerHTML` with no escaping — stored XSS via malicious import files | Added `esc()` helper; applied across ~120 interpolation points in `app.js` |
| 7 | MEDIUM | `debug=True` hardcoded — Werkzeug interactive debugger gives full Python REPL on exception | Changed to `debug=False` |

### Remaining known issues

| Severity | Issue | Notes |
|----------|-------|-------|
| Low | No CSRF protection | Local-only app, low risk |
| Low | No rate limiting on API-proxying endpoints | Conversation trainer proxies to Anthropic API |
| Low | API key stored in plaintext JSON | `data/config.json` — gitignored but readable by process |
| Low | No Flask `secret_key` set | No session-based features currently |
