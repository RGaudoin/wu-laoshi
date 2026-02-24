# Wu Laoshi (吴老师)

A web-based Mandarin vocabulary learning tool built to accompany the beginner course *Mandarin World 1A*. Named after Wu Laoshi, a character in the textbook.

It grew from a personal study aid into a fairly complete system for managing vocabulary, quizzing, practising tones, and exploring how Chinese words are built from individual characters. Not a polished product — just a tool that works well for one learner and might be useful to others on a similar path.

## Features

- **Vocabulary management** — add words manually or import from course materials; look up definitions via CC-CEDICT (~124k entries); auto-generate pinyin and audio
- **Quiz** — multiple modes (English, pinyin, characters, audio), weighted ordering so mistakes reappear, separate stats for meaning vs character recognition
- **Clickable characters** — click any Chinese character in the app to look it up; compound words auto-decompose into components (e.g. 手机 → 手 hand + 机 machine)
- **Tone practice** — interactive pinyin chart, configurable tone identification drills
- **Conversation practice** — AI-powered dialogue sessions using lesson materials (requires an LLM API key; currently uses Anthropic's Claude, but straightforward to swap for another provider)
- **Course material import** — extract vocabulary, dialogues, and grammar from textbook photos using an AI assistant, then import with duplicate detection and pinyin cross-referencing

## Quick Start

```bash
git clone https://github.com/RGaudoin/wu-laoshi.git
cd wu-laoshi

# Install dependencies
pip install flask pypinyin gTTS anthropic
sudo apt install espeak-ng   # for tone practice audio (Linux)

# Run
python vocab_web.py
# Open http://localhost:5000
```

The CC-CEDICT dictionary is downloaded automatically on first run.

### Conversation Practice (Optional)

The conversation trainer uses an LLM to roleplay dialogues from the course. Add your API key in Settings, or set:

```bash
export CLAUDE_API_KEY=your-key-here
```

Currently wired to the Anthropic API, but the integration is a single endpoint in `vocab_web.py` — easy to adapt to OpenAI, Ollama, or any other provider.

## Importing from Textbook Pages

The tool includes a workflow for extracting vocabulary from textbook photos:

1. **Photograph** your textbook pages and place the images in `data/import/book_name/lesson_N/`
2. **Extract** using the included Claude Code skill: `/extract-lesson data/import/book_name/lesson_N` — this reads the photos and produces a structured `extracted.json` with vocabulary, dialogues, and grammar
3. **Import** via the Import tab in the web app — preview everything, review pinyin against the dictionary, select what to add, and import with audio auto-generated

The extraction step requires [Claude Code](https://github.com/anthropics/claude-code) (or you can produce the JSON manually). See [docs/import.md](docs/import.md) for the schema and technical details.

## Documentation

- [Development notes](docs/development.md) — pinyin handling, CLI usage, data files
- [Import system](docs/import.md) — importing course materials
- [CLAUDE.md](CLAUDE.md) — context for AI coding assistants

## Acknowledgements

- **[CC-CEDICT](https://cc-cedict.org/)** — Chinese-English dictionary, licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
- **[pypinyin](https://github.com/mozillazg/python-pinyin)** — pinyin generation from characters
- **[gTTS](https://github.com/pndurette/gTTS)** — Google Text-to-Speech for pronunciation audio
- **[espeak-ng](https://github.com/espeak-ng/espeak-ng)** — offline tone practice audio

## Licence

[MIT](LICENSE)
