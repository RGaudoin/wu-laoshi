# Lesson Import System

## Overview

The extraction → import workflow separates:

1. **Extraction** (produces `extracted.json`): Reading textbook images/PDFs and structuring the content
2. **Import** (app feature): Validating, comparing with dictionary, and adding to vocabulary

## Directory Structure

```
data/import/                          # Gitignored - user content
├── book_name/                        # Optional: organise by textbook
│   ├── cover.jpg                     # Optional: book cover for reference
│   └── lesson_N/
│       ├── *.jpg                     # Source images
│       └── extracted.json            # Structured extraction
└── lesson_N/                         # Or flat structure
    └── extracted.json

schemas/
└── extraction_schema.json            # JSON Schema (tracked in git)
```

The import system recursively scans `data/import/` for `extracted.json` files, supporting nested folders for organisation by textbook.

## Extraction Methods

| Method | How | When to use |
|--------|-----|-------------|
| `claude-conversation` | Ask Claude in a conversation to read images and produce JSON | Ad-hoc imports, reviewing extraction |
| `claude-api` | Automated via Claude API | Batch processing, in-app automation |
| `manual` | Hand-written JSON | Corrections, custom content |
| `ocr` | Tesseract + post-processing | Offline, cost-free (lower accuracy) |

## Extraction Schema (v1)

See `schemas/extraction_schema.json` for the full JSON Schema. Key sections:

### Required
- **source**: Metadata (lesson number, textbook, extraction method, date)
- **vocabulary**: Array of vocab items with english, pinyin, characters

### Optional
- **proper_nouns**: Names (not imported to vocab, but useful for context)
- **dialogues**: Conversations for interactive practice
- **grammar_patterns**: Grammar points with explanations and examples
- **exercises**: Comprehension questions, fill-in-the-blank, etc.

## Vocabulary Item Format

```json
{
  "english": "how many",
  "pinyin": "jǐ",           // Tone marks or numbers accepted
  "characters": "几",
  "category": "pronoun",    // Optional: noun, verb, adjective, etc.
  "notes": null             // Optional: textbook notes
}
```

## Import Workflow (App)

1. **Preview**: `GET /api/import/preview?lesson=book/lesson_3`
   - Loads `extracted.json` from the specified path
   - Validates against schema
   - Compares each vocab item with existing vocabulary and pypinyin/CC-CEDICT
   - Returns items with status: `new`, `sandhi`, `new_not_in_dict`, `conflict`, `duplicate`

2. **Confirm**: `POST /api/import/confirm`
   - User selects which items to import
   - For conflicts, user chooses textbook or expected pinyin
   - Items added to vocabulary.json with audio generated

## Status Types

| Status | Meaning |
|--------|---------|
| `new` | Matches pypinyin/dictionary - ready to import |
| `sandhi` | Tone sandhi detected (textbook uses spoken form) - auto-accepted |
| `new_not_in_dict` | Not in CC-CEDICT but pypinyin can handle it |
| `conflict` | Pinyin differs from expected - user must review |
| `duplicate` | Already in vocabulary |

## Conflict Resolution

The import system uses `pypinyin` as the primary reference (same as the Add feature), since CC-CEDICT may store alternate/rare readings.

When textbook differs from expected pinyin:

```
Textbook:  不是 bú shì  (tone sandhi applied)
Expected:  不是 bú shì  (pypinyin - matches textbook)
Dict:      不是 bù shì  (citation form)
→ Status: sandhi (auto-accepted)

Textbook:  something unexpected
Expected:  different pinyin
→ Status: conflict (user reviews)
```

## Future Extensions

- Import dialogues → interactive listening/speaking practice
- Import grammar patterns → contextual help during quizzes
- Import exercises → auto-generate lesson-specific quizzes
- Claude API integration for automated extraction
