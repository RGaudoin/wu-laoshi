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
from flask import Flask, render_template_string, request, jsonify

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

HTML_TEMPLATE = r'''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mandarin Vocabulary</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 { color: #333; text-align: center; margin-bottom: 10px; }

        /* Main navigation */
        .main-nav {
            display: flex;
            gap: 5px;
            margin-bottom: 20px;
            border-bottom: 2px solid #333;
            padding-bottom: 10px;
        }
        .nav-btn {
            padding: 10px 20px;
            background: transparent;
            border: none;
            cursor: pointer;
            font-size: 16px;
            color: #666;
            border-radius: 5px 5px 0 0;
        }
        .nav-btn:hover { background: #eee; }
        .nav-btn.active { background: #333; color: white; font-weight: bold; }
        .nav-btn.settings-btn { margin-left: auto; }

        /* Sections */
        .section {
            display: none;
        }
        .section.active { display: block; }

        /* Sub-tabs (within sections) */
        .tabs {
            display: flex;
            gap: 5px;
            margin-bottom: 20px;
        }
        .tab {
            padding: 10px 20px;
            background: #ddd;
            border: none;
            cursor: pointer;
            border-radius: 5px 5px 0 0;
            font-size: 16px;
        }
        .tab.active { background: white; font-weight: bold; }
        .tab-content {
            display: none;
            background: white;
            padding: 20px;
            border-radius: 0 5px 5px 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .tab-content.active { display: block; }

        /* Home section cards */
        .home-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .home-card {
            background: white;
            padding: 30px 20px;
            border-radius: 10px;
            text-align: center;
            cursor: pointer;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .home-card:hover { transform: translateY(-3px); box-shadow: 0 4px 10px rgba(0,0,0,0.15); }
        .home-card h3 { margin: 0 0 10px 0; color: #333; }
        .home-card p { margin: 0; color: #666; font-size: 14px; }

        /* Settings modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.5);
            z-index: 100;
        }
        .modal-overlay.active { display: flex; justify-content: center; align-items: center; }
        .modal {
            background: white;
            padding: 30px;
            border-radius: 10px;
            max-width: 500px;
            width: 90%;
            max-height: 80vh;
            overflow-y: auto;
        }
        .modal h2 { margin-top: 0; }
        .modal-close { float: right; background: none; font-size: 24px; padding: 0 10px; }

        /* Collapsible sections */
        .collapsible {
            background: #e0e0e0;
            color: #333;
            border: none;
            padding: 12px 15px;
            width: 100%;
            text-align: left;
            cursor: pointer;
            font-size: 15px;
            font-weight: bold;
            border-radius: 5px;
            margin-bottom: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .collapsible:hover { background: #d0d0d0; }
        .collapsible::after { content: '▼'; font-size: 12px; transition: transform 0.2s; color: #555; }
        .collapsible.collapsed::after { transform: rotate(-90deg); }
        .collapsible-content {
            padding: 15px;
            background: white;
            border: 1px solid #ddd;
            border-top: none;
            border-radius: 0 0 5px 5px;
            margin-bottom: 15px;
            margin-top: -5px;
        }
        .collapsible-content.collapsed { display: none; }

        /* Chinese text */
        .chinese {
            font-family: "Noto Sans CJK SC", "Microsoft YaHei", "SimHei", sans-serif;
            font-size: 24px;
        }
        .pinyin {
            font-family: "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
            font-size: 18px;
            color: #666;
        }

        /* Forms */
        input[type="text"] {
            padding: 10px;
            font-size: 18px;
            border: 1px solid #ccc;
            border-radius: 5px;
            width: 300px;
        }
        button {
            padding: 10px 20px;
            font-size: 16px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
        }
        button:hover { background: #45a049; }
        button.secondary { background: #2196F3; }
        button.danger { background: #f44336; }

        /* Lists */
        .vocab-item {
            padding: 15px;
            border-bottom: 1px solid #eee;
            display: flex;
            align-items: center;
            gap: 20px;
        }
        .vocab-item:hover { background: #f9f9f9; }
        .vocab-english { width: 150px; font-weight: bold; }
        .vocab-chars { font-size: 28px; }
        .vocab-pinyin { color: #666; }

        /* Dictionary matches */
        .match-item {
            padding: 10px;
            border: 1px solid #ddd;
            margin: 5px 0;
            border-radius: 5px;
            cursor: pointer;
        }
        .match-item:hover { background: #e3f2fd; border-color: #2196F3; }
        .match-item.selected { background: #bbdefb; border-color: #1976D2; }

        /* Quiz */
        .quiz-prompt {
            font-size: 48px;
            text-align: center;
            padding: 40px;
            margin: 20px 0;
        }
        .quiz-input {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin: 20px 0;
        }
        .quiz-feedback {
            text-align: center;
            font-size: 24px;
            padding: 20px;
        }
        .correct { color: #4CAF50; }
        .wrong { color: #f44336; }
        .score { text-align: center; font-size: 18px; color: #666; }

        /* Audio button */
        .audio-btn {
            background: #9C27B0;
            padding: 5px 10px;
            font-size: 14px;
        }

        /* Settings */
        .settings {
            display: flex;
            flex-wrap: wrap;
            gap: 10px 20px;
            margin-bottom: 20px;
            align-items: center;
        }
        select {
            padding: 8px;
            font-size: 16px;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <h1>Mandarin Vocabulary</h1>

    <!-- Main Navigation -->
    <nav class="main-nav">
        <button class="nav-btn active" onclick="showSection('home')">Home</button>
        <button class="nav-btn" onclick="showSection('learn')">Learn</button>
        <button class="nav-btn" onclick="showSection('vocabulary')">Vocabulary</button>
        <button class="nav-btn" onclick="showSection('import')">Import</button>
        <button class="nav-btn settings-btn" onclick="openSettings()">⚙️</button>
    </nav>

    <!-- HOME SECTION -->
    <div id="section-home" class="section active">
        <div class="home-cards">
            <div class="home-card" onclick="showSection('learn')">
                <h3>📝 Learn</h3>
                <p>Quiz yourself on vocabulary</p>
            </div>
            <div class="home-card" onclick="showSection('vocabulary')">
                <h3>📚 Vocabulary</h3>
                <p id="home-vocab-count">Lookup, add, and manage words</p>
            </div>
            <div class="home-card" onclick="showSection('import')">
                <h3>📄 Import</h3>
                <p>Import from course materials</p>
            </div>
        </div>
    </div>

    <!-- LEARN SECTION -->
    <div id="section-learn" class="section">
        <div class="tabs">
            <button class="tab active" onclick="showSubTab('learn', 'quiz')">Quiz</button>
            <!-- Future: Tones, Conversation tabs -->
        </div>

        <!-- QUIZ TAB -->
        <div id="learn-quiz" class="tab-content active">
            <div id="quiz-stats-summary" style="background: #f0f0f0; padding: 10px 15px; border-radius: 5px; margin-bottom: 15px; color: #666; font-size: 14px;"></div>
            <div class="settings">
                <label>Show:
                    <select id="quiz-show">
                        <option value="english">English</option>
                        <option value="characters">Characters</option>
                        <option value="pinyin">Pinyin</option>
                        <option value="audio">Audio Only</option>
                    </select>
                </label>
                <label>Answer with:
                    <select id="quiz-answer">
                        <option value="characters">Characters</option>
                        <option value="pinyin">Pinyin</option>
                        <option value="english">English</option>
                    </select>
                </label>
                <label>Order:
                    <select id="quiz-order">
                        <option value="random">Random</option>
                        <option value="weighted">Weighted (more mistakes = more frequent)</option>
                        <option value="inorder">In Order</option>
                    </select>
                </label>
                <label>Count:
                    <select id="quiz-count">
                        <option value="10">10</option>
                        <option value="20" selected>20</option>
                        <option value="50">50</option>
                        <option value="0">All</option>
                    </select>
                </label>
                <label><input type="checkbox" id="quiz-focus-only"> Focus only</label>
                <label>Tag: <select id="quiz-tag-filter"><option value="">All</option></select></label>
                <label><input type="checkbox" id="quiz-require-tones"> Require tones</label>
                <button onclick="startQuiz()">Start Quiz</button>
            </div>
            <div class="quiz-prompt chinese" id="quiz-prompt">Press "Start Quiz" to begin</div>
            <div id="quiz-audio-btn" style="text-align: center; margin: 10px 0;">
                <button class="audio-btn" onclick="playQuizAudio()" style="display: none;" id="quiz-play-audio">🔊 Play Audio</button>
            </div>
            <div class="quiz-input" id="quiz-input-area">
                <input type="text" id="quiz-input" class="chinese" placeholder="Your answer">
                <button onclick="checkAnswer()">Check</button>
            </div>
            <div class="quiz-feedback" id="quiz-feedback"></div>
            <div id="quiz-next-btn" style="text-align: center; display: none; margin: 15px 0;">
                <button class="secondary" onclick="nextQuestion()">Next →</button>
            </div>
            <div class="score" id="quiz-score">Score: 0/0</div>
        </div>
    </div>

    <!-- VOCABULARY SECTION -->
    <div id="section-vocabulary" class="section">
        <div class="tabs">
            <button class="tab active" onclick="showSubTab('vocabulary', 'lookup')">Lookup</button>
            <button class="tab" onclick="showSubTab('vocabulary', 'add')">Add</button>
            <button class="tab" onclick="showSubTab('vocabulary', 'list')">List</button>
        </div>

        <!-- LOOKUP TAB -->
        <div id="vocabulary-lookup" class="tab-content active">
            <div style="margin-bottom: 20px;">
                <input type="text" id="search-input" placeholder="Search (English, 中文, or pinyin)">
                <button onclick="doSearch()">Search</button>
            </div>
            <h3>Your Vocabulary</h3>
            <div id="vocab-results"></div>
            <h3>Dictionary</h3>
            <div id="dict-count"></div>
            <div id="dict-results"></div>
        </div>

        <!-- ADD TAB -->
        <div id="vocabulary-add" class="tab-content">
            <div style="margin-bottom: 15px;">
                <label>English: </label>
                <input type="text" id="add-english" placeholder="meaning">
            </div>
            <div style="margin-bottom: 15px;">
                <label>Characters: </label>
                <input type="text" id="add-chars" placeholder="中文" class="chinese">
            </div>
            <div style="margin-bottom: 15px;">
                <label>OR Search: </label>
                <input type="text" id="add-pinyin" placeholder="pinyin or English (e.g., ni3 hao3, you)">
                <button class="secondary" onclick="searchPinyin()">Search Dictionary</button>
            </div>
            <div id="add-count"></div>
            <div id="pinyin-matches"></div>
            <button onclick="addWord()" style="margin-top: 20px;">Add to Vocabulary</button>
            <div id="add-result" style="margin-top: 15px;"></div>
        </div>

        <!-- LIST TAB -->
        <div id="vocabulary-list" class="tab-content">
            <div style="display: flex; gap: 20px; align-items: center; margin-bottom: 10px; flex-wrap: wrap;">
                <label><input type="checkbox" id="show-stats" onchange="refreshList()"> Show quiz stats</label>
                <label>Tag: <select id="list-tag-filter" onchange="refreshList()"><option value="">All</option></select></label>
            </div>
            <div id="list-count"></div>
            <div id="vocab-list"></div>
        </div>
    </div>

    <!-- IMPORT SECTION -->
    <div id="section-import" class="section">
        <div style="background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
            <h2>Import Course Materials</h2>
            <p style="color: #666;">Upload images or PDFs of your course materials to extract vocabulary and exercises.</p>
            <p style="color: #999; font-style: italic;">Coming soon - requires Claude API configuration in Settings.</p>
        </div>
    </div>

    <!-- SETTINGS MODAL -->
    <div id="settings-modal" class="modal-overlay">
        <div class="modal">
            <button class="modal-close" onclick="closeSettings()">&times;</button>
            <h2>Settings</h2>

            <!-- API Section -->
            <button class="collapsible collapsed" onclick="toggleCollapsible(this)">API</button>
            <div class="collapsible-content collapsed">
                <label><strong>Claude API Key</strong></label>
                <p style="color: #666; font-size: 14px; margin: 5px 0;">Required for Import and Practice features</p>
                <input type="password" id="api-key" placeholder="sk-ant-..." style="width: 100%; margin-top: 5px;">
            </div>

            <!-- Quiz Section -->
            <button class="collapsible" onclick="toggleCollapsible(this)">Quiz</button>
            <div class="collapsible-content">
                <p style="color: #666; font-size: 13px; margin: 0 0 10px 0;"><strong>Weighting formula:</strong> weight = 1 + wrong_w × log(1+wrong) − correct_w × log(1+correct)</p>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <label style="font-size: 14px;">Wrong weight: <input type="number" id="setting-wrong-weight" value="1.0" step="0.1" min="0" style="width: 60px;"></label>
                    <label style="font-size: 14px;">Correct weight: <input type="number" id="setting-correct-weight" value="0.5" step="0.1" min="0" style="width: 60px;"></label>
                    <label style="font-size: 14px;">Max count: <input type="number" id="setting-max-count" value="20" step="1" min="1" style="width: 60px;"></label>
                    <label style="font-size: 14px;">Decay: <input type="number" id="setting-decay" value="1" step="1" min="0" style="width: 60px;"></label>
                </div>
                <p style="color: #999; font-size: 12px; margin-top: 10px;">Higher wrong weight = focus on mistakes. Decay = how much correct reduces wrong (and vice versa).</p>
                <hr style="margin: 15px 0; border: none; border-top: 1px solid #ddd;">
                <p style="color: #666; font-size: 13px; margin: 0 0 5px 0;"><strong>Reset data:</strong></p>
                <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                    <button class="danger" onclick="resetStats('stats')">Reset Quiz Stats</button>
                    <button class="danger" onclick="resetStats('char_stats')">Reset Character Stats</button>
                    <button class="danger" onclick="resetStats('both')">Reset All</button>
                </div>
            </div>

            <!-- Audio Section -->
            <button class="collapsible collapsed" onclick="toggleCollapsible(this)">Audio</button>
            <div class="collapsible-content collapsed">
                <label style="font-size: 14px; display: block; margin-bottom: 10px;">
                    Mode:
                    <select id="audio-rebuild-mode" style="margin-left: 5px;">
                        <option value="smart">Smart rebuild (renumber + missing)</option>
                        <option value="renumber">Renumber only (no gTTS)</option>
                        <option value="force">Force rebuild (regenerate all)</option>
                    </select>
                </label>
                <p id="audio-mode-desc" style="color: #666; font-size: 13px; margin: 0 0 10px 0;">Reuse existing audio files where possible, generate only for entries without audio.</p>
                <button class="secondary" onclick="rebuildAudio()">Rebuild Audio</button>
            </div>

            <div style="display: flex; gap: 10px; margin-top: 20px;">
                <button onclick="saveSettings()">Save</button>
                <button class="secondary" onclick="closeSettings()">Cancel</button>
            </div>
        </div>
    </div>

    <!-- EDIT ENTRY MODAL -->
    <div id="edit-modal" class="modal-overlay">
        <div class="modal">
            <button class="modal-close" onclick="closeEditModal()">&times;</button>
            <h2 id="edit-modal-title">Edit Entry</h2>
            <input type="hidden" id="edit-index">
            <div style="margin-bottom: 15px;">
                <label><strong>Characters</strong></label>
                <p id="edit-chars" class="chinese" style="font-size: 32px; margin: 5px 0;"></p>
            </div>
            <div style="margin-bottom: 15px;">
                <label><strong>English</strong></label>
                <input type="text" id="edit-english" style="width: 100%; margin-top: 5px;">
            </div>
            <div style="margin-bottom: 15px;">
                <label><strong>Pinyin</strong></label>
                <div style="display: flex; gap: 10px; margin-top: 5px;">
                    <input type="text" id="edit-pinyin" style="flex: 1;">
                    <button class="secondary" onclick="lookupEditPinyin()" style="white-space: nowrap;">Lookup</button>
                </div>
                <div id="edit-pinyin-options" style="margin-top: 8px;"></div>
            </div>
            <div style="margin-bottom: 15px;">
                <label><strong>Tags</strong></label>
                <input type="text" id="edit-tags" placeholder="comma-separated, e.g. lesson1, greetings" style="width: 100%; margin-top: 5px;">
            </div>
            <div style="margin-bottom: 15px;" id="edit-audio-container"></div>
            <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
            <div style="display: flex; gap: 10px; justify-content: space-between;">
                <div>
                    <button onclick="saveEditModal()">Save</button>
                    <button class="secondary" onclick="closeEditModal()">Cancel</button>
                </div>
                <button class="danger" onclick="deleteFromModal()">Delete</button>
            </div>
        </div>
    </div>

    <script>
        let quizEntries = [];
        let quizAllEntries = [];  // Full vocab for duplicate matching (not limited by count)
        let quizIndex = 0;
        let quizCorrect = 0;
        let quizTotal = 0;
        let currentEntry = null;
        let currentAudio = null;

        // Tone mappings: toned vowel → [base vowel, tone number]
        const tonedVowels = {
            'ā': ['a', 1], 'á': ['a', 2], 'ǎ': ['a', 3], 'à': ['a', 4],
            'ē': ['e', 1], 'é': ['e', 2], 'ě': ['e', 3], 'è': ['e', 4],
            'ī': ['i', 1], 'í': ['i', 2], 'ǐ': ['i', 3], 'ì': ['i', 4],
            'ō': ['o', 1], 'ó': ['o', 2], 'ǒ': ['o', 3], 'ò': ['o', 4],
            'ū': ['u', 1], 'ú': ['u', 2], 'ǔ': ['u', 3], 'ù': ['u', 4],
            'ǖ': ['ü', 1], 'ǘ': ['ü', 2], 'ǚ': ['ü', 3], 'ǜ': ['ü', 4]
        };

        // Convert toned pinyin to plain (ǐ→i, ǎ→a, etc.) and remove tone numbers/spaces
        function stripTones(s) {
            return s.split('').map(c => tonedVowels[c] ? tonedVowels[c][0] : c).join('')
                    .replace(/[1-5 ]/g, '').toLowerCase();
        }

        // Convert pinyin to numbered format for tone-aware comparison
        // "hǎo" → "hao3", "ni3 hao3" stays as is
        function toNumberedPinyin(s) {
            // Split into syllables (space-separated)
            return s.toLowerCase().split(/\s+/).map(syllable => {
                let base = '';
                let tone = '';
                // Check if already has tone number at end
                const numMatch = syllable.match(/^(.+?)([1-5])$/);
                if (numMatch) {
                    return syllable; // Already numbered
                }
                // Extract tone from toned vowels
                for (const char of syllable) {
                    if (tonedVowels[char]) {
                        base += tonedVowels[char][0];
                        tone = tonedVowels[char][1];
                    } else {
                        base += char;
                    }
                }
                return tone ? base + tone : base;
            }).join(' ');
        }

        // Compare pinyin with tones (accepts both toned markers and numbered)
        function comparePinyinWithTones(answer, correct) {
            return toNumberedPinyin(answer) === toNumberedPinyin(correct);
        }

        // Levenshtein distance for fuzzy matching
        function levenshtein(a, b) {
            const matrix = [];
            for (let i = 0; i <= b.length; i++) matrix[i] = [i];
            for (let j = 0; j <= a.length; j++) matrix[0][j] = j;
            for (let i = 1; i <= b.length; i++) {
                for (let j = 1; j <= a.length; j++) {
                    matrix[i][j] = b[i-1] === a[j-1]
                        ? matrix[i-1][j-1]
                        : Math.min(matrix[i-1][j-1] + 1, matrix[i][j-1] + 1, matrix[i-1][j] + 1);
                }
            }
            return matrix[b.length][a.length];
        }

        // Normalize English text for comparison
        function normalizeEnglish(s) {
            return s.toLowerCase()
                    .replace(/^to\s+/, '')  // strip "to " prefix
                    .replace(/\([^)]*\)/g, '') // remove (bracketed content)
                    .replace(/\[[^\]]*\]/g, '') // remove [bracketed content]
                    .trim();
        }

        // Match English answer against definition
        function matchEnglish(answer, definition) {
            const normAnswer = normalizeEnglish(answer);
            if (!normAnswer) return false;

            // Check if it's a particle definition
            const isParticle = definition.toLowerCase().includes('particle');

            // Strip brackets BEFORE splitting (to avoid splitting on commas inside brackets)
            const defNoBrackets = definition
                .replace(/\([^)]*\)/g, '')
                .replace(/\[[^\]]*\]/g, '');

            // Split definition by delimiters
            const parts = defNoBrackets.split(/[\/,;]/).map(p => normalizeEnglish(p)).filter(p => p);

            // If particle definition, also accept "particle" as answer
            if (isParticle && normAnswer === 'particle') return true;

            // Extract keywords from definition (words 3+ chars, excluding common words)
            const stopWords = ['the', 'and', 'for', 'that', 'this', 'with', 'from', 'indicating', 'used', 'sth', 'someone', 'something'];
            const keywords = definition.toLowerCase()
                .replace(/[()[\]]/g, ' ')
                .split(/[\s\/,;]+/)
                .filter(w => w.length >= 3 && !stopWords.includes(w));

            // Exact match on any part
            for (const part of parts) {
                if (normAnswer === part) return true;
            }

            // Exact match on any keyword (for particles especially)
            if (isParticle && keywords.includes(normAnswer)) return true;

            // Fuzzy match (80% similarity threshold)
            for (const part of parts) {
                if (part.length >= 3) {
                    const dist = levenshtein(normAnswer, part);
                    const similarity = 1 - dist / Math.max(normAnswer.length, part.length);
                    if (similarity >= 0.8) return true;
                }
            }

            return false;
        }

        // MAIN NAVIGATION
        function showSection(sectionId) {
            // Update nav buttons
            document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
            const btn = document.querySelector(`.nav-btn[onclick*="${sectionId}"]`);
            if (btn) btn.classList.add('active');

            // Show section
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.getElementById('section-' + sectionId).classList.add('active');

            // Load data for specific sections
            if (sectionId === 'home') loadHomeStats();
            if (sectionId === 'learn') loadQuizStats();
            if (sectionId === 'vocabulary') {
                // Check which tab is active and load its data
                const activeTab = document.querySelector('#section-vocabulary .tab-content.active');
                if (activeTab && activeTab.id === 'vocabulary-list') refreshList();
            }
        }

        function showSubTab(section, tabId) {
            const sectionEl = document.getElementById('section-' + section);

            // Update tab buttons within section
            sectionEl.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');

            // Show tab content within section
            sectionEl.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById(section + '-' + tabId).classList.add('active');

            // Load data for specific tabs
            if (tabId === 'list') refreshList();
        }

        function openSettings() {
            document.getElementById('settings-modal').classList.add('active');
        }

        function toggleCollapsible(btn) {
            btn.classList.toggle('collapsed');
            const content = btn.nextElementSibling;
            content.classList.toggle('collapsed');
        }

        function closeSettings() {
            document.getElementById('settings-modal').classList.remove('active');
        }

        // Quiz weight settings (defaults)
        let quizSettings = {
            wrongWeight: 1.0,
            correctWeight: 0.5,
            maxCount: 20,
            decay: 1
        };

        function loadSettings() {
            fetch('/api/config')
                .then(r => r.json())
                .then(config => {
                    // Load quiz settings from config
                    if (config.quiz) {
                        quizSettings = {...quizSettings, ...config.quiz};
                    }
                    // Update UI
                    document.getElementById('setting-wrong-weight').value = quizSettings.wrongWeight;
                    document.getElementById('setting-correct-weight').value = quizSettings.correctWeight;
                    document.getElementById('setting-max-count').value = quizSettings.maxCount;
                    document.getElementById('setting-decay').value = quizSettings.decay;

                    // API key status (from env var)
                    const apiKeyInput = document.getElementById('api-key');
                    if (config.hasApiKey) {
                        apiKeyInput.placeholder = '(set via CLAUDE_API_KEY env var)';
                        apiKeyInput.disabled = true;
                    } else {
                        apiKeyInput.placeholder = 'Set CLAUDE_API_KEY environment variable';
                        apiKeyInput.disabled = true;
                    }
                })
                .catch(err => console.error('Failed to load settings:', err));
        }

        function loadTags() {
            fetch('/api/tags')
                .then(r => r.json())
                .then(data => {
                    const tags = data.tags || [];
                    // Populate tag filter dropdowns
                    ['list-tag-filter', 'quiz-tag-filter'].forEach(id => {
                        const select = document.getElementById(id);
                        if (select) {
                            const currentVal = select.value;
                            select.innerHTML = '<option value="">All</option>';
                            tags.forEach(tag => {
                                select.innerHTML += `<option value="${tag}">${tag}</option>`;
                            });
                            select.value = currentVal; // Preserve selection
                        }
                    });
                })
                .catch(err => console.error('Failed to load tags:', err));
        }

        function saveSettings() {
            quizSettings = {
                wrongWeight: parseFloat(document.getElementById('setting-wrong-weight').value) || 1.0,
                correctWeight: parseFloat(document.getElementById('setting-correct-weight').value) || 0.5,
                maxCount: parseInt(document.getElementById('setting-max-count').value) || 20,
                decay: parseInt(document.getElementById('setting-decay').value) || 1
            };

            fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({quiz: quizSettings})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    closeSettings();
                }
            })
            .catch(err => console.error('Failed to save settings:', err));
        }

        // Load settings on page load
        document.addEventListener('DOMContentLoaded', () => {
            loadSettings();
            loadTags();
        });

        // EDIT MODAL
        let editModalContext = null; // 'list' or 'lookup' - to know which to refresh

        function openEditModal(index, chars, english, pinyin, dictPinyin, pypinyinPinyin, audio, context, tags) {
            editModalContext = context || 'list';
            document.getElementById('edit-index').value = index;
            document.getElementById('edit-chars').textContent = chars;
            document.getElementById('edit-english').value = english;
            document.getElementById('edit-pinyin').value = pinyin || '';
            document.getElementById('edit-tags').value = (tags || []).join(', ');
            document.getElementById('edit-pinyin-options').innerHTML = '';

            // Audio button
            const audioContainer = document.getElementById('edit-audio-container');
            if (audio) {
                audioContainer.innerHTML = `<button class="audio-btn" onclick="playAudio('${audio}')">🔊 Play Audio</button>`;
            } else {
                audioContainer.innerHTML = '';
            }

            document.getElementById('edit-modal').classList.add('active');
            document.getElementById('edit-english').focus();
        }

        function lookupEditPinyin() {
            const chars = document.getElementById('edit-chars').textContent;
            if (!chars) return;

            fetch('/api/pinyin_lookup?chars=' + encodeURIComponent(chars))
                .then(r => r.json())
                .then(data => {
                    const container = document.getElementById('edit-pinyin-options');
                    if (!data.dict && !data.pypinyin) {
                        container.innerHTML = '<span style="color: #999; font-size: 13px;">No pinyin found</span>';
                        return;
                    }

                    let html = '<span style="font-size: 13px;">Choose: </span>';
                    if (data.dict) {
                        html += `<button class="secondary" onclick="document.getElementById('edit-pinyin').value='${data.dict}'" style="padding: 3px 8px; font-size: 13px; margin-right: 5px;">dict: ${data.dict}</button>`;
                    }
                    if (data.pypinyin && data.pypinyin !== data.dict) {
                        html += `<button class="secondary" onclick="document.getElementById('edit-pinyin').value='${data.pypinyin}'" style="padding: 3px 8px; font-size: 13px;">pypinyin: ${data.pypinyin}</button>`;
                    }
                    container.innerHTML = html;
                });
        }

        function closeEditModal() {
            document.getElementById('edit-modal').classList.remove('active');
            editModalContext = null;
        }

        function saveEditModal() {
            const index = parseInt(document.getElementById('edit-index').value);
            const english = document.getElementById('edit-english').value.trim();
            const pinyinEl = document.getElementById('edit-pinyin');
            const pinyin = pinyinEl ? (pinyinEl.value || pinyinEl.textContent).trim() : '';
            const tagsStr = document.getElementById('edit-tags').value.trim();
            const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(t => t) : [];

            if (!english) {
                alert('English is required');
                return;
            }

            fetch('/api/edit', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index, english, pinyin, tags})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    closeEditModal();
                    loadTags();  // Refresh tag dropdowns with any new tags
                    if (editModalContext === 'lookup') doSearch();
                    else refreshList();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }

        function deleteFromModal() {
            const index = parseInt(document.getElementById('edit-index').value);
            const chars = document.getElementById('edit-chars').textContent;
            if (!confirm(`Delete "${chars}"?`)) return;

            fetch('/api/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    closeEditModal();
                    if (editModalContext === 'lookup') doSearch();
                    else refreshList();
                    loadHomeStats();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }

        function loadHomeStats() {
            fetch('/api/list')
                .then(r => r.json())
                .then(data => {
                    const total = data.total || 0;
                    // Update vocab card on home
                    document.getElementById('home-vocab-count').innerHTML = `<strong>${total}</strong> words`;
                });
        }

        function loadQuizStats() {
            fetch('/api/list')
                .then(r => r.json())
                .then(data => {
                    const total = data.total || 0;
                    let statsHtml = `<strong>${total}</strong> words in vocabulary`;
                    if (total > 0) {
                        const withStats = data.vocab.filter(v => v.stats && (v.stats.correct || v.stats.wrong));
                        if (withStats.length > 0) {
                            const totalCorrect = withStats.reduce((sum, v) => sum + (v.stats.correct || 0), 0);
                            const totalWrong = withStats.reduce((sum, v) => sum + (v.stats.wrong || 0), 0);
                            statsHtml += ` · Quiz history: ${totalCorrect} ✓ / ${totalWrong} ✗`;
                        }
                    }
                    document.getElementById('quiz-stats-summary').innerHTML = statsHtml;
                });
        }

        // Load stats on page load
        loadHomeStats();

        // LOOKUP
        let lookupQuery = '';
        let lookupDictOffset = 0;

        function doSearch(loadMore = false) {
            const query = document.getElementById('search-input').value;
            if (!loadMore) {
                lookupQuery = query;
                lookupDictOffset = 0;
            }
            fetch('/api/lookup?q=' + encodeURIComponent(lookupQuery) + '&offset=' + lookupDictOffset)
                .then(r => r.json())
                .then(data => {
                    if (!loadMore) {
                        let vocabHtml = '';
                        data.vocab.forEach(v => {
                            const idx = v._index;
                            const hasPinyinOptions = v.pinyin_pypinyin && v.pinyin_dict;
                            const escEnglish = v.english.replace(/'/g, "\\'");
                            const tagsJson = JSON.stringify(v.tags || []);
                            const editParams = `${idx}, '${v.characters || ''}', '${escEnglish}', '${v.pinyin || ''}', ${hasPinyinOptions ? `'${v.pinyin_dict}', '${v.pinyin_pypinyin}'` : 'null, null'}, '${v.audio || ''}', 'lookup', ${tagsJson}`;
                            vocabHtml += `<div class="vocab-item" onclick="openEditModal(${editParams})" style="cursor: pointer;">
                                <span class="vocab-english">${v.english}</span>
                                <span class="vocab-chars chinese">${v.characters || ''}</span>
                                <span class="vocab-pinyin pinyin">${v.pinyin || ''}</span>
                                ${v.audio ? `<button class="audio-btn" onclick="event.stopPropagation(); playAudio('${v.audio}')">🔊</button>` : ''}
                            </div>`;
                        });
                        document.getElementById('vocab-results').innerHTML = vocabHtml || '<p>(not in vocabulary)</p>';
                    }

                    let dictHtml = loadMore ? '' : '';
                    data.dict.forEach(d => {
                        let pinyinDisplay = d.pinyin;
                        if (d.pinyin_pypinyin) {
                            pinyinDisplay = `${d.pinyin} <span style="color: #999; font-size: 12px;">(pypinyin: ${d.pinyin_pypinyin})</span>`;
                        }
                        dictHtml += `<div class="vocab-item">
                            <span class="vocab-chars chinese">${d.simplified}</span>
                            <span class="vocab-pinyin pinyin">${pinyinDisplay}</span>
                            <span>${d.definitions.slice(0, 3).join(', ')}</span>
                        </div>`;
                    });

                    // Count display
                    const showing = data.dict_offset + data.dict.length;
                    let countHtml = data.dict_total > 0 ? `<p style="color: #666; font-size: 14px;">Showing ${showing} of ${data.dict_total}</p>` : '';

                    // Load more button
                    if (data.dict_has_more) {
                        dictHtml += `<button class="secondary" onclick="loadMoreLookup()" style="margin-top: 10px;">Load More</button>`;
                    }

                    if (loadMore) {
                        // Append to existing results (remove old Load More button first)
                        const container = document.getElementById('dict-results');
                        const oldBtn = container.querySelector('button');
                        if (oldBtn) oldBtn.remove();
                        container.insertAdjacentHTML('beforeend', dictHtml);
                        // Update count
                        const countEl = document.getElementById('dict-count');
                        if (countEl) countEl.innerHTML = countHtml;
                    } else {
                        document.getElementById('dict-count').innerHTML = countHtml;
                        document.getElementById('dict-results').innerHTML = dictHtml || '';
                    }
                });
        }

        function loadMoreLookup() {
            lookupDictOffset += 10;
            doSearch(true);
        }

        function lookupEditWord(index, english, pinyin, dictPinyin, pypinyinPinyin) {
            const englishSpan = document.getElementById(`lookup-english-${index}`);
            const pinyinSpan = document.getElementById(`lookup-pinyin-${index}`);
            const item = document.getElementById(`lookup-item-${index}`);

            // Replace English with input
            englishSpan.innerHTML = `<input type="text" id="lookup-edit-english-${index}" value="${english}" style="width: 150px;">`;

            // Replace pinyin with selector if options exist
            if (dictPinyin && pypinyinPinyin && dictPinyin !== pypinyinPinyin) {
                const isDict = pinyin === dictPinyin;
                pinyinSpan.innerHTML = `
                    <select id="lookup-edit-pinyin-${index}">
                        <option value="${dictPinyin}" ${isDict ? 'selected' : ''}>dict: ${dictPinyin}</option>
                        <option value="${pypinyinPinyin}" ${!isDict ? 'selected' : ''}>pypinyin: ${pypinyinPinyin}</option>
                    </select>`;
            }

            // Replace buttons
            const buttons = item.querySelectorAll('button.secondary, button.danger');
            buttons.forEach(b => b.style.display = 'none');
            item.insertAdjacentHTML('beforeend', `
                <button class="secondary" onclick="lookupSaveEdit(${index})" id="lookup-save-btn-${index}">Save</button>
                <button onclick="doSearch()" id="lookup-cancel-btn-${index}">Cancel</button>
            `);
        }

        function lookupSaveEdit(index) {
            const englishInput = document.getElementById(`lookup-edit-english-${index}`);
            const pinyinSelect = document.getElementById(`lookup-edit-pinyin-${index}`);

            const english = englishInput ? englishInput.value.trim() : null;
            const pinyin = pinyinSelect ? pinyinSelect.value : null;

            fetch('/api/edit', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index, english, pinyin})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    doSearch();  // Refresh lookup results
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }

        function lookupDeleteWord(index, english) {
            if (!confirm('Delete "' + english + '"?')) return;
            fetch('/api/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) doSearch();  // Refresh lookup results
            });
        }

        document.getElementById('search-input').addEventListener('keypress', e => {
            if (e.key === 'Enter') doSearch();
        });

        // ADD
        let searchMatches = [];  // Store matches for pinyin selection
        let selectedMatchIdx = -1;  // Track which match is selected
        let addSearchQuery = '';
        let addSearchOffset = 0;

        function searchPinyin(loadMore = false) {
            const pinyin = document.getElementById('add-pinyin').value;
            if (!loadMore) {
                addSearchQuery = pinyin;
                addSearchOffset = 0;
                searchMatches = [];
                selectedMatchIdx = -1;
            }
            fetch('/api/search_pinyin?p=' + encodeURIComponent(addSearchQuery) + '&offset=' + addSearchOffset)
                .then(r => r.json())
                .then(data => {
                    const baseIdx = searchMatches.length;
                    searchMatches = searchMatches.concat(data.matches);

                    let html = '';
                    data.matches.forEach((m, i) => {
                        const idx = baseIdx + i;
                        let pinyinOptions = '';
                        if (m.pinyin_pypinyin) {
                            pinyinOptions = `<div style="margin-top: 5px; font-size: 13px;">
                                <label><input type="radio" name="pinyin_${idx}" value="dict" checked onchange="updatePinyin(${idx})"> dict: ${m.pinyin}</label>
                                <label style="margin-left: 10px;"><input type="radio" name="pinyin_${idx}" value="pypinyin" onchange="updatePinyin(${idx})"> pypinyin: ${m.pinyin_pypinyin}</label>
                            </div>`;
                        }
                        html += `<div class="match-item" onclick="selectMatch(${idx})">
                            <button class="audio-btn" onclick="event.stopPropagation(); previewAudio('${m.simplified}')" style="margin-right: 8px;">🔊</button>
                            <span class="chinese" style="font-size: 20px;">${m.simplified}</span>
                            <span class="pinyin">(${m.pinyin})</span>
                            - ${m.definitions.slice(0, 2).join(', ')}
                            ${pinyinOptions}
                        </div>`;
                    });

                    // Count display
                    const showing = data.offset + data.matches.length;
                    let countHtml = data.total > 0 ? `<p style="color: #666; font-size: 14px;">Showing ${showing} of ${data.total}</p>` : '';

                    // Load more button
                    if (data.has_more) {
                        html += `<button class="secondary" onclick="loadMoreAdd()" style="margin-top: 10px;">Load More</button>`;
                    }

                    if (loadMore) {
                        // Append to existing results
                        const container = document.getElementById('pinyin-matches');
                        const oldBtn = container.querySelector('button.secondary');
                        if (oldBtn) oldBtn.remove();
                        container.insertAdjacentHTML('beforeend', html);
                        document.getElementById('add-count').innerHTML = countHtml;
                    } else {
                        document.getElementById('add-count').innerHTML = countHtml;
                        document.getElementById('pinyin-matches').innerHTML = html || '<p>No matches</p>';
                    }
                });
        }

        function loadMoreAdd() {
            addSearchOffset += 10;
            searchPinyin(true);
        }

        function selectMatch(idx) {
            document.querySelectorAll('.match-item').forEach((el, i) => {
                el.classList.toggle('selected', i === idx);
            });
            selectedMatchIdx = idx;
            const m = searchMatches[idx];
            // Check which pinyin is selected
            let pinyin = m.pinyin;
            if (m.pinyin_pypinyin) {
                const radio = document.querySelector(`input[name="pinyin_${idx}"]:checked`);
                if (radio && radio.value === 'pypinyin') {
                    pinyin = m.pinyin_pypinyin;
                }
            }
            document.getElementById('add-chars').value = m.simplified;
            document.getElementById('add-pinyin').value = pinyin;
            // Auto-fill English from first definition if empty
            const englishField = document.getElementById('add-english');
            if (!englishField.value.trim() && m.definitions.length > 0) {
                englishField.value = m.definitions[0];
            }
        }

        function updatePinyin(idx) {
            // Called when radio button changes - update pinyin field if this match is selected
            if (selectedMatchIdx !== idx) {
                // Auto-select this match when clicking its radio button
                selectMatch(idx);
                return;
            }
            const m = searchMatches[idx];
            const radio = document.querySelector(`input[name="pinyin_${idx}"]:checked`);
            if (radio) {
                document.getElementById('add-pinyin').value = (radio.value === 'pypinyin') ? m.pinyin_pypinyin : m.pinyin;
            }
        }

        function addWord(force = false, update = false) {
            const english = document.getElementById('add-english').value;
            const chars = document.getElementById('add-chars').value;
            const pinyin = document.getElementById('add-pinyin').value;

            fetch('/api/add', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({english, chars, pinyin, force, update})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    const action = update ? 'Updated' : 'Added';
                    let msg = `<p style="color: green;">${action}: ${data.entry.english} - ${data.entry.characters} (${data.entry.pinyin})</p>`;
                    if (data.pinyin_pypinyin && data.pinyin_dict) {
                        msg += `<p style="color: #666; font-size: 14px;">Note: pypinyin="${data.pinyin_pypinyin}" vs dictionary="${data.pinyin_dict}"</p>`;
                    }
                    document.getElementById('add-result').innerHTML = msg;
                    document.getElementById('add-english').value = '';
                    document.getElementById('add-chars').value = '';
                    document.getElementById('add-pinyin').value = '';
                    document.getElementById('pinyin-matches').innerHTML = '';
                    selectedMatchIdx = -1;
                } else if (data.duplicate) {
                    // Show duplicate warning with options
                    const ex = data.existing;
                    let msg = `<p style="color: orange;"><strong>⚠ Already exists:</strong> ${ex.english} - ${ex.characters} (${ex.pinyin || ''})</p>`;
                    msg += `<p style="margin-top: 10px;">
                        <button class="secondary" onclick="addWord(true, false)">Add Anyway</button>
                        <button class="secondary" onclick="addWord(false, true)" style="margin-left: 10px;">Update Existing</button>
                    </p>`;
                    document.getElementById('add-result').innerHTML = msg;
                } else {
                    document.getElementById('add-result').innerHTML =
                        `<p style="color: red;">Error: ${data.error}</p>`;
                }
            });
        }

        // LIST
        let listOffset = 0;

        // Calculate weight (duplicated here for list display - same as quiz)
        function calcWeightForList(stats) {
            const correct = stats?.correct || 0;
            const wrong = stats?.wrong || 0;
            const weight = 1 + quizSettings.wrongWeight * Math.log(1 + wrong) - quizSettings.correctWeight * Math.log(1 + correct);
            return Math.max(0.1, weight);
        }

        function refreshList(loadMore = false) {
            if (!loadMore) listOffset = 0;
            const showStats = document.getElementById('show-stats').checked;
            const tagFilter = document.getElementById('list-tag-filter').value;
            const tagParam = tagFilter ? '&tag=' + encodeURIComponent(tagFilter) : '';
            fetch('/api/list?offset=' + listOffset + '&limit=10' + tagParam)
                .then(r => r.json())
                .then(data => {
                    let html = '';
                    data.vocab.forEach((v, i) => {
                        const idx = data.offset + i;
                        let pinyinDisplay = v.pinyin || '';
                        // Store raw pinyin options for editing
                        const hasPinyinOptions = v.pinyin_pypinyin && v.pinyin_dict;
                        if (hasPinyinOptions) {
                            pinyinDisplay += ` <span style="color: #999; font-size: 11px;">(dict: ${v.pinyin_dict} | pypinyin: ${v.pinyin_pypinyin})</span>`;
                        }
                        // Stats display (both quiz stats and character stats if present)
                        let statsDisplay = '';
                        if (showStats) {
                            const qC = v.stats?.correct || 0;
                            const qW = v.stats?.wrong || 0;
                            const cC = v.char_stats?.correct || 0;
                            const cW = v.char_stats?.wrong || 0;
                            let parts = [];
                            if (qC || qW) parts.push(`Q: ✓${qC} ✗${qW}`);
                            if (cC || cW) parts.push(`字: ✓${cC} ✗${cW}`);
                            if (parts.length > 0) {
                                statsDisplay = `<span style="color: #666; font-size: 11px; margin-left: 10px;">${parts.join(' | ')}</span>`;
                            }
                        }
                        const escEnglish = v.english.replace(/'/g, "\\'");
                        const tagsJson = JSON.stringify(v.tags || []);
                        const editParams = `${idx}, '${v.characters || ''}', '${escEnglish}', '${v.pinyin || ''}', ${hasPinyinOptions ? `'${v.pinyin_dict}', '${v.pinyin_pypinyin}'` : 'null, null'}, '${v.audio || ''}', 'list', ${tagsJson}`;
                        const focusStar = v.focus ? '★' : '☆';
                        const focusStyle = v.focus ? 'color: #f0ad4e;' : 'color: #ccc;';
                        html += `<div class="vocab-item" id="vocab-item-${idx}" onclick="openEditModal(${editParams})" style="cursor: pointer;">
                            <span onclick="event.stopPropagation(); toggleFocus(${idx})" style="cursor: pointer; font-size: 18px; ${focusStyle}" title="Toggle focus">${focusStar}</span>
                            <span>${idx + 1}.</span>
                            <span class="vocab-english">${v.english}</span>
                            <span class="vocab-chars chinese">${v.characters || ''}</span>
                            <span class="vocab-pinyin pinyin">${v.pinyin || ''}</span>
                            ${statsDisplay}
                            ${v.audio ? `<button class="audio-btn" onclick="event.stopPropagation(); playAudio('${v.audio}')">🔊</button>` : ''}
                        </div>`;
                    });

                    // Count display
                    const showing = data.offset + data.vocab.length;
                    let countHtml = data.total > 0 ? `<p style="color: #666; font-size: 14px;">Showing ${showing} of ${data.total}</p>` : '';

                    // Load more button
                    if (data.has_more) {
                        html += `<button class="secondary" onclick="loadMoreList()" style="margin-top: 10px;">Load More</button>`;
                    }

                    if (loadMore) {
                        const container = document.getElementById('vocab-list');
                        const oldBtn = container.querySelector('button.secondary');
                        if (oldBtn) oldBtn.remove();
                        container.insertAdjacentHTML('beforeend', html);
                        document.getElementById('list-count').innerHTML = countHtml;
                    } else {
                        document.getElementById('list-count').innerHTML = countHtml;
                        document.getElementById('vocab-list').innerHTML = html || '<p>Vocabulary is empty</p>';
                    }
                });
        }

        function loadMoreList() {
            listOffset += 10;
            refreshList(true);
        }

        function toggleFocus(index) {
            fetch('/api/toggle_focus', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Update just the star without full refresh
                    const item = document.getElementById(`vocab-item-${index}`);
                    if (item) {
                        const star = item.querySelector('span[title="Toggle focus"]');
                        if (star) {
                            star.textContent = data.focus ? '★' : '☆';
                            star.style.color = data.focus ? '#f0ad4e' : '#ccc';
                        }
                    }
                }
            });
        }

        function deleteWord(index) {
            fetch('/api/list')
                .then(r => r.json())
                .then(data => {
                    const entry = data.vocab[index];
                    if (!entry) return;
                    if (!confirm('Delete "' + entry.english + '"?')) return;
                    fetch('/api/delete', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({index})
                    })
                    .then(r => r.json())
                    .then(data => {
                        if (data.success) refreshList();
                    });
                });
        }

        // Audio mode descriptions
        const audioModeDescs = {
            smart: 'Reuse existing audio files where possible, generate only for entries without audio.',
            renumber: 'Only rename existing files to match current indices. No gTTS calls.',
            force: 'Regenerate all audio files from scratch (for corruption or quality issues).'
        };

        function updateAudioModeDesc() {
            const mode = document.getElementById('audio-rebuild-mode').value;
            document.getElementById('audio-mode-desc').textContent = audioModeDescs[mode];
        }

        // Add listener after DOM loads
        document.addEventListener('DOMContentLoaded', () => {
            document.getElementById('audio-rebuild-mode').addEventListener('change', updateAudioModeDesc);
        });

        function rebuildAudio() {
            const mode = document.getElementById('audio-rebuild-mode').value;
            const modeNames = {smart: 'Smart rebuild', renumber: 'Renumber', force: 'Force rebuild'};
            if (!confirm(`${modeNames[mode]}: ${audioModeDescs[mode]}\n\nProceed?`)) return;

            closeSettings();
            alert('Rebuilding audio... This runs in the background.');

            fetch('/api/rebuild_audio', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({mode: mode})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    let msg = `Done: ${data.renamed} renamed`;
                    if (data.generated !== undefined) msg += `, ${data.generated} generated`;
                    if (data.skipped !== undefined) msg += `, ${data.skipped} skipped`;
                    alert(msg);
                    refreshList();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }

        function editWord(index, english, pinyin, dictPinyin, pypinyinPinyin) {
            const englishSpan = document.getElementById(`english-${index}`);
            const pinyinSpan = document.getElementById(`pinyin-${index}`);
            const item = document.getElementById(`vocab-item-${index}`);

            // Replace English with input
            englishSpan.innerHTML = `<input type="text" id="edit-english-${index}" value="${english}" style="width: 150px;">`;

            // Replace pinyin with selector if options exist
            if (dictPinyin && pypinyinPinyin && dictPinyin !== pypinyinPinyin) {
                const isDict = pinyin === dictPinyin;
                pinyinSpan.innerHTML = `
                    <select id="edit-pinyin-${index}">
                        <option value="${dictPinyin}" ${isDict ? 'selected' : ''}>dict: ${dictPinyin}</option>
                        <option value="${pypinyinPinyin}" ${!isDict ? 'selected' : ''}>pypinyin: ${pypinyinPinyin}</option>
                    </select>`;
            }

            // Replace buttons
            const buttons = item.querySelectorAll('button.secondary, button.danger');
            buttons.forEach(b => b.style.display = 'none');
            item.insertAdjacentHTML('beforeend', `
                <button class="secondary" onclick="saveEdit(${index})" id="save-btn-${index}">Save</button>
                <button onclick="cancelEdit()" id="cancel-btn-${index}">Cancel</button>
            `);
        }

        function saveEdit(index) {
            const englishInput = document.getElementById(`edit-english-${index}`);
            const pinyinSelect = document.getElementById(`edit-pinyin-${index}`);

            const english = englishInput ? englishInput.value.trim() : null;
            const pinyin = pinyinSelect ? pinyinSelect.value : null;

            fetch('/api/edit', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index, english, pinyin})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    refreshList();
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }

        function cancelEdit() {
            refreshList();
        }

        // QUIZ
        function resetStats(statType = 'both') {
            const typeLabels = {
                'stats': 'quiz stats',
                'char_stats': 'character stats',
                'both': 'all stats'
            };
            if (!confirm(`Reset ${typeLabels[statType]} to zero?`)) return;
            fetch('/api/reset_stats', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({statType: statType})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    alert('Stats reset successfully');
                }
            });
        }

        // Calculate weight for weighted quiz ordering
        function calcWeight(stats) {
            const correct = stats?.correct || 0;
            const wrong = stats?.wrong || 0;
            const weight = 1 + quizSettings.wrongWeight * Math.log(1 + wrong) - quizSettings.correctWeight * Math.log(1 + correct);
            return Math.max(0.1, weight);  // Floor at 0.1
        }

        // Weighted random selection
        function weightedShuffle(entries, useCharStats = false) {
            const result = [];
            const items = entries.map(e => ({
                entry: e,
                weight: calcWeight(useCharStats ? e.char_stats : e.stats)
            }));

            while (items.length > 0) {
                const totalWeight = items.reduce((sum, item) => sum + item.weight, 0);
                let random = Math.random() * totalWeight;

                for (let i = 0; i < items.length; i++) {
                    random -= items[i].weight;
                    if (random <= 0) {
                        result.push(items[i].entry);
                        items.splice(i, 1);
                        break;
                    }
                }
            }
            return result;
        }

        // Determine if quiz involves characters (for stats selection)
        function quizUsesCharacters() {
            const showMode = document.getElementById('quiz-show').value;
            const answerMode = document.getElementById('quiz-answer').value;
            return showMode === 'characters' || answerMode === 'characters';
        }

        function startQuiz() {
            const tagFilter = document.getElementById('quiz-tag-filter').value;
            const tagParam = tagFilter ? '?tag=' + encodeURIComponent(tagFilter) : '';
            fetch('/api/list' + tagParam)
                .then(r => r.json())
                .then(data => {
                    if (data.vocab.length < 1) {
                        alert('Need at least 1 vocabulary entry');
                        return;
                    }

                    // Add original index to each entry for stats tracking
                    let entriesWithIndex = data.vocab.map((v, i) => ({...v, _index: i}));

                    // Filter by focus if checked
                    const focusOnly = document.getElementById('quiz-focus-only').checked;
                    if (focusOnly) {
                        entriesWithIndex = entriesWithIndex.filter(v => v.focus);
                        if (entriesWithIndex.length < 1) {
                            alert('No focus words marked. Star some words in the List first.');
                            return;
                        }
                    }

                    // Determine which stats to use
                    const useCharStats = quizUsesCharacters();

                    // Apply ordering based on selection
                    const order = document.getElementById('quiz-order').value;
                    if (order === 'random') {
                        quizEntries = entriesWithIndex.sort(() => Math.random() - 0.5);
                    } else if (order === 'weighted') {
                        quizEntries = weightedShuffle(entriesWithIndex, useCharStats);
                    } else {
                        // inorder - keep as is
                        quizEntries = entriesWithIndex;
                    }

                    // Store full vocab for duplicate matching before limiting
                    quizAllEntries = entriesWithIndex;

                    // Limit to selected count (0 = all)
                    const count = parseInt(document.getElementById('quiz-count').value);
                    if (count > 0 && quizEntries.length > count) {
                        quizEntries = quizEntries.slice(0, count);
                    }

                    quizIndex = 0;
                    quizCorrect = 0;
                    quizTotal = 0;
                    nextQuestion();
                });
        }

        function nextQuestion() {
            // Hide next button, show input area
            document.getElementById('quiz-next-btn').style.display = 'none';
            document.getElementById('quiz-input-area').style.display = 'flex';

            if (quizIndex >= quizEntries.length) {
                document.getElementById('quiz-prompt').textContent =
                    'Quiz Complete! ' + quizCorrect + '/' + quizTotal;
                document.getElementById('quiz-play-audio').style.display = 'none';
                document.getElementById('quiz-input-area').style.display = 'none';
                return;
            }

            currentEntry = quizEntries[quizIndex];
            currentAudio = currentEntry.audio;
            const showMode = document.getElementById('quiz-show').value;
            const prompt = document.getElementById('quiz-prompt');
            const playAudioBtn = document.getElementById('quiz-play-audio');

            // Show play audio button (but hide when showing English - would give away answer)
            if (showMode === 'english') {
                playAudioBtn.style.display = 'none';
            } else {
                playAudioBtn.style.display = currentAudio ? 'inline-block' : 'none';
            }

            if (showMode === 'english') {
                prompt.textContent = currentEntry.english;
                prompt.className = 'quiz-prompt';
            } else if (showMode === 'characters') {
                prompt.textContent = currentEntry.characters || '?';
                prompt.className = 'quiz-prompt chinese';
            } else if (showMode === 'pinyin') {
                prompt.textContent = currentEntry.pinyin || '?';
                prompt.className = 'quiz-prompt pinyin';
            } else if (showMode === 'audio') {
                prompt.textContent = '🔊';
                prompt.className = 'quiz-prompt';
                playQuizAudio();  // Auto-play for audio-only mode
            }

            document.getElementById('quiz-input').value = '';
            document.getElementById('quiz-feedback').textContent = '';
            document.getElementById('quiz-input').focus();
        }

        function playQuizAudio() {
            if (currentAudio) playAudio(currentAudio);
        }

        function quizEditEntry() {
            if (!currentEntry || currentEntry._index === undefined) return;

            const englishSpan = document.getElementById('quiz-english-display');
            if (!englishSpan) return;

            // Replace with input
            const currentEnglish = currentEntry.english || '';
            englishSpan.innerHTML = `
                <input type="text" id="quiz-edit-english" value="${currentEnglish.replace(/"/g, '&quot;')}" style="width: 200px;">
                <button class="secondary" onclick="quizSaveEdit()" style="padding: 2px 8px; font-size: 12px;">Save</button>
                <button onclick="quizCancelEdit('${currentEnglish.replace(/'/g, "\\'")}')" style="padding: 2px 8px; font-size: 12px;">Cancel</button>
            `;
            document.getElementById('quiz-edit-english').focus();
        }

        function quizSaveEdit() {
            const input = document.getElementById('quiz-edit-english');
            if (!input || currentEntry._index === undefined) return;

            const newEnglish = input.value.trim();
            fetch('/api/edit', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index: currentEntry._index, english: newEnglish})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    currentEntry.english = newEnglish;
                    document.getElementById('quiz-english-display').textContent = newEnglish;
                } else {
                    alert('Error: ' + data.error);
                }
            });
        }

        function quizCancelEdit(original) {
            document.getElementById('quiz-english-display').textContent = original;
        }

        function quizDeleteEntry() {
            if (!currentEntry || currentEntry._index === undefined) return;
            if (!confirm('Delete "' + currentEntry.english + '"?')) return;

            fetch('/api/delete', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({index: currentEntry._index})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Remove from quiz entries and continue
                    document.getElementById('quiz-feedback').innerHTML = '<span style="color: #999;">Entry deleted</span>';
                }
            });
        }

        function checkAnswer() {
            if (!currentEntry) return;

            const answer = document.getElementById('quiz-input').value.trim();
            const answerMode = document.getElementById('quiz-answer').value;
            const feedback = document.getElementById('quiz-feedback');

            let correct = false;
            let correctAnswer = '';

            if (answerMode === 'english') {
                correctAnswer = currentEntry.english;
                correct = matchEnglish(answer, correctAnswer);
            } else if (answerMode === 'characters') {
                correctAnswer = currentEntry.characters || '';
                // Check if answer matches this entry OR any other entry with same English (for duplicates like "where")
                const showMode = document.getElementById('quiz-show').value;
                if (showMode === 'english') {
                    // Accept any characters that match an entry with the same English (search full vocab, not just quiz subset)
                    correct = quizAllEntries.some(e =>
                        e.english === currentEntry.english && e.characters === answer
                    );
                } else {
                    correct = answer === correctAnswer;
                }
            } else if (answerMode === 'pinyin') {
                correctAnswer = currentEntry.pinyin || '';
                const requireTones = document.getElementById('quiz-require-tones').checked;
                const showMode = document.getElementById('quiz-show').value;

                // Choose comparison function based on tone requirement
                const pinyinMatch = requireTones ? comparePinyinWithTones : (a, b) => stripTones(a) === stripTones(b);

                if (showMode === 'english') {
                    // Accept any pinyin that matches an entry with the same English (search full vocab, not just quiz subset)
                    correct = quizAllEntries.some(e =>
                        e.english === currentEntry.english && pinyinMatch(answer, e.pinyin || '')
                    );
                } else {
                    correct = pinyinMatch(answer, correctAnswer);
                }
            }

            quizTotal++;
            // Show full entry info: characters (pinyin) - English
            // Include both pypinyin and dict pinyin when they differ
            let pinyinDisplay = currentEntry.pinyin || '';
            if (currentEntry.pinyin_pypinyin && currentEntry.pinyin_dict) {
                pinyinDisplay = `${currentEntry.pinyin} <span style="color: #999; font-size: 14px;">(dict: ${currentEntry.pinyin_dict} | pypinyin: ${currentEntry.pinyin_pypinyin})</span>`;
            }
            const entryInfo = `<span class="chinese">${currentEntry.characters || ''}</span> ` +
                `<span class="pinyin">(${pinyinDisplay})</span> - <span id="quiz-english-display">${currentEntry.english}</span>`;

            // Determine which stats to use based on quiz mode
            const useCharStats = quizUsesCharacters();
            const currentStats = useCharStats ? currentEntry.char_stats : currentEntry.stats;

            // Stats display (show what they'll be AFTER this answer)
            let newCorrect = currentStats?.correct || 0;
            let newWrong = currentStats?.wrong || 0;
            if (correct) {
                newCorrect = Math.min(quizSettings.maxCount, newCorrect + 1);
                newWrong = Math.max(0, newWrong - quizSettings.decay);
            } else {
                newWrong = Math.min(quizSettings.maxCount, newWrong + 1);
                newCorrect = Math.max(0, newCorrect - quizSettings.decay);
            }
            const newWeight = calcWeight({correct: newCorrect, wrong: newWrong}).toFixed(2);
            const statsLabel = useCharStats ? '字' : '';  // Show 字 for character stats
            const statsInfo = `<span style="color: #666; font-size: 12px; margin-left: 10px;">[${statsLabel}✓${newCorrect} ✗${newWrong} w:${newWeight}]</span>`;

            // Edit/delete buttons for quiz feedback
            const editBtns = `<span style="margin-left: 15px;">
                <button class="secondary" onclick="quizEditEntry()" style="padding: 2px 8px; font-size: 12px;">Edit</button>
                <button class="danger" onclick="quizDeleteEntry()" style="padding: 2px 8px; font-size: 12px;">Delete</button>
            </span>`;

            // Show audio button after answering (was hidden in English mode)
            if (currentAudio) {
                document.getElementById('quiz-play-audio').style.display = 'inline-block';
            }

            if (correct) {
                quizCorrect++;
                feedback.innerHTML = '✓ Correct! ' + entryInfo + statsInfo + editBtns;
                feedback.className = 'quiz-feedback correct';
            } else {
                const yourAnswer = `<span style="color: #c00; font-size: 13px;"> (you said: "${answer}")</span>`;
                feedback.innerHTML = '✗ Wrong.' + yourAnswer + ' ' + entryInfo + statsInfo + editBtns;
                feedback.className = 'quiz-feedback wrong';
                if (currentEntry.audio) playAudio(currentEntry.audio);
            }

            document.getElementById('quiz-score').textContent = 'Score: ' + quizCorrect + '/' + quizTotal;

            // Update stats in backend
            if (currentEntry._index !== undefined) {
                fetch('/api/update_stats', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        index: currentEntry._index,
                        correct: correct,
                        maxCount: quizSettings.maxCount,
                        decay: quizSettings.decay,
                        statType: useCharStats ? 'char_stats' : 'stats'
                    })
                });
            }

            quizIndex++;
            // Show next button instead of auto-advancing
            document.getElementById('quiz-input-area').style.display = 'none';
            document.getElementById('quiz-next-btn').style.display = 'block';
        }

        document.getElementById('quiz-input').addEventListener('keypress', e => {
            if (e.key === 'Enter') checkAnswer();
        });

        // AUDIO
        function playAudio(path) {
            fetch('/api/audio?path=' + encodeURIComponent(path))
                .then(r => r.blob())
                .then(blob => {
                    const url = URL.createObjectURL(blob);
                    new Audio(url).play();
                });
        }

        // Preview audio using gTTS (for dictionary entries not yet added)
        function previewAudio(text) {
            fetch('/api/preview_audio?text=' + encodeURIComponent(text))
                .then(r => r.blob())
                .then(blob => {
                    const url = URL.createObjectURL(blob);
                    new Audio(url).play();
                })
                .catch(err => console.error('Preview audio failed:', err));
        }
    </script>
</body>
</html>
'''


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


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
