---
name: extract-lesson
description: Extract vocabulary, dialogues, and grammar from textbook lesson photos into extracted.json format for import into Wu Laoshi.
argument-hint: [lesson-folder-path]
---

# Extract Lesson from Textbook Photos

Extract structured content from textbook photos and produce an `extracted.json` file following the project's extraction schema.

## Input

The argument should be a path to the lesson folder containing photos, e.g.:
- `data/import/mandarin_world_l1a/lesson_7`
- Or just `lesson_7` (will resolve under the most recent textbook folder)

The folder should contain a subfolder with `.jpg` photos of textbook pages.

## Process

1. **Find photos**: Look for `.jpg` files in subfolders of the lesson directory
2. **Read all photos**: Read every image to understand the full lesson content
3. **Extract content** into the schema sections below
4. **Write** `extracted.json` to the lesson folder
5. **Report** a summary of what was extracted (counts of vocab, dialogues, etc.)

## What to Extract

### Vocabulary (required)

Include ALL of the following:

- **Core vocabulary list**: The labelled "Vocabulary" section — always include
- **Component characters**: When compound words are broken down (e.g. 手机 → 手 + 机), include the individual characters as separate entries. This helps learners understand how Mandarin builds words from related components.
- **Native expressions / set phrases**: Phrases from "Closer to Native" sections or similar (e.g. 祝你生日快乐, 没问题). Good for future-proofing.
- **Useful phrases from exercises**: Phrases that appear in examples or exercises and work as standalone vocabulary (e.g. 来吃饭, 去吃饭). These support the conversation trainer.

Each vocabulary item needs:
- `english`: English translation
- `pinyin`: Pinyin with tone marks (e.g. "nǐ hǎo")
- `characters`: Simplified Chinese characters
- `category`: One of: noun, verb, adjective, adverb, pronoun, particle, number, measure_word, conjunction, preposition, phrase, other
- `notes` (optional): Additional context from the textbook

**Do NOT** include:
- Proper nouns in the vocabulary list (put them in `proper_nouns` instead)
- Items that are clearly revision from earlier lessons (unless they appear in this lesson's vocab list)

### Dialogues (required if present)

Include:
- **Story Time / main dialogue**: The primary conversation — always include with full speaker, chinese, pinyin, and english per line
- **Conversation Flow**: Fill-in-the-blank dialogues — include as a separate dialogue entry. Fill in the blanks using context and answer keys if available.

### Grammar Patterns (include if present)

Extract grammar points with:
- `pattern`: The grammatical structure
- `explanation`: How it works
- `examples`: Array of {chinese, pinyin, english}

### Exercises (include if present)

Extract comprehension questions and exercises that have clear answers.

### Proper Nouns (include if present)

Names of people, places, brands etc. — separate from vocabulary.

## Output Format

Write `extracted.json` following this structure:

```json
{
  "source": {
    "lesson": 7,
    "title": "Lesson title in English",
    "title_chinese": "Chinese title",
    "title_pinyin": "pinyin of title",
    "textbook": "Mandarin World Level 1 ABC",
    "extracted_by": "claude-conversation",
    "extracted_date": "YYYY-MM-DD",
    "image_files": ["filename1.jpg", "filename2.jpg"]
  },
  "vocabulary": [...],
  "proper_nouns": [...],
  "dialogues": [...],
  "grammar_patterns": [...],
  "exercises": [...]
}
```

## Quality Notes

- Use tone marks in pinyin (nǐ hǎo), not tone numbers (ni3 hao3)
- The app's import preview will cross-reference pinyin with pypinyin and CC-CEDICT, so don't worry about verifying pinyin accuracy during extraction — just transcribe what the textbook shows
- For dialogues, include the speaker name in pinyin as shown in the textbook
- Set `extracted_date` to today's date
- List all image filenames in `source.image_files`

## Reference

See `data/import/mandarin_world_l1a/lesson_6/extracted.json` for a complete example of the expected output format.
