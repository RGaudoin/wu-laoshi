#!/usr/bin/env python3
"""
Mandarin Vocabulary Web App - Flask-based learning tool.
Run with: python vocab_web.py
Then open: http://localhost:5000
"""

import os
import json
import random
import re
from flask import Flask, render_template, request, jsonify

from vocab import (
    load_vocab, save_vocab, load_cedict, generate_audio,
    chars_to_pinyin, strip_tones, numbered_to_toned,
    load_config, save_config, DEFAULT_CONFIG,
    AUDIO_DIR
)

app = Flask(__name__)

# Load dictionary once at startup
print("Loading dictionary...")
BY_PINYIN, BY_CHARS = load_cedict()
print(f"Dictionary loaded: {len(BY_CHARS)} entries")
print(f"Vocabulary: {len(load_vocab())} entries")

# Load pinyin tone characters from JSON
DATA_DIR = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(DATA_DIR, 'data', 'pinyin_tones.json'), 'r', encoding='utf-8') as f:
    PINYIN_TONE_CHARS = json.load(f)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/lookup')
def api_lookup():
    query = request.args.get('q', '').strip()
    offset = int(request.args.get('offset', 0))
    limit = 10
    vocab = load_vocab()

    query_plain = strip_tones(query.replace(' ', ''))

    # Search vocabulary (substring match for English and pinyin, exact for characters)
    vocab_results = []
    for i, entry in enumerate(vocab):
        entry_pinyin_plain = strip_tones((entry.get('pinyin') or '').replace(' ', ''))
        if (query.lower() in entry['english'].lower() or
            query == entry.get('characters') or
            query_plain in entry_pinyin_plain):
            # Add pypinyin comparison and index
            v = dict(entry)
            v['_index'] = i
            chars = entry.get('characters')
            if chars:
                pypinyin_ver = chars_to_pinyin(chars)
                dict_pinyin = BY_CHARS.get(chars, {}).get('pinyin')
                if pypinyin_ver and dict_pinyin and pypinyin_ver != dict_pinyin:
                    v['pinyin_pypinyin'] = pypinyin_ver
                    v['pinyin_dict'] = dict_pinyin
            vocab_results.append(v)

    # Search dictionary - collect all matches first
    all_dict_results = []
    if query in BY_CHARS:
        all_dict_results.append(BY_CHARS[query])
    else:
        pinyin_plain = strip_tones(query).replace(' ', '')
        if pinyin_plain in BY_PINYIN:
            all_dict_results = BY_PINYIN[pinyin_plain]

    # Paginate dictionary results
    dict_total = len(all_dict_results)
    dict_results = all_dict_results[offset:offset + limit]

    # Add pypinyin version for dictionary results
    dict_with_pypinyin = []
    for d in dict_results:
        entry = dict(d)
        pypinyin_ver = chars_to_pinyin(d['simplified'])
        if pypinyin_ver and pypinyin_ver != d['pinyin']:
            entry['pinyin_pypinyin'] = pypinyin_ver
        dict_with_pypinyin.append(entry)

    return jsonify({
        'vocab': vocab_results,
        'dict': dict_with_pypinyin,
        'dict_total': dict_total,
        'dict_offset': offset,
        'dict_has_more': offset + limit < dict_total
    })


@app.route('/api/search_pinyin')
def api_search_pinyin():
    query = request.args.get('p', '').strip()
    offset = int(request.args.get('offset', 0))
    limit = 10
    if not query:
        return jsonify({'matches': [], 'total': 0, 'has_more': False})

    matches = []

    # Try pinyin search first - use strip_tones to convert ǐ→i etc, then remove spaces/numbers
    pinyin_plain = re.sub(r'[1-5 ]', '', strip_tones(query))
    input_tones = re.findall(r'[1-5]', query)

    if pinyin_plain in BY_PINYIN:
        matches = BY_PINYIN[pinyin_plain][:]  # Copy to avoid modifying original

        # Filter by tones if provided
        if input_tones:
            filtered = []
            for m in matches:
                dict_tones = re.findall(r'[1-5]', m['pinyin_numbered'])
                if dict_tones == input_tones:
                    filtered.append(m)
            if filtered:
                matches = filtered

    # Also search by English definition if no pinyin matches or query looks like English
    if not matches or ' ' in query or not query.replace(' ', '').isalpha():
        query_lower = query.lower()
        seen_chars = {m['simplified'] for m in matches}
        for entry in BY_CHARS.values():
            if entry['simplified'] not in seen_chars:
                for defn in entry['definitions']:
                    if query_lower in defn.lower():
                        matches.append(entry)
                        seen_chars.add(entry['simplified'])
                        break
            if len(matches) >= 100:  # Collect more for pagination
                break

    # Paginate results
    total = len(matches)
    paginated = matches[offset:offset + limit]

    # Add pypinyin version for each match
    results = []
    for m in paginated:
        entry = dict(m)  # Copy
        pypinyin_ver = chars_to_pinyin(m['simplified'])
        if pypinyin_ver and pypinyin_ver != m['pinyin']:
            entry['pinyin_pypinyin'] = pypinyin_ver
        results.append(entry)

    return jsonify({
        'matches': results,
        'total': total,
        'offset': offset,
        'has_more': offset + limit < total
    })


@app.route('/api/pinyin_lookup')
def api_pinyin_lookup():
    """Lookup pinyin options for given characters."""
    chars = request.args.get('chars', '').strip()
    if not chars:
        return jsonify({'dict': None, 'pypinyin': None})

    result = {'dict': None, 'pypinyin': None}

    # Get dictionary pinyin
    if chars in BY_CHARS:
        result['dict'] = BY_CHARS[chars]['pinyin']

    # Get pypinyin version
    pypinyin_ver = chars_to_pinyin(chars)
    if pypinyin_ver:
        result['pypinyin'] = pypinyin_ver

    return jsonify(result)


@app.route('/api/add', methods=['POST'])
def api_add():
    data = request.json
    english = data.get('english', '').strip()
    chars = data.get('chars', '').strip()
    pinyin = data.get('pinyin', '').strip()
    tags = data.get('tags', [])  # Optional tags array
    force = data.get('force', False)  # Add anyway despite duplicate
    update = data.get('update', False)  # Update existing entry

    if not english:
        return jsonify({'success': False, 'error': 'English required'})
    if not chars and not pinyin:
        return jsonify({'success': False, 'error': 'Characters or pinyin required'})

    # Track both pinyin sources for comparison
    pinyin_pypinyin = None
    pinyin_dict = None

    # Get pinyin from characters if needed
    if chars and not pinyin:
        pinyin_pypinyin = chars_to_pinyin(chars)
        if chars in BY_CHARS:
            pinyin_dict = BY_CHARS[chars]['pinyin']
        # Use pypinyin by default, fall back to dictionary
        pinyin = pinyin_pypinyin or pinyin_dict
    elif chars:
        # Pinyin was provided (from dictionary selection), but also get pypinyin for reference
        pinyin_pypinyin = chars_to_pinyin(chars)
        if chars in BY_CHARS:
            pinyin_dict = BY_CHARS[chars]['pinyin']

    vocab = load_vocab()

    # Check for duplicates (by characters)
    existing_idx = None
    existing_entry = None
    if chars:
        for i, v in enumerate(vocab):
            if v.get('characters') == chars:
                existing_idx = i
                existing_entry = v
                break

    # If duplicate found and not forcing/updating, return warning
    if existing_entry and not force and not update:
        return jsonify({
            'success': False,
            'duplicate': True,
            'existing': existing_entry,
            'error': f'"{chars}" already in vocabulary'
        })

    # Generate audio (reuse existing if updating and audio exists)
    audio_path = None
    if chars:
        if update and existing_entry and existing_entry.get('audio'):
            audio_path = existing_entry['audio']
        else:
            # Find next available ID (max existing + 1, never reuses deleted IDs)
            import re
            max_id = -1
            for v in vocab:
                if v.get('audio'):
                    match = re.match(r'.*?(\d{4})_', v['audio'])
                    if match:
                        max_id = max(max_id, int(match.group(1)))
            next_id = max_id + 1
            entry_id = f"{next_id:04d}_{chars}"
            audio_path = generate_audio(chars, entry_id)

    entry = {
        'english': english,
        'characters': chars,
        'pinyin': pinyin,
        'audio': audio_path
    }
    if tags:
        entry['tags'] = tags

    if update and existing_idx is not None:
        # Update existing entry, preserving stats
        if 'stats' in vocab[existing_idx]:
            entry['stats'] = vocab[existing_idx]['stats']
        if 'char_stats' in vocab[existing_idx]:
            entry['char_stats'] = vocab[existing_idx]['char_stats']
        if 'focus' in vocab[existing_idx]:
            entry['focus'] = vocab[existing_idx]['focus']
        vocab[existing_idx] = entry
    else:
        # Add new entry
        vocab.append(entry)

    save_vocab(vocab)

    # Include both pinyin versions in response for user info
    result = {'success': True, 'entry': entry}
    if pinyin_pypinyin and pinyin_dict and pinyin_pypinyin != pinyin_dict:
        result['pinyin_pypinyin'] = pinyin_pypinyin
        result['pinyin_dict'] = pinyin_dict

    return jsonify(result)


@app.route('/api/edit', methods=['POST'])
def api_edit():
    """Edit a vocabulary entry (English, pinyin, and/or tags)."""
    data = request.json
    index = data.get('index')
    english = data.get('english')
    pinyin = data.get('pinyin')
    tags = data.get('tags')  # Can be [] to clear tags

    vocab = load_vocab()
    if index is None or index < 0 or index >= len(vocab):
        return jsonify({'success': False, 'error': 'Invalid index'})

    entry = vocab[index]

    if english is not None:
        entry['english'] = english.strip()
    if pinyin is not None:
        entry['pinyin'] = pinyin.strip()
    if tags is not None:
        if tags:
            entry['tags'] = tags
        elif 'tags' in entry:
            del entry['tags']  # Remove empty tags

    save_vocab(vocab)
    return jsonify({'success': True, 'entry': entry})


@app.route('/api/tags')
def api_tags():
    """Get all unique tags from vocabulary."""
    vocab = load_vocab()
    tags = set()
    for entry in vocab:
        for tag in entry.get('tags', []):
            tags.add(tag)
    return jsonify({'tags': sorted(tags)})


@app.route('/api/list')
def api_list():
    offset = int(request.args.get('offset', 0))
    limit = int(request.args.get('limit', 0))  # 0 means all (for quiz)
    tag_filter = request.args.get('tag', '')  # Optional tag filter
    vocab = load_vocab()

    # Filter by tag if specified
    if tag_filter:
        vocab = [v for v in vocab if tag_filter in v.get('tags', [])]

    # Add pypinyin comparison for each entry
    vocab_with_pypinyin = []
    for entry in vocab:
        v = dict(entry)
        chars = entry.get('characters')
        if chars:
            pypinyin_ver = chars_to_pinyin(chars)
            dict_pinyin = BY_CHARS.get(chars, {}).get('pinyin')
            if pypinyin_ver and dict_pinyin and pypinyin_ver != dict_pinyin:
                v['pinyin_pypinyin'] = pypinyin_ver
                v['pinyin_dict'] = dict_pinyin
        vocab_with_pypinyin.append(v)

    total = len(vocab_with_pypinyin)
    if limit > 0:
        paginated = vocab_with_pypinyin[offset:offset + limit]
        has_more = offset + limit < total
    else:
        paginated = vocab_with_pypinyin
        has_more = False

    return jsonify({
        'vocab': paginated,
        'total': total,
        'offset': offset,
        'has_more': has_more
    })


@app.route('/api/delete', methods=['POST'])
def api_delete():
    data = request.json
    index = data.get('index')

    vocab = load_vocab()
    if index is None or index < 0 or index >= len(vocab):
        return jsonify({'success': False, 'error': 'Invalid index'})

    entry = vocab[index]
    # Remove audio
    if entry.get('audio') and os.path.exists(entry['audio']):
        os.remove(entry['audio'])
    vocab.pop(index)
    save_vocab(vocab)
    return jsonify({'success': True})


@app.route('/api/toggle_focus', methods=['POST'])
def api_toggle_focus():
    """Toggle focus flag for a vocabulary entry."""
    data = request.json
    index = data.get('index')

    vocab = load_vocab()
    if index is None or index < 0 or index >= len(vocab):
        return jsonify({'success': False, 'error': 'Invalid index'})

    entry = vocab[index]
    entry['focus'] = not entry.get('focus', False)
    save_vocab(vocab)
    return jsonify({'success': True, 'focus': entry['focus']})


@app.route('/api/rebuild_audio', methods=['POST'])
def api_rebuild_audio():
    """Rebuild audio files with different modes."""
    import glob
    import shutil

    data = request.json or {}
    mode = data.get('mode', 'smart')  # smart, renumber, force

    vocab = load_vocab()
    renamed = 0
    generated = 0
    skipped = 0

    # Build map of existing audio files by characters
    existing_audio = {}  # chars -> filepath
    if AUDIO_DIR.exists():
        for f in AUDIO_DIR.glob('*.mp3'):
            # Extract chars from filename like "0005_你.mp3"
            name = f.stem
            if '_' in name:
                chars_part = name.split('_', 1)[1]
                existing_audio[chars_part] = str(f)

    for i, entry in enumerate(vocab):
        chars = entry.get('characters')
        if not chars:
            continue

        target_id = f"{i:04d}_{chars}"
        target_path = str(AUDIO_DIR / f"{target_id}.mp3")

        # Check if correct file already exists
        if os.path.exists(target_path):
            entry['audio'] = target_path
            skipped += 1
            continue

        # Check if file exists under different name
        existing_path = existing_audio.get(chars)

        if mode == 'renumber':
            # Only rename, don't generate
            if existing_path and os.path.exists(existing_path):
                shutil.move(existing_path, target_path)
                entry['audio'] = target_path
                renamed += 1
            else:
                skipped += 1

        elif mode == 'smart':
            # Rename if exists, otherwise generate
            if existing_path and os.path.exists(existing_path):
                shutil.move(existing_path, target_path)
                entry['audio'] = target_path
                renamed += 1
            else:
                audio_path = generate_audio(chars, target_id)
                if audio_path:
                    entry['audio'] = audio_path
                    generated += 1

        elif mode == 'force':
            # Always regenerate
            if existing_path and os.path.exists(existing_path):
                os.remove(existing_path)
            audio_path = generate_audio(chars, target_id)
            if audio_path:
                entry['audio'] = audio_path
                generated += 1

    save_vocab(vocab)
    return jsonify({
        'success': True,
        'renamed': renamed,
        'generated': generated,
        'skipped': skipped
    })


@app.route('/api/update_stats', methods=['POST'])
def api_update_stats():
    """Update quiz stats for a vocabulary entry."""
    data = request.json
    index = data.get('index')
    correct = data.get('correct', False)
    max_count = data.get('maxCount', 20)
    decay = data.get('decay', 1)
    stat_type = data.get('statType', 'stats')  # 'stats' or 'char_stats'

    # Validate stat_type
    if stat_type not in ('stats', 'char_stats'):
        stat_type = 'stats'

    vocab = load_vocab()
    if index is None or index < 0 or index >= len(vocab):
        return jsonify({'success': False, 'error': 'Invalid index'})

    entry = vocab[index]
    # Initialize stats if not present
    if stat_type not in entry:
        entry[stat_type] = {'correct': 0, 'wrong': 0}

    # Update stats (capped at max_count, answers decay the opposite count)
    if correct:
        entry[stat_type]['correct'] = min(max_count, entry[stat_type]['correct'] + 1)
        entry[stat_type]['wrong'] = max(0, entry[stat_type]['wrong'] - decay)
    else:
        entry[stat_type]['wrong'] = min(max_count, entry[stat_type]['wrong'] + 1)
        entry[stat_type]['correct'] = max(0, entry[stat_type]['correct'] - decay)

    save_vocab(vocab)
    return jsonify({'success': True, 'stats': entry[stat_type], 'statType': stat_type})


@app.route('/api/reset_stats', methods=['POST'])
def api_reset_stats():
    """Reset quiz stats for all vocabulary entries."""
    data = request.json or {}
    stat_type = data.get('statType', 'both')  # 'stats', 'char_stats', or 'both'

    vocab = load_vocab()
    for entry in vocab:
        if stat_type in ('stats', 'both') and 'stats' in entry:
            entry['stats'] = {'correct': 0, 'wrong': 0}
        if stat_type in ('char_stats', 'both') and 'char_stats' in entry:
            entry['char_stats'] = {'correct': 0, 'wrong': 0}
    save_vocab(vocab)
    return jsonify({'success': True, 'statType': stat_type})


@app.route('/api/audio')
def api_audio():
    path = request.args.get('path', '')
    if os.path.exists(path):
        from flask import send_file
        return send_file(path, mimetype='audio/mpeg')
    return '', 404


@app.route('/api/preview_audio')
def api_preview_audio():
    """Generate preview audio for Chinese text using gTTS."""
    text = request.args.get('text', '').strip()
    if not text:
        return '', 400

    try:
        from gtts import gTTS
        from io import BytesIO
        from flask import send_file

        mp3_fp = BytesIO()
        tts = gTTS(text=text, lang='zh-CN')
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return send_file(mp3_fp, mimetype='audio/mpeg')
    except Exception as e:
        print(f"Preview audio error: {e}")
        return '', 500


# Pinyin to representative character mapping for tone audio
# Each entry maps pinyin (without tone) to [char_t1, char_t2, char_t3, char_t4]
# Using common characters that clearly demonstrate each tone


@app.route('/api/tone_audio')
def api_tone_audio():
    """Generate audio for a specific pinyin syllable with tone using espeak-ng."""
    pinyin = request.args.get('pinyin', '').strip().lower()
    tone = request.args.get('tone', '1')

    try:
        tone = int(tone)
        if tone < 1 or tone > 4:
            tone = 1
    except ValueError:
        tone = 1

    if not pinyin:
        return '', 400

    try:
        import subprocess
        import tempfile
        from io import BytesIO
        from flask import send_file

        # Create pinyin with tone number for espeak-ng
        # Convert ü to v (espeak-ng expects ASCII pinyin)
        pinyin_ascii = pinyin.replace('ü', 'v')
        pinyin_with_tone = f"{pinyin_ascii}{tone}"

        # Generate WAV using espeak-ng with Mandarin pinyin voice
        # -s 90 for slower speech, -g 10 adds 10ms gap between words
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        result = subprocess.run(
            ['espeak-ng', '-v', 'cmn-latn-pinyin', '-s', '90', '-g', '10', '-w', tmp_path, pinyin_with_tone],
            capture_output=True, text=True
        )

        if result.returncode != 0:
            print(f"espeak-ng error: {result.stderr}")
            return '', 500

        # Read the WAV file and return it
        with open(tmp_path, 'rb') as f:
            wav_data = BytesIO(f.read())

        # Clean up temp file
        import os
        os.unlink(tmp_path)

        wav_data.seek(0)
        return send_file(wav_data, mimetype='audio/wav')
    except Exception as e:
        print(f"Tone audio error for {pinyin} tone {tone}: {e}")
        return '', 500


# ============================================================================
# TONE PRACTICE API
# ============================================================================

# Pinyin initial groups for filtering
PINYIN_INITIAL_GROUPS = {
    'none': [''],
    'labial': ['b', 'p', 'm', 'f'],
    'alveolar': ['d', 't', 'n', 'l'],
    'velar': ['g', 'k', 'h'],
    'palatal': ['j', 'q', 'x'],
    'retroflex': ['zh', 'ch', 'sh', 'r'],
    'dental': ['z', 'c', 's'],
    'semivowel': ['y', 'w'],
}

# All valid initials
ALL_INITIALS = ['', 'b', 'p', 'm', 'f', 'd', 't', 'n', 'l', 'g', 'k', 'h',
                'j', 'q', 'x', 'zh', 'ch', 'sh', 'r', 'z', 'c', 's', 'y', 'w']


def get_pinyin_initial(syllable):
    """Extract the initial consonant from a pinyin syllable."""
    for initial in ['zh', 'ch', 'sh']:  # Check digraphs first
        if syllable.startswith(initial):
            return initial
    for initial in ALL_INITIALS:
        if initial and syllable.startswith(initial):
            return initial
    return ''


def get_pinyin_final(syllable):
    """Extract the final (vowel part) from a pinyin syllable."""
    initial = get_pinyin_initial(syllable)
    return syllable[len(initial):]


def load_pinyin_stats():
    """Load tone practice statistics from file."""
    stats_file = os.path.join(DATA_DIR, 'data', 'pinyin_stats.json')
    if os.path.exists(stats_file):
        with open(stats_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'tones': {}, 'initials': {}, 'finals': {}}


def save_pinyin_stats(stats):
    """Save tone practice statistics to file."""
    stats_file = os.path.join(DATA_DIR, 'data', 'pinyin_stats.json')
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


@app.route('/api/tone_practice/syllables')
def api_tone_practice_syllables():
    """Get available syllables based on filters."""
    initial_group = request.args.get('initial', 'all')
    tones_filter = request.args.get('tones', 'all')

    # Get all syllables from PINYIN_TONE_CHARS
    all_syllables = list(PINYIN_TONE_CHARS.keys())

    # Filter by initial group
    if initial_group != 'all':
        if initial_group in PINYIN_INITIAL_GROUPS:
            allowed_initials = PINYIN_INITIAL_GROUPS[initial_group]
            all_syllables = [s for s in all_syllables
                            if get_pinyin_initial(s) in allowed_initials]

    # Parse tones filter
    if tones_filter == 'all':
        allowed_tones = [1, 2, 3, 4]
    else:
        allowed_tones = [int(t) for t in tones_filter.split(',') if t.isdigit()]

    return jsonify({
        'syllables': all_syllables,
        'tones': allowed_tones,
        'count': len(all_syllables) * len(allowed_tones)
    })


@app.route('/api/tone_practice/question')
def api_tone_practice_question():
    """Generate a random question for tone practice."""
    mode = request.args.get('mode', 'tone_id')
    initial_group = request.args.get('initial', 'all')
    tones_filter = request.args.get('tones', 'all')
    weighted = request.args.get('weighted', 'false') == 'true'

    # Get filtered syllables
    all_syllables = list(PINYIN_TONE_CHARS.keys())

    if initial_group != 'all':
        if initial_group in PINYIN_INITIAL_GROUPS:
            allowed_initials = PINYIN_INITIAL_GROUPS[initial_group]
            all_syllables = [s for s in all_syllables
                            if get_pinyin_initial(s) in allowed_initials]

    if not all_syllables:
        return jsonify({'error': 'No syllables match the filter'}), 400

    # Parse tones filter
    if tones_filter == 'all':
        allowed_tones = [1, 2, 3, 4]
    else:
        allowed_tones = [int(t) for t in tones_filter.split(',') if t.isdigit()]

    if not allowed_tones:
        allowed_tones = [1, 2, 3, 4]

    # Load stats for weighted selection
    stats = load_pinyin_stats()
    config = load_config()
    wrong_weight = config.get('quiz', {}).get('wrongWeight', 1.0)
    correct_weight = config.get('quiz', {}).get('correctWeight', 0.5)

    # Build list of (syllable, tone) pairs with weights
    candidates = []
    for syllable in all_syllables:
        for tone in allowed_tones:
            weight = 1.0
            if weighted and syllable in stats.get('tones', {}):
                tone_stats = stats['tones'][syllable].get(str(tone), [0, 0])
                correct, wrong = tone_stats[0], tone_stats[1]
                # Weight formula: more wrong = higher weight
                import math
                weight = 1 + wrong_weight * math.log1p(wrong) - correct_weight * math.log1p(correct)
                weight = max(0.1, weight)  # Minimum weight
            candidates.append((syllable, tone, weight))

    if not candidates:
        return jsonify({'error': 'No valid syllable-tone combinations'}), 400

    # Weighted random selection
    if weighted:
        total_weight = sum(c[2] for c in candidates)
        r = random.random() * total_weight
        cumulative = 0
        selected = candidates[0]
        for c in candidates:
            cumulative += c[2]
            if cumulative >= r:
                selected = c
                break
        syllable, tone = selected[0], selected[1]
    else:
        syllable, tone = random.choice([(c[0], c[1]) for c in candidates])

    # Get the representative character
    char = PINYIN_TONE_CHARS[syllable][tone - 1]

    # Build response based on mode
    initial = get_pinyin_initial(syllable)
    final = get_pinyin_final(syllable)

    # Determine what to reveal and what to ask
    reveal = {}
    ask = 'tone'

    if mode == 'tone_id':
        reveal = {'syllable': syllable}
        ask = 'tone'
    elif mode == 'syllable_id':
        reveal = {'tone': tone}
        ask = 'syllable'
    elif mode == 'initial_id':
        reveal = {'tone': tone, 'final': final}
        ask = 'initial'
    elif mode == 'full_id':
        reveal = {}
        ask = 'full'

    # Generate options for multiple choice (except full_id)
    options = []
    if ask == 'tone':
        options = allowed_tones
    elif ask == 'syllable':
        # Pick some confusable syllables
        similar = [s for s in all_syllables if s != syllable]
        random.shuffle(similar)
        options = [syllable] + similar[:5]
        random.shuffle(options)
    elif ask == 'initial':
        # Get confusable initials from same group or nearby
        initial_group_name = None
        for group, initials in PINYIN_INITIAL_GROUPS.items():
            if initial in initials:
                initial_group_name = group
                break
        if initial_group_name:
            options = list(PINYIN_INITIAL_GROUPS[initial_group_name])
        else:
            options = [initial, 'b', 'p', 'd', 't', 'g', 'k']
        if initial not in options:
            options.append(initial)
        random.shuffle(options)
        options = options[:6]

    return jsonify({
        'syllable': syllable,
        'tone': tone,
        'initial': initial,
        'final': final,
        'char': char,
        'reveal': reveal,
        'ask': ask,
        'options': options,
        'mode': mode
    })


@app.route('/api/tone_practice/answer', methods=['POST'])
def api_tone_practice_answer():
    """Submit an answer and update stats."""
    data = request.json
    syllable = data.get('syllable', '')
    tone = data.get('tone', 1)
    answer = data.get('answer')
    ask_type = data.get('ask', 'tone')

    # Determine if correct
    correct = False
    correct_answer = None

    if ask_type == 'tone':
        correct_answer = tone
        correct = (answer == tone)
    elif ask_type == 'syllable':
        correct_answer = syllable
        correct = (answer == syllable)
    elif ask_type == 'initial':
        correct_answer = get_pinyin_initial(syllable)
        correct = (answer == correct_answer)
    elif ask_type == 'full':
        # Answer should be like "ma3" or "ma 3"
        answer_clean = str(answer).replace(' ', '').lower()
        correct_answer = f"{syllable}{tone}"
        correct = (answer_clean == correct_answer)

    # Update stats
    stats = load_pinyin_stats()
    config = load_config()
    max_count = config.get('quiz', {}).get('maxCount', 20)
    decay = config.get('quiz', {}).get('decay', 1)

    # Update tone stats
    if 'tones' not in stats:
        stats['tones'] = {}
    if syllable not in stats['tones']:
        stats['tones'][syllable] = {}
    tone_key = str(tone)
    if tone_key not in stats['tones'][syllable]:
        stats['tones'][syllable][tone_key] = [0, 0]

    if correct:
        stats['tones'][syllable][tone_key][0] = min(max_count,
            stats['tones'][syllable][tone_key][0] + 1)
        stats['tones'][syllable][tone_key][1] = max(0,
            stats['tones'][syllable][tone_key][1] - decay)
    else:
        stats['tones'][syllable][tone_key][1] = min(max_count,
            stats['tones'][syllable][tone_key][1] + 1)
        stats['tones'][syllable][tone_key][0] = max(0,
            stats['tones'][syllable][tone_key][0] - decay)

    # Update initial stats if relevant
    if ask_type == 'initial':
        initial = get_pinyin_initial(syllable)
        if 'initials' not in stats:
            stats['initials'] = {}
        if initial not in stats['initials']:
            stats['initials'][initial] = [0, 0]
        if correct:
            stats['initials'][initial][0] = min(max_count, stats['initials'][initial][0] + 1)
            stats['initials'][initial][1] = max(0, stats['initials'][initial][1] - decay)
        else:
            stats['initials'][initial][1] = min(max_count, stats['initials'][initial][1] + 1)
            stats['initials'][initial][0] = max(0, stats['initials'][initial][0] - decay)

    save_pinyin_stats(stats)

    return jsonify({
        'correct': correct,
        'correctAnswer': correct_answer,
        'stats': stats['tones'].get(syllable, {}).get(tone_key, [0, 0])
    })


@app.route('/api/tone_practice/stats')
def api_tone_practice_stats():
    """Get tone practice statistics."""
    stats = load_pinyin_stats()
    return jsonify(stats)


@app.route('/api/tone_practice/reset', methods=['POST'])
def api_tone_practice_reset():
    """Reset tone practice statistics."""
    data = request.json or {}
    stat_type = data.get('type', 'all')  # 'tones', 'initials', 'finals', or 'all'

    stats = load_pinyin_stats()

    if stat_type in ('tones', 'all'):
        stats['tones'] = {}
    if stat_type in ('initials', 'all'):
        stats['initials'] = {}
    if stat_type in ('finals', 'all'):
        stats['finals'] = {}

    save_pinyin_stats(stats)
    return jsonify({'success': True, 'type': stat_type})


# ============================================================================
# CONFIG API
# ============================================================================

@app.route('/api/config')
def api_get_config():
    """Get configuration."""
    config = load_config()
    # Add API key status (from env var, don't expose the actual key)
    config['hasApiKey'] = bool(os.environ.get('CLAUDE_API_KEY'))
    return jsonify(config)


@app.route('/api/config', methods=['POST'])
def api_save_config():
    """Save configuration."""
    data = request.json
    config = load_config()

    # Update quiz settings if provided
    if 'quiz' in data:
        config['quiz'] = {**config.get('quiz', {}), **data['quiz']}

    save_config(config)
    return jsonify({'success': True, 'config': config})


# ============================================================================
# IMPORT API
# ============================================================================

IMPORT_DIR = os.path.join(DATA_DIR, 'data', 'import')
SCHEMA_PATH = os.path.join(DATA_DIR, 'schemas', 'extraction_schema.json')


def load_extraction_schema():
    """Load the extraction JSON schema."""
    if os.path.exists(SCHEMA_PATH):
        with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def validate_extraction(data, schema):
    """Basic validation of extraction data against schema."""
    errors = []

    # Check required fields
    if 'source' not in data:
        errors.append("Missing required field: source")
    if 'vocabulary' not in data:
        errors.append("Missing required field: vocabulary")
    elif not isinstance(data['vocabulary'], list):
        errors.append("vocabulary must be an array")

    # Validate vocabulary items
    if 'vocabulary' in data and isinstance(data['vocabulary'], list):
        for i, item in enumerate(data['vocabulary']):
            if 'english' not in item:
                errors.append(f"vocabulary[{i}]: missing 'english'")
            if 'characters' not in item:
                errors.append(f"vocabulary[{i}]: missing 'characters'")

    return errors


def normalize_pinyin(pinyin_str):
    """Normalize pinyin for comparison: lowercase, apostrophes→spaces, collapse whitespace."""
    if not pinyin_str:
        return ''
    # Replace apostrophes with spaces (kě'ài → kě ài)
    normalized = pinyin_str.lower().replace("'", " ").replace("'", " ")
    # Collapse multiple spaces
    return ' '.join(normalized.split())


def compare_with_dictionary(item, by_chars):
    """Compare extracted item with CC-CEDICT dictionary.

    Uses pypinyin as the primary reference (like the Add functionality does),
    since BY_CHARS may store rare/alternate readings for multi-reading characters.
    Also detects tone sandhi by comparing against dictionary citation form.
    """
    chars = item.get('characters', '')
    extracted_pinyin = item.get('pinyin', '')

    if not chars:
        return {'status': 'no_chars', 'dict_entry': None}

    # Get pypinyin version - this is our trusted reference (same as Add functionality)
    pypinyin_result = chars_to_pinyin(chars) if chars else None

    # Look up in dictionary (BY_CHARS maps chars -> single entry dict)
    # Note: BY_CHARS may have wrong reading for multi-reading chars (e.g. 大 dài instead of dà)
    dict_entry = by_chars.get(chars)

    # Get dictionary info (may be wrong for multi-reading characters, or missing for compounds)
    dict_pinyin = dict_entry.get('pinyin', '') if dict_entry else ''
    dict_definitions = dict_entry.get('definitions', []) if dict_entry else []
    dict_english = '; '.join(dict_definitions[:3]) if dict_definitions else ''

    if not extracted_pinyin:
        # No pinyin to compare
        if dict_entry:
            return {'status': 'match', 'dict_entry': dict_entry}
        elif pypinyin_result:
            # Not in dict but pypinyin can handle it
            return {'status': 'match', 'dict_entry': None}
        return {'status': 'not_in_dict', 'dict_entry': None}

    # Normalised versions for comparison (handles apostrophes like kě'ài → kě ài)
    ext_norm = normalize_pinyin(extracted_pinyin)
    pypinyin_norm = normalize_pinyin(pypinyin_result)
    dict_norm = normalize_pinyin(dict_pinyin)

    # Strip tones for base comparison
    extracted_plain = strip_tones(ext_norm.replace(' ', ''))
    pypinyin_plain = strip_tones(pypinyin_norm.replace(' ', '')) if pypinyin_norm else None
    dict_plain = strip_tones(dict_norm.replace(' ', '')) if dict_norm else None

    # Check if extracted matches pypinyin (our trusted reference)
    matches_pypinyin = pypinyin_norm and ext_norm == pypinyin_norm
    # Check if extracted matches dictionary (citation form)
    matches_dict = dict_norm and ext_norm == dict_norm
    # Check if pypinyin differs from dictionary (indicates sandhi or alternate reading)
    pypinyin_differs_from_dict = pypinyin_norm and dict_norm and pypinyin_norm != dict_norm

    if matches_pypinyin:
        # Extracted matches pypinyin - correct
        if pypinyin_differs_from_dict and dict_plain == pypinyin_plain:
            # pypinyin differs from dict only in tones (same base) - this is sandhi
            # Textbook uses the spoken/sandhi form which matches pypinyin
            return {
                'status': 'sandhi_variant',
                'dict_entry': dict_entry,
                'dict_pinyin': dict_pinyin,
                'pypinyin': pypinyin_result,
                'dict_english': dict_english
            }
        # Regular match
        return {'status': 'match', 'dict_entry': dict_entry}

    if matches_dict:
        # Extracted matches dictionary citation form exactly
        return {'status': 'match', 'dict_entry': dict_entry}

    # Check if base pinyin matches (could be sandhi with tones differing)
    if pypinyin_plain and extracted_plain == pypinyin_plain:
        # Base matches pypinyin but tones differ - likely sandhi
        return {
            'status': 'sandhi_variant',
            'dict_entry': dict_entry,
            'dict_pinyin': dict_pinyin,
            'pypinyin': pypinyin_result,
            'dict_english': dict_english
        }

    # Not in dictionary but matches pypinyin
    if not dict_entry and pypinyin_norm and ext_norm == pypinyin_norm:
        return {'status': 'match', 'dict_entry': None}

    # No match - real conflict
    if not dict_entry and not pypinyin_result:
        return {'status': 'not_in_dict', 'dict_entry': None}

    return {
        'status': 'pinyin_differs',
        'dict_entry': dict_entry,
        'dict_pinyin': dict_pinyin,
        'pypinyin': pypinyin_result,
        'dict_english': dict_english
    }


@app.route('/api/import/lessons')
def api_import_lessons():
    """List available lesson extractions.

    Recursively scans data/import/ for extracted.json files.
    Supports nested folders like: book_name/lesson_3/extracted.json
    Directory naming is flexible - lesson info comes from the JSON content.
    """
    lessons = []

    if not os.path.exists(IMPORT_DIR):
        return jsonify({'lessons': []})

    # Recursively find all extracted.json files
    for root, dirs, files in os.walk(IMPORT_DIR):
        if 'extracted.json' in files:
            extracted_path = os.path.join(root, 'extracted.json')
            # Get relative path from IMPORT_DIR for the lesson ID
            rel_path = os.path.relpath(root, IMPORT_DIR)

            try:
                with open(extracted_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                source = data.get('source', {})

                # Build display title from source metadata
                lesson_num = source.get('lesson', '')
                title = source.get('title', '')
                textbook = source.get('textbook', '')

                # Create informative display name
                if lesson_num and title:
                    display = f"Lesson {lesson_num}: {title}"
                elif title:
                    display = title
                elif lesson_num:
                    display = f"Lesson {lesson_num}"
                else:
                    display = rel_path  # Fallback to relative path

                lessons.append({
                    'id': rel_path,  # Relative path (for API calls)
                    'lesson': lesson_num,
                    'title': title,
                    'textbook': textbook,
                    'display': display,
                    'vocab_count': len(data.get('vocabulary', [])),
                    'has_dialogues': bool(data.get('dialogues')),
                    'has_grammar': bool(data.get('grammar_patterns')),
                    'has_exercises': bool(data.get('exercises')),
                    'extracted_date': source.get('extracted_date'),
                    'extracted_by': source.get('extracted_by')
                })
            except (json.JSONDecodeError, IOError) as e:
                # Include failed directories with error info
                lessons.append({
                    'id': rel_path,
                    'display': f"{rel_path} (error loading)",
                    'error': str(e),
                    'vocab_count': 0
                })

    # Sort by textbook then lesson number
    lessons.sort(key=lambda x: (x.get('textbook', ''), str(x.get('lesson', ''))))

    return jsonify({'lessons': lessons})


@app.route('/api/import/preview')
def api_import_preview():
    """Preview an extraction before importing."""
    lesson_id = request.args.get('lesson', '')

    if not lesson_id:
        return jsonify({'error': 'lesson parameter required'}), 400

    extracted_path = os.path.join(IMPORT_DIR, lesson_id, 'extracted.json')

    if not os.path.exists(extracted_path):
        return jsonify({'error': f'Extraction not found: {lesson_id}'}), 404

    try:
        with open(extracted_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Invalid JSON: {e}'}), 400

    # Validate against schema
    schema = load_extraction_schema()
    validation_errors = validate_extraction(data, schema)
    if validation_errors:
        return jsonify({'error': 'Validation failed', 'details': validation_errors}), 400

    # Load existing vocabulary for duplicate detection
    vocab = load_vocab()
    existing_chars = {v.get('characters') for v in vocab}

    # Process vocabulary items
    items = []
    for item in data.get('vocabulary', []):
        chars = item.get('characters', '')

        # Determine status
        comparison = None
        if chars in existing_chars:
            status = 'duplicate'
        else:
            comparison = compare_with_dictionary(item, BY_CHARS)
            if comparison['status'] == 'pinyin_differs':
                status = 'conflict'
            elif comparison['status'] == 'sandhi_variant':
                status = 'sandhi'  # Recognised sandhi - auto-accept textbook version
            elif comparison['status'] == 'not_in_dict':
                status = 'new_not_in_dict'
            else:
                status = 'new'

        processed = {
            'english': item.get('english', ''),
            'pinyin': item.get('pinyin', ''),
            'characters': chars,
            'category': item.get('category'),
            'status': status
        }

        # Add reference info for conflicts and sandhi variants
        if status == 'conflict':
            processed['pypinyin'] = comparison.get('pypinyin')  # More reliable reference
            processed['dict_pinyin'] = comparison.get('dict_pinyin')
            processed['dict_english'] = comparison.get('dict_english')
        elif status == 'sandhi':
            processed['pypinyin'] = comparison.get('pypinyin')
            processed['dict_pinyin'] = comparison.get('dict_pinyin')
            processed['note'] = 'Tone sandhi (textbook uses spoken form)'

        items.append(processed)

    return jsonify({
        'source': data.get('source', {}),
        'items': items,
        'summary': {
            'total': len(items),
            'new': sum(1 for i in items if i['status'] == 'new'),
            'sandhi': sum(1 for i in items if i['status'] == 'sandhi'),
            'new_not_in_dict': sum(1 for i in items if i['status'] == 'new_not_in_dict'),
            'conflict': sum(1 for i in items if i['status'] == 'conflict'),
            'duplicate': sum(1 for i in items if i['status'] == 'duplicate')
        },
        'dialogues': data.get('dialogues', []),
        'grammar_patterns': data.get('grammar_patterns', [])
    })


@app.route('/api/import/confirm', methods=['POST'])
def api_import_confirm():
    """Import selected vocabulary items."""
    data = request.json

    if not data or 'items' not in data:
        return jsonify({'error': 'items array required'}), 400

    vocab = load_vocab()
    existing_chars = {v.get('characters') for v in vocab}

    imported = []
    skipped = []

    for item in data['items']:
        chars = item.get('characters', '')

        # Skip if already exists
        if chars in existing_chars:
            skipped.append({'characters': chars, 'reason': 'duplicate'})
            continue

        # Use expected pinyin (pypinyin preferred, dict as fallback) if requested
        use_expected = item.get('use_dictionary', False)
        if use_expected:
            # Prefer pypinyin (more reliable), fall back to dict_pinyin
            pinyin = item.get('pypinyin') or item.get('dict_pinyin') or item.get('pinyin', '')
        else:
            pinyin = item.get('pinyin', '')

        # Convert tone numbers to marks if needed (e.g., ni3 -> nǐ)
        if pinyin and re.search(r'[1-4]', pinyin):
            pinyin = numbered_to_toned(pinyin)

        # Generate audio
        audio_path = None
        if chars:
            try:
                audio_path = generate_audio(chars, len(vocab))
            except Exception as e:
                print(f"Audio generation failed for {chars}: {e}")

        # Create entry
        entry = {
            'english': item.get('english', ''),
            'characters': chars,
            'pinyin': pinyin,
            'audio': audio_path,
            'stats': {'correct': 0, 'wrong': 0}
        }

        vocab.append(entry)
        existing_chars.add(chars)
        imported.append(entry)

    # Save vocabulary
    if imported:
        save_vocab(vocab)

    return jsonify({
        'success': True,
        'imported': len(imported),
        'skipped': len(skipped),
        'skipped_items': skipped,
        'total_vocab': len(vocab)
    })


if __name__ == '__main__':
    print("Starting Mandarin Vocabulary Web App...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)
