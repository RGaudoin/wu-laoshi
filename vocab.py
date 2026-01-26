#!/usr/bin/env python3
"""
Mandarin vocabulary learning tool.

Usage:
    python vocab.py add "hello" --chars "你好"
    python vocab.py add "hello" --pinyin "ni hao"
    python vocab.py lookup hello
    python vocab.py lookup 你好
    python vocab.py quiz
    python vocab.py list
"""

import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import warnings
warnings.filterwarnings('ignore', category=UserWarning)

import argparse
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

# Optional imports - check availability
try:
    from pypinyin import pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False
    print("Warning: pypinyin not installed. Run: pip install pypinyin")

try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False
    print("Warning: gTTS not installed. Run: pip install gTTS")

try:
    import pygame
    pygame.mixer.init()
    HAS_PYGAME = True
except ImportError:
    HAS_PYGAME = False


# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
AUDIO_DIR = SCRIPT_DIR / "audio"
VOCAB_FILE = DATA_DIR / "vocabulary.json"
CEDICT_FILE = DATA_DIR / "cedict.txt"
CONFIG_FILE = DATA_DIR / "config.json"

# Default configuration
DEFAULT_CONFIG = {
    'quiz': {
        'wrongWeight': 1.0,
        'correctWeight': 0.5,
        'maxCount': 20,
        'decay': 1
    }
}


def download_cedict():
    """Download CC-CEDICT dictionary if not present."""
    import urllib.request
    import gzip

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    url = "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
    print(f"Downloading CC-CEDICT from {url}...")

    try:
        with urllib.request.urlopen(url) as response:
            compressed = response.read()

        print("Extracting...")
        decompressed = gzip.decompress(compressed)
        with open(CEDICT_FILE, 'wb') as f:
            f.write(decompressed)

        print(f"Dictionary saved to {CEDICT_FILE}")
        return True
    except Exception as e:
        print(f"Error downloading dictionary: {e}")
        return False


def load_cedict():
    """Load CC-CEDICT dictionary into a searchable structure."""
    if not CEDICT_FILE.exists():
        print(f"Dictionary not found at {CEDICT_FILE}")
        if not download_cedict():
            return {}, {}

    by_pinyin = {}  # pinyin (no tones) -> list of entries
    by_chars = {}   # characters -> entry

    with open(CEDICT_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('#'):
                continue
            # Format: 傳統 传统 [chuan2 tong3] /tradition/traditional/...
            match = re.match(r'^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+(.+)$', line.strip())
            if match:
                trad, simp, pinyin_numbered, definitions = match.groups()
                # Convert numbered pinyin to tone marks
                pinyin_toned = numbered_to_toned(pinyin_numbered)
                pinyin_plain = re.sub(r'[1-5]', '', pinyin_numbered.lower()).replace(' ', '')

                entry = {
                    'traditional': trad,
                    'simplified': simp,
                    'pinyin': pinyin_toned,
                    'pinyin_numbered': pinyin_numbered,
                    'definitions': definitions.strip('/').split('/')
                }

                # Index by simplified characters
                by_chars[simp] = entry
                by_chars[trad] = entry

                # Index by plain pinyin (no tones, no spaces)
                if pinyin_plain not in by_pinyin:
                    by_pinyin[pinyin_plain] = []
                by_pinyin[pinyin_plain].append(entry)

    return by_pinyin, by_chars


def numbered_to_toned(pinyin_numbered):
    """Convert numbered pinyin (ni3 hao3) to toned (nǐ hǎo)."""
    tone_marks = {
        'a': ['ā', 'á', 'ǎ', 'à', 'a'],
        'e': ['ē', 'é', 'ě', 'è', 'e'],
        'i': ['ī', 'í', 'ǐ', 'ì', 'i'],
        'o': ['ō', 'ó', 'ǒ', 'ò', 'o'],
        'u': ['ū', 'ú', 'ǔ', 'ù', 'u'],
        'ü': ['ǖ', 'ǘ', 'ǚ', 'ǜ', 'ü'],
        'v': ['ǖ', 'ǘ', 'ǚ', 'ǜ', 'ü'],  # v often used for ü
    }

    def convert_syllable(syl):
        # Find tone number at end
        match = re.match(r'^(.+?)([1-5])?$', syl.lower())
        if not match:
            return syl
        base, tone = match.groups()
        if not tone:
            return base
        tone = int(tone) - 1  # 0-indexed

        # Replace u: or v with ü
        base = base.replace('u:', 'ü').replace('v', 'ü')

        # Find vowel to mark (simplified rule: a/e always, else last vowel)
        for vowel in ['a', 'e']:
            if vowel in base:
                return base.replace(vowel, tone_marks[vowel][tone])
        # For ou, mark o
        if 'ou' in base:
            return base.replace('o', tone_marks['o'][tone])
        # Otherwise mark last vowel
        for vowel in ['i', 'o', 'u', 'ü']:
            if vowel in base:
                # Mark the last occurrence
                idx = base.rfind(vowel)
                return base[:idx] + tone_marks[vowel][tone] + base[idx+1:]
        return base

    syllables = pinyin_numbered.split()
    return ' '.join(convert_syllable(s) for s in syllables)


def chars_to_pinyin(chars):
    """Convert Chinese characters to pinyin with tone marks using pypinyin."""
    if not HAS_PYPINYIN:
        return None
    result = pinyin(chars, style=Style.TONE)
    return ' '.join([p[0] for p in result])


def strip_tones(pinyin_str):
    """Strip tone marks from pinyin, returning plain letters."""
    if not pinyin_str:
        return ''
    tone_map = {
        'ā': 'a', 'á': 'a', 'ǎ': 'a', 'à': 'a',
        'ē': 'e', 'é': 'e', 'ě': 'e', 'è': 'e',
        'ī': 'i', 'í': 'i', 'ǐ': 'i', 'ì': 'i',
        'ō': 'o', 'ó': 'o', 'ǒ': 'o', 'ò': 'o',
        'ū': 'u', 'ú': 'u', 'ǔ': 'u', 'ù': 'u',
        'ǖ': 'v', 'ǘ': 'v', 'ǚ': 'v', 'ǜ': 'v', 'ü': 'v',
    }
    result = pinyin_str.lower()
    for tone_char, plain_char in tone_map.items():
        result = result.replace(tone_char, plain_char)
    return result


def load_vocab():
    """Load user's vocabulary list. Creates empty file if missing."""
    if not VOCAB_FILE.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(VOCAB_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f)
        print(f"Created empty vocabulary at {VOCAB_FILE}")
        return []

    with open(VOCAB_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_vocab(vocab):
    """Save vocabulary list."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(VOCAB_FILE, 'w', encoding='utf-8') as f:
        json.dump(vocab, f, ensure_ascii=False, indent=2)


def load_config():
    """Load configuration. Creates default config if missing."""
    if not CONFIG_FILE.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return dict(DEFAULT_CONFIG)

    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)

    # Merge with defaults (in case new settings are added)
    merged = dict(DEFAULT_CONFIG)
    for key, value in config.items():
        if isinstance(value, dict) and key in merged:
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def save_config(config):
    """Save configuration."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)


def generate_audio(chars, entry_id):
    """Generate audio file for Chinese text."""
    if not HAS_GTTS:
        return None

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = AUDIO_DIR / f"{entry_id}.mp3"

    if not audio_path.exists():
        try:
            tts = gTTS(text=chars, lang='zh-CN')
            tts.save(str(audio_path))
        except Exception as e:
            print(f"Warning: Could not generate audio: {e}")
            return None

    return str(audio_path)


def play_audio(audio_path):
    """Play audio file."""
    if not audio_path or not os.path.exists(audio_path):
        return

    # Try pygame first (most reliable)
    if HAS_PYGAME:
        try:
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()
            import time
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            return
        except Exception:
            pass

    # Fallback to command-line players
    for player in ['mpv', 'ffplay', 'aplay', 'paplay']:
        try:
            subprocess.run([player, audio_path],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL,
                         check=True)
            return
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    print(f"Could not play audio. File: {audio_path}")


def cmd_add(args):
    """Add a word/phrase to vocabulary."""
    english = args.english
    chars = args.chars
    pinyin_input = args.pinyin

    vocab = load_vocab()
    by_pinyin, by_chars = load_cedict()

    entry = {
        'english': english,
        'characters': None,
        'pinyin': None,
        'audio': None
    }

    if chars:
        # Mode 1: Characters provided
        entry['characters'] = chars
        entry['pinyin'] = chars_to_pinyin(chars)
        if not entry['pinyin'] and chars in by_chars:
            entry['pinyin'] = by_chars[chars]['pinyin']

    elif pinyin_input:
        # Mode 2: Pinyin provided (with or without tones)
        pinyin_plain = re.sub(r'[1-5āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ ]', '', pinyin_input.lower())
        pinyin_plain = pinyin_plain.replace(' ', '')

        # Extract tone numbers from input for filtering (e.g., "zai4" → [4], "ni3 hao3" → [3, 3])
        input_tones = re.findall(r'[1-5]', pinyin_input)

        if pinyin_plain in by_pinyin:
            matches = by_pinyin[pinyin_plain]

            # Filter by tones if provided
            if input_tones:
                filtered = []
                for m in matches:
                    dict_tones = re.findall(r'[1-5]', m['pinyin_numbered'])
                    if dict_tones == input_tones:
                        filtered.append(m)
                if filtered:
                    matches = filtered

            if len(matches) == 1:
                match = matches[0]
                entry['characters'] = match['simplified']
                entry['pinyin'] = match['pinyin']
                print(f"Found: {match['simplified']} ({match['pinyin']}) - {', '.join(match['definitions'][:3])}")
            else:
                # Multiple matches - let user choose
                print(f"\nMultiple matches for '{pinyin_input}':")
                for i, m in enumerate(matches[:10]):
                    print(f"  {i+1}. {m['simplified']} ({m['pinyin']}) - {', '.join(m['definitions'][:2])}")

                choice = input("\nEnter number to select (or 0 to cancel): ").strip()
                if choice.isdigit() and 0 < int(choice) <= len(matches[:10]):
                    match = matches[int(choice)-1]
                    entry['characters'] = match['simplified']
                    entry['pinyin'] = match['pinyin']
                else:
                    print("Cancelled.")
                    return
        else:
            # Not found in dictionary - store pinyin as-is
            # Check if it has tone numbers and convert
            if re.search(r'[1-5]', pinyin_input):
                entry['pinyin'] = numbered_to_toned(pinyin_input)
            else:
                entry['pinyin'] = pinyin_input
            print(f"Note: '{pinyin_input}' not found in dictionary. Storing as provided.")
            # Ask for characters
            chars_input = input("Enter Chinese characters (or press Enter to skip): ").strip()
            if chars_input:
                entry['characters'] = chars_input

    else:
        print("Error: Provide either --chars or --pinyin")
        return

    # Generate audio if we have characters
    if entry['characters']:
        entry_id = f"{len(vocab):04d}_{entry['characters']}"
        entry['audio'] = generate_audio(entry['characters'], entry_id)

    vocab.append(entry)
    save_vocab(vocab)

    print(f"\nAdded: {entry['english']}")
    print(f"  Characters: {entry['characters']}")
    print(f"  Pinyin: {entry['pinyin']}")
    if entry['audio']:
        print(f"  Audio: {entry['audio']}")


def cmd_lookup(args):
    """Look up a word in vocabulary or dictionary."""
    query = args.query
    exact = getattr(args, 'exact', False)
    vocab = load_vocab()
    by_pinyin, by_chars = load_cedict()

    # Search in user's vocab first
    print("\n=== Your Vocabulary ===")
    found = False
    query_plain = strip_tones(query.replace(' ', ''))
    for entry in vocab:
        entry_pinyin_plain = strip_tones((entry.get('pinyin') or '').replace(' ', ''))
        if exact:
            # Exact match: full English, characters, or pinyin
            match = (query.lower() == entry['english'].lower() or
                    query == entry.get('characters') or
                    query_plain == entry_pinyin_plain)
        else:
            # Substring match for English
            match = (query.lower() in entry['english'].lower() or
                    query == entry.get('characters') or
                    query_plain == entry_pinyin_plain)
        if match:
            print(f"  {entry['english']}: {entry['characters']} ({entry['pinyin']})")
            if entry.get('audio'):
                play_audio(entry['audio'])
            found = True

    if not found:
        print("  (not in your vocabulary)")

    # Also search dictionary (only show if found)
    dict_results = []
    if query in by_chars:
        e = by_chars[query]
        dict_results.append(f"  {e['simplified']} ({e['pinyin']})")
        dict_results.append(f"  Definitions: {', '.join(e['definitions'][:5])}")
    else:
        # Try pinyin search
        pinyin_plain = re.sub(r'[ āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]', '', query.lower())
        if pinyin_plain in by_pinyin:
            for e in by_pinyin[pinyin_plain][:5]:
                dict_results.append(f"  {e['simplified']} ({e['pinyin']}) - {', '.join(e['definitions'][:2])}")

    if dict_results:
        print("\n=== Dictionary ===")
        for line in dict_results:
            print(line)


def cmd_list(args):
    """List all vocabulary."""
    vocab = load_vocab()
    if not vocab:
        print("Vocabulary is empty. Add words with: python vocab.py add \"english\" --chars \"中文\"")
        return

    print(f"\n=== Vocabulary ({len(vocab)} entries) ===\n")
    for i, entry in enumerate(vocab, 1):
        print(f"{i:3}. {entry['english']:20} {entry.get('characters', ''):10} {entry.get('pinyin', '')}")


def cmd_delete(args):
    """Delete a word from vocabulary."""
    query = args.query
    vocab = load_vocab()

    if not vocab:
        print("Vocabulary is empty.")
        return

    # Find matching entries
    matches = []
    for i, entry in enumerate(vocab):
        if (query.lower() == entry['english'].lower() or
            query == entry.get('characters') or
            query.isdigit() and int(query) == i + 1):
            matches.append((i, entry))

    if not matches:
        print(f"No entry found for '{query}'")
        return

    if len(matches) == 1:
        idx, entry = matches[0]
        print(f"Delete: {entry['english']} - {entry.get('characters')} ({entry.get('pinyin')})?")
        confirm = input("Confirm (y/n): ").strip().lower()
        if confirm == 'y':
            # Remove audio file if exists
            if entry.get('audio') and os.path.exists(entry['audio']):
                os.remove(entry['audio'])
            vocab.pop(idx)
            save_vocab(vocab)
            print("Deleted.")
        else:
            print("Cancelled.")
    else:
        print(f"Multiple matches for '{query}':")
        for i, (idx, entry) in enumerate(matches, 1):
            print(f"  {i}. {entry['english']} - {entry.get('characters')} ({entry.get('pinyin')})")
        choice = input("Enter number to delete (or 0 to cancel): ").strip()
        if choice.isdigit() and 0 < int(choice) <= len(matches):
            idx, entry = matches[int(choice) - 1]
            if entry.get('audio') and os.path.exists(entry['audio']):
                os.remove(entry['audio'])
            vocab.pop(idx)
            save_vocab(vocab)
            print("Deleted.")
        else:
            print("Cancelled.")


def cmd_quiz(args):
    """Quiz mode - test vocabulary."""
    vocab = load_vocab()
    if len(vocab) < 2:
        print("Need at least 2 vocabulary entries for quiz.")
        return

    mode = args.mode or 'en2cn'
    count = args.count or 5
    correct = 0

    entries = random.sample(vocab, min(count, len(vocab)))

    print(f"\n=== Quiz ({mode}) ===\n")

    for i, entry in enumerate(entries, 1):
        if mode == 'en2cn':
            print(f"{i}. What is '{entry['english']}' in Chinese?")
            if entry.get('audio'):
                input("  (Press Enter to hear audio)")
                play_audio(entry['audio'])
            answer = input("  Your answer (pinyin or characters): ").strip()

            is_correct = (answer == entry.get('characters') or
                         answer.lower() == (entry.get('pinyin') or '').lower().replace(' ', ''))

            if is_correct:
                print("  Correct!")
                correct += 1
            else:
                print(f"  Answer: {entry.get('characters')} ({entry.get('pinyin')})")

        elif mode == 'cn2en':
            print(f"{i}. What does '{entry.get('characters')}' ({entry.get('pinyin')}) mean?")
            if entry.get('audio'):
                play_audio(entry['audio'])
            answer = input("  Your answer: ").strip()

            is_correct = answer.lower() in entry['english'].lower()

            if is_correct:
                print("  Correct!")
                correct += 1
            else:
                print(f"  Answer: {entry['english']}")

        print()

    print(f"Score: {correct}/{len(entries)} ({100*correct//len(entries)}%)")


def main():
    parser = argparse.ArgumentParser(description='Mandarin vocabulary learning tool')
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Add command
    add_parser = subparsers.add_parser('add', help='Add a word/phrase')
    add_parser.add_argument('english', help='English meaning')
    add_parser.add_argument('--chars', '-c', help='Chinese characters')
    add_parser.add_argument('--pinyin', '-p', help='Pinyin (with or without tones)')

    # Lookup command
    lookup_parser = subparsers.add_parser('lookup', help='Look up a word')
    lookup_parser.add_argument('query', help='Word to look up (English, Chinese, or pinyin)')
    lookup_parser.add_argument('--exact', '-e', action='store_true',
                              help='Exact match only (no substring matching)')

    # List command
    subparsers.add_parser('list', help='List all vocabulary')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a word from vocabulary')
    delete_parser.add_argument('query', help='Word to delete (English, characters, or list number)')

    # Quiz command
    quiz_parser = subparsers.add_parser('quiz', help='Quiz yourself')
    quiz_parser.add_argument('--mode', '-m', choices=['en2cn', 'cn2en'],
                            help='Quiz mode (default: en2cn)')
    quiz_parser.add_argument('--count', '-n', type=int, help='Number of questions (default: 5)')

    args = parser.parse_args()

    if args.command == 'add':
        cmd_add(args)
    elif args.command == 'lookup':
        cmd_lookup(args)
    elif args.command == 'list':
        cmd_list(args)
    elif args.command == 'delete':
        cmd_delete(args)
    elif args.command == 'quiz':
        cmd_quiz(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
