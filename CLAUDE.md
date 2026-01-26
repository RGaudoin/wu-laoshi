# Mandarin Vocabulary Learning Tool

## Environment

Use conda environment `mandarin`:
```bash
conda activate mandarin
```

Dependencies: `pypinyin`, `gTTS`

## Project Structure

- `vocab.py` - Main CLI tool for vocabulary management
- `data/` - Contains vocabulary.json (user data) and cedict.txt (dictionary)
- `audio/` - Generated pronunciation audio files (MP3)

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
# Add with characters (pinyin auto-generated)
python vocab.py add "hello" --chars "你好"

# Add with pinyin (characters looked up)
python vocab.py add "hello" --pinyin "ni hao"

# Lookup
python vocab.py lookup hello
python vocab.py lookup 你好

# List all
python vocab.py list

# Quiz
python vocab.py quiz
python vocab.py quiz --mode cn2en --count 10
```

## Future Enhancements

- Mobile web interface
- Spaced repetition algorithm
- Export to Anki format
- Categories/tags for vocabulary
