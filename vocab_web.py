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
    """Generate audio for a specific pinyin syllable with tone."""
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

    # Look up the representative character for this syllable and tone
    if pinyin in PINYIN_TONE_CHARS:
        char = PINYIN_TONE_CHARS[pinyin][tone - 1]
    else:
        # Fallback: try to use the pinyin directly (may not work well)
        char = pinyin

    try:
        from gtts import gTTS
        from io import BytesIO
        from flask import send_file

        mp3_fp = BytesIO()
        tts = gTTS(text=char, lang='zh-CN')
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)
        return send_file(mp3_fp, mimetype='audio/mpeg')
    except Exception as e:
        print(f"Tone audio error for {pinyin} tone {tone}: {e}")
        return '', 500


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


if __name__ == '__main__':
    print("Starting Mandarin Vocabulary Web App...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)
