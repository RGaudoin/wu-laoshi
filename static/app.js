// Wu Laoshi - Mandarin Vocabulary Tool

// HTML-escape user data to prevent stored XSS
function esc(s) {
    if (s == null) return '';
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

let quizEntries = [];
        let quizAllEntries = [];  // Full vocab for duplicate matching (not limited by count)
        let quizIndex = 0;
        let quizCorrect = 0;
        let quizTotal = 0;
        let currentEntry = null;
        let currentAudio = null;
        let lastAnswerStats = null;  // For override feature: stores {index, originalStats, statType}

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
                    .replace(/^(the|a|an)\s+/i, '')  // strip articles (no articles in Mandarin)
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

            // Exact match on any part (also try with "to" stripped as infinitive marker)
            const stripTo = s => s.replace(/\bto\s+/g, '').replace(/\s+/g, ' ').trim();
            for (const part of parts) {
                if (normAnswer === part) return true;
                if (stripTo(normAnswer) === stripTo(part)) return true;
            }

            // Exact match on any keyword (for particles especially)
            if (isParticle && keywords.includes(normAnswer)) return true;

            // Fuzzy match (configurable similarity threshold)
            for (const part of parts) {
                if (part.length >= 3) {
                    const dist = levenshtein(normAnswer, part);
                    const similarity = 1 - dist / Math.max(normAnswer.length, part.length);
                    if (similarity >= quizSettings.fuzzyThreshold) return true;
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
            if (tabId === 'conversation') loadConversationLessons();
        }

        function openSettings() {
            document.getElementById('settings-modal').classList.add('active');
            loadApiUsage(); // Refresh usage stats
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
            decay: 1,
            fuzzyThreshold: 0.8
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
                    document.getElementById('setting-fuzzy-threshold').value = quizSettings.fuzzyThreshold;

                    // API key status
                    const apiKeyInput = document.getElementById('api-key');
                    apiKeyInput.disabled = false;
                    if (config.hasApiKey) {
                        if (config.apiKeySource === 'config') {
                            apiKeyInput.placeholder = '••••••••••••••••••••• (saved in config)';
                        } else {
                            apiKeyInput.placeholder = '(set via CLAUDE_API_KEY env var)';
                        }
                    } else {
                        apiKeyInput.placeholder = 'sk-ant-...';
                    }
                    apiKeyInput.value = ''; // Never show the actual key
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
                                select.innerHTML += `<option value="${esc(tag)}">${esc(tag)}</option>`;
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
                decay: parseInt(document.getElementById('setting-decay').value) || 1,
                fuzzyThreshold: parseFloat(document.getElementById('setting-fuzzy-threshold').value) || 0.8
            };

            const payload = {quiz: quizSettings};

            // Only send API key if user entered something new
            const apiKeyInput = document.getElementById('api-key');
            if (apiKeyInput.value.trim()) {
                payload.claude_api_key = apiKeyInput.value.trim();
            }

            fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    closeSettings();
                }
            })
            .catch(err => console.error('Failed to save settings:', err));
        }

        function testApiKey() {
            const statusEl = document.getElementById('api-key-status');
            const apiKeyInput = document.getElementById('api-key');

            // If user entered a new key, save it first
            if (apiKeyInput.value.trim()) {
                statusEl.textContent = 'Saving and testing...';
                statusEl.style.color = '#666';

                fetch('/api/config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({claude_api_key: apiKeyInput.value.trim()})
                })
                .then(() => doTestApiKey())
                .catch(err => {
                    statusEl.textContent = 'Error saving key: ' + err.message;
                    statusEl.style.color = '#c00';
                });
            } else {
                doTestApiKey();
            }
        }

        function doTestApiKey() {
            const statusEl = document.getElementById('api-key-status');
            statusEl.textContent = 'Testing API key...';
            statusEl.style.color = '#666';

            fetch('/api/config/test_api_key', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        statusEl.textContent = '✓ ' + data.message;
                        statusEl.style.color = '#4CAF50';
                        loadSettings(); // Refresh status
                    } else {
                        statusEl.textContent = '✗ ' + data.error;
                        statusEl.style.color = '#c00';
                    }
                })
                .catch(err => {
                    statusEl.textContent = 'Error: ' + err.message;
                    statusEl.style.color = '#c00';
                });
        }

        function clearApiKey() {
            if (!confirm('Clear the saved API key? (Environment variable will still work if set)')) return;

            const statusEl = document.getElementById('api-key-status');
            fetch('/api/config/clear_api_key', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        statusEl.textContent = 'API key cleared from config';
                        statusEl.style.color = '#666';
                        loadSettings(); // Refresh status
                    }
                })
                .catch(err => {
                    statusEl.textContent = 'Error: ' + err.message;
                    statusEl.style.color = '#c00';
                });
        }

        function saveApiModel() {
            const model = document.getElementById('api-model').value;
            fetch('/api/config/model', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({model: model})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    loadApiUsage(); // Recalculate cost with new model
                }
            })
            .catch(err => console.error('Failed to save model:', err));
        }

        function loadApiUsage() {
            fetch('/api/config/usage')
                .then(r => r.json())
                .then(data => {
                    document.getElementById('usage-input-tokens').textContent = data.input_tokens.toLocaleString();
                    document.getElementById('usage-output-tokens').textContent = data.output_tokens.toLocaleString();
                    document.getElementById('usage-cost').textContent = '$' + data.cost.toFixed(4);
                    // Also set the model dropdown
                    const modelSelect = document.getElementById('api-model');
                    if (modelSelect && data.model) {
                        modelSelect.value = data.model;
                    }
                })
                .catch(err => console.error('Failed to load usage:', err));
        }

        function resetApiUsage() {
            if (!confirm('Reset the usage counter to zero?')) return;
            fetch('/api/config/usage/reset', {method: 'POST'})
                .then(r => r.json())
                .then(data => {
                    if (data.success) {
                        loadApiUsage();
                    }
                })
                .catch(err => console.error('Failed to reset usage:', err));
        }

        // Load settings on page load
        document.addEventListener('DOMContentLoaded', () => {
            loadSettings();
            loadTags();
            loadApiUsage();
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
                audioContainer.innerHTML = `<button class="audio-btn" onclick="playAudio('${esc(audio)}')">🔊 Play Audio</button>`;
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
                        html += `<button class="secondary" onclick="document.getElementById('edit-pinyin').value='${esc(data.dict)}'" style="padding: 3px 8px; font-size: 13px; margin-right: 5px;">dict: ${esc(data.dict)}</button>`;
                    }
                    if (data.pypinyin && data.pypinyin !== data.dict) {
                        html += `<button class="secondary" onclick="document.getElementById('edit-pinyin').value='${esc(data.pypinyin)}'" style="padding: 3px 8px; font-size: 13px;">pypinyin: ${esc(data.pypinyin)}</button>`;
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
        let lookupHistory = [];

        function doSearch(loadMore = false) {
            const query = document.getElementById('search-input').value;
            if (!loadMore) {
                // Push previous query to history (if different)
                if (lookupQuery && lookupQuery !== query) {
                    lookupHistory.push(lookupQuery);
                }
                updateLookupBackBtn();
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
                            const editParams = `${idx}, '${esc(v.characters || '')}', '${esc(escEnglish)}', '${esc(v.pinyin || '')}', ${hasPinyinOptions ? `'${esc(v.pinyin_dict)}', '${esc(v.pinyin_pypinyin)}'` : 'null, null'}, '${esc(v.audio || '')}', 'lookup', ${tagsJson}`;
                            vocabHtml += `<div class="vocab-item" onclick="openEditModal(${editParams})" style="cursor: pointer;">
                                <span class="vocab-english">${esc(v.english)}</span>
                                <span class="vocab-chars chinese">${makeCharsClickable(v.characters || '')}</span>
                                <span class="vocab-pinyin pinyin">${esc(v.pinyin || '')}</span>
                                ${v.audio ? `<button class="audio-btn" onclick="event.stopPropagation(); playAudio('${esc(v.audio)}')">🔊</button>` : ''}
                            </div>`;
                        });
                        document.getElementById('vocab-results').innerHTML = vocabHtml || '<p>(not in vocabulary)</p>';
                    }

                    let dictHtml = loadMore ? '' : '';
                    data.dict.forEach(d => {
                        let pinyinDisplay = esc(d.pinyin);
                        if (d.pinyin_pypinyin) {
                            pinyinDisplay = `${esc(d.pinyin)} <span style="color: #999; font-size: 12px;">(pypinyin: ${esc(d.pinyin_pypinyin)})</span>`;
                        }
                        dictHtml += `<div class="vocab-item">
                            <span class="vocab-chars chinese">${makeCharsClickable(d.simplified)}</span>
                            <span class="vocab-pinyin pinyin">${pinyinDisplay}</span>
                            <span>${d.definitions.slice(0, 3).map(x => esc(x)).join(', ')}</span>
                            <button class="audio-btn" onclick="event.stopPropagation(); previewAudio('${esc(d.simplified)}')" style="opacity: 0.6;">&#128266;</button>
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

        function lookupBack() {
            if (lookupHistory.length === 0) return;
            // If we came from the List tab, go straight back (skip intermediate lookups)
            if (lookupHistory.includes('__LIST__')) {
                const vocabSection = document.getElementById('section-vocabulary');
                if (vocabSection) {
                    vocabSection.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                    vocabSection.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                    document.getElementById('vocabulary-list').classList.add('active');
                    const tabBtn = vocabSection.querySelector('.tab[onclick*="list"]');
                    if (tabBtn) tabBtn.classList.add('active');
                }
                lookupHistory = [];
                updateLookupBackBtn();
                return;
            }
            const prev = lookupHistory.pop();
            document.getElementById('search-input').value = prev;
            lookupQuery = '';  // Reset so doSearch doesn't push current as history
            doSearch();
        }

        function updateLookupBackBtn() {
            const btn = document.getElementById('lookup-back-btn');
            if (btn) btn.style.display = lookupHistory.length > 0 ? 'inline-block' : 'none';
        }

        function lookupEditWord(index, english, pinyin, dictPinyin, pypinyinPinyin) {
            const englishSpan = document.getElementById(`lookup-english-${index}`);
            const pinyinSpan = document.getElementById(`lookup-pinyin-${index}`);
            const item = document.getElementById(`lookup-item-${index}`);

            // Replace English with input
            englishSpan.innerHTML = `<input type="text" id="lookup-edit-english-${index}" value="${esc(english)}" style="width: 150px;">`;

            // Replace pinyin with selector if options exist
            if (dictPinyin && pypinyinPinyin && dictPinyin !== pypinyinPinyin) {
                const isDict = pinyin === dictPinyin;
                pinyinSpan.innerHTML = `
                    <select id="lookup-edit-pinyin-${index}">
                        <option value="${esc(dictPinyin)}" ${isDict ? 'selected' : ''}>dict: ${esc(dictPinyin)}</option>
                        <option value="${esc(pypinyinPinyin)}" ${!isDict ? 'selected' : ''}>pypinyin: ${esc(pypinyinPinyin)}</option>
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
                                <label><input type="radio" name="pinyin_${idx}" value="dict" checked onchange="updatePinyin(${idx})"> dict: ${esc(m.pinyin)}</label>
                                <label style="margin-left: 10px;"><input type="radio" name="pinyin_${idx}" value="pypinyin" onchange="updatePinyin(${idx})"> pypinyin: ${esc(m.pinyin_pypinyin)}</label>
                            </div>`;
                        }
                        html += `<div class="match-item" onclick="selectMatch(${idx})">
                            <button class="audio-btn" onclick="event.stopPropagation(); previewAudio('${esc(m.simplified)}')" style="margin-right: 8px;">🔊</button>
                            <span class="chinese" style="font-size: 20px;">${esc(m.simplified)}</span>
                            <span class="pinyin">(${esc(m.pinyin)})</span>
                            - ${m.definitions.slice(0, 2).map(x => esc(x)).join(', ')}
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
                    let msg = `<p style="color: green;">${action}: ${esc(data.entry.english)} - ${esc(data.entry.characters)} (${esc(data.entry.pinyin)})</p>`;
                    if (data.pinyin_pypinyin && data.pinyin_dict) {
                        msg += `<p style="color: #666; font-size: 14px;">Note: pypinyin="${esc(data.pinyin_pypinyin)}" vs dictionary="${esc(data.pinyin_dict)}"</p>`;
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
                    let msg = `<p style="color: orange;"><strong>⚠ Already exists:</strong> ${esc(ex.english)} - ${esc(ex.characters)} (${esc(ex.pinyin || '')})</p>`;
                    msg += `<p style="margin-top: 10px;">
                        <button class="secondary" onclick="addWord(true, false)">Add Anyway</button>
                        <button class="secondary" onclick="addWord(false, true)" style="margin-left: 10px;">Update Existing</button>
                    </p>`;
                    document.getElementById('add-result').innerHTML = msg;
                } else {
                    document.getElementById('add-result').innerHTML =
                        `<p style="color: red;">Error: ${esc(data.error)}</p>`;
                }
            });
        }

        // LIST
        let listOffset = 0;

        // Calculate weight (duplicated here for list display - same as quiz)
        function calcWeightForList(stats) {
            const correct = Math.min(quizSettings.maxCount, stats?.correct || 0);
            const wrong = Math.min(quizSettings.maxCount, stats?.wrong || 0);
            const weight = 1 + quizSettings.wrongWeight * Math.log(1 + wrong) - quizSettings.correctWeight * Math.log(1 + correct);
            // New words (0 attempts) get a boost to ensure they're introduced
            const attempts = (stats?.correct || 0) + (stats?.wrong || 0);
            const newnessBoost = attempts === 0 ? 0.5 : 0;
            return Math.max(0.1, weight + newnessBoost);
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
                    data.vocab.forEach(v => {
                        const idx = v._index;  // Use original vocab index from backend
                        let pinyinDisplay = esc(v.pinyin || '');
                        // Store raw pinyin options for editing
                        const hasPinyinOptions = v.pinyin_pypinyin && v.pinyin_dict;
                        if (hasPinyinOptions) {
                            pinyinDisplay += ` <span style="color: #999; font-size: 11px;">(dict: ${esc(v.pinyin_dict)} | pypinyin: ${esc(v.pinyin_pypinyin)})</span>`;
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
                        const editParams = `${idx}, '${esc(v.characters || '')}', '${esc(escEnglish)}', '${esc(v.pinyin || '')}', ${hasPinyinOptions ? `'${esc(v.pinyin_dict)}', '${esc(v.pinyin_pypinyin)}'` : 'null, null'}, '${esc(v.audio || '')}', 'list', ${tagsJson}`;
                        const focusStar = v.focus ? '★' : '☆';
                        const focusStyle = v.focus ? 'color: #f0ad4e;' : 'color: #ccc;';
                        html += `<div class="vocab-item" id="vocab-item-${idx}" onclick="openEditModal(${editParams})" style="cursor: pointer;">
                            <span onclick="event.stopPropagation(); toggleFocus(${idx})" style="cursor: pointer; font-size: 18px; ${focusStyle}" title="Toggle focus">${focusStar}</span>
                            <span>${idx + 1}.</span>
                            <span class="vocab-english">${esc(v.english)}</span>
                            <span class="vocab-chars chinese">${makeCharsClickable(v.characters || '')}</span>
                            <span class="vocab-pinyin pinyin">${esc(v.pinyin || '')}</span>
                            ${statsDisplay}
                            ${v.audio ? `<button class="audio-btn" onclick="event.stopPropagation(); playAudio('${esc(v.audio)}')">🔊</button>` : ''}
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

        function generateToneAudio() {
            const force = document.getElementById('tone-audio-force').checked;
            const label = force ? 'Force regenerate ALL tone audio' : 'Generate missing tone audio';
            if (!confirm(`${label}?\n\nThis calls gTTS for each syllable+tone combination and may take a while.`)) return;

            const statusEl = document.getElementById('tone-audio-status');
            statusEl.textContent = 'Generating tone audio...';

            fetch('/api/generate_tone_audio', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({force})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    let msg = `Done: ${data.generated} generated, ${data.skipped} skipped`;
                    if (data.failed > 0) {
                        msg += `, ${data.failed} failed`;
                    }
                    statusEl.textContent = msg;
                    if (data.failures && data.failures.length > 0) {
                        const details = data.failures.map(f => `${f.syllable}${f.tone}: ${f.error}`).join('\n');
                        console.warn('Tone audio generation failures:\n' + details);
                        statusEl.textContent += ' (see console for details)';
                    }
                } else {
                    statusEl.textContent = 'Error: ' + (data.error || 'unknown');
                }
            })
            .catch(err => {
                statusEl.textContent = 'Error: ' + err.message;
            });
        }

        // ===== TONE AUDIO CURATION =====

        let curationSyllables = [];

        // Status indicator helper
        function statusIndicator(status) {
            if (status === 'accepted' || status === 'unflagged') return '<span class="curation-status curation-ok" title="OK">●</span>';
            if (status === 'flagged') return '<span class="curation-status curation-flagged" title="Flagged">⚠</span>';
            if (status === 'espeak') return '<span class="curation-status curation-espeak" title="espeak-ng">◇</span>';
            return '';
        }

        function flagBadgesHtml(flags) {
            const colors = {
                duplicate_char: '#f44336', cedict_mismatch: '#ff9800',
                polyphone: '#2196F3', cedict_missing: '#999'
            };
            const labels = {
                duplicate_char: 'DUP', cedict_mismatch: 'MISMATCH',
                polyphone: 'POLY', cedict_missing: 'MISSING'
            };
            return flags.map(f =>
                `<span style="font-size: 10px; padding: 1px 5px; border-radius: 8px; background: ${colors[f] || '#999'}; color: white;">${labels[f] || esc(f)}</span>`
            ).join(' ');
        }

        function loadCurationItems() {
            const filter = document.getElementById('curation-filter').value;
            const flagFilter = document.getElementById('curation-flag-filter').value;
            const includeReviewed = filter === 'all_flagged' || filter === 'accepted';

            const summaryEl = document.getElementById('curation-summary');
            summaryEl.textContent = 'Analysing...';

            fetch(`/api/tone_curation/analyse?include_reviewed=${includeReviewed}`)
                .then(r => r.json())
                .then(data => {
                    const summary = data.summary;
                    summaryEl.textContent = `${summary.total_flagged_tones} flagged tones · ${summary.reviewed} reviewed · ${summary.unreviewed} unreviewed · ${summary.total_syllables} syllables`;

                    let syllables = data.syllables || [];
                    // Client-side filtering
                    if (filter === 'accepted') {
                        syllables = syllables.filter(s => s.tones.some(t => t.status === 'accepted'));
                    }
                    if (flagFilter !== 'any') {
                        syllables = syllables.filter(s => s.tones.some(t => t.flags.includes(flagFilter)));
                    }

                    curationSyllables = syllables;
                    renderCurationList(syllables);
                })
                .catch(err => {
                    summaryEl.textContent = 'Error: ' + err.message;
                });
        }

        function renderCurationList(syllables) {
            const listEl = document.getElementById('curation-list');
            if (!syllables.length) {
                listEl.innerHTML = '<p style="padding: 15px; color: #666;">No items to review.</p>';
                return;
            }

            let html = '';
            syllables.forEach((syl, sIdx) => {
                html += `<div class="curation-syllable" id="curation-syl-${sIdx}">
                    <div class="curation-syllable-header"><strong>${esc(syl.syllable)}</strong></div>
                    <div class="curation-tones-row">`;

                syl.tones.forEach((t, tIdx) => {
                    const id = `${sIdx}-${tIdx}`;
                    const badges = t.flags.length ? `<div style="margin-top: 2px;">${flagBadgesHtml(t.flags)}</div>` : '';

                    // Action buttons
                    let actions = '';
                    if (t.status === 'accepted') {
                        actions = `<button class="curation-action-btn" onclick="event.stopPropagation(); curationAction('${esc(syl.syllable)}', ${t.tone}, 'reset')">Reset</button>`;
                    } else if (t.status === 'espeak') {
                        actions = `<button class="curation-action-btn" onclick="event.stopPropagation(); curationAction('${esc(syl.syllable)}', ${t.tone}, 'reset')">Reset</button>`;
                    } else {
                        actions = `<button class="curation-action-btn" onclick="event.stopPropagation(); curationAction('${esc(syl.syllable)}', ${t.tone}, 'accept')">Accept</button>`;
                        actions += `<button class="curation-action-btn" onclick="event.stopPropagation(); playEspeakPreview('${esc(syl.syllable)}', ${t.tone})" title="Preview espeak-ng">▶es</button>`;
                        actions += `<button class="curation-action-btn curation-espeak-btn" onclick="event.stopPropagation(); curationAction('${esc(syl.syllable)}', ${t.tone}, 'espeak')">Espeak</button>`;
                    }

                    // Alts toggle
                    const altsCount = (t.alternatives || []).length;
                    const altsToggle = altsCount > 0
                        ? `<button class="curation-action-btn" onclick="event.stopPropagation(); toggleCurationAlts('${id}')">Alts(${altsCount})</button>`
                        : '';

                    // Alternatives panel
                    let altsPanel = '';
                    if (altsCount > 0) {
                        altsPanel = `<div id="curation-alts-${id}" class="curation-alts-panel" style="display: none;">
                            ${t.alternatives.map(alt =>
                                `<div class="curation-alt-row">
                                    <button class="audio-btn" onclick="event.stopPropagation(); playCurationPreview('${esc(alt.char)}')" style="padding: 2px 6px; font-size: 11px;">▶</button>
                                    <span class="chinese" style="font-size: 16px;">${esc(alt.char)}</span>
                                    <span style="color: #666; font-size: 12px;">${esc(alt.definition)}</span>
                                    ${alt.polyphone ? '<span style="font-size: 10px; padding: 1px 4px; border-radius: 6px; background: #2196F3; color: white;">POLY</span>' : ''}
                                    <button class="curation-action-btn" style="margin-left: auto;" onclick="event.stopPropagation(); replaceCurationChar('${esc(syl.syllable)}', ${t.tone}, '${esc(alt.char)}')">Use</button>
                                </div>`
                            ).join('')}
                        </div>`;
                    }

                    html += `<div class="curation-tone-cell">
                        <div class="curation-tone-header">
                            <span style="font-size: 12px; color: #999;">T${t.tone}</span>
                            ${statusIndicator(t.status)}
                        </div>
                        <div style="display: flex; align-items: center; gap: 4px;">
                            <button class="audio-btn" onclick="event.stopPropagation(); playCurationAudio('${esc(syl.syllable)}', ${t.tone})" style="padding: 2px 6px; font-size: 11px;">▶</button>
                            <span class="chinese" style="font-size: 20px;">${esc(t.char)}</span>
                        </div>
                        ${badges}
                        <div class="curation-tone-actions">${altsToggle}${actions}</div>
                        ${altsPanel}
                    </div>`;
                });

                html += `</div></div>`;
            });

            listEl.innerHTML = html;
        }

        function toggleCurationAlts(id) {
            const el = document.getElementById(`curation-alts-${id}`);
            if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
        }

        function playCurationAudio(syllable, tone) {
            fetch(`/api/tone_audio?pinyin=${encodeURIComponent(syllable)}&tone=${tone}`)
                .then(r => r.blob())
                .then(blob => { new Audio(URL.createObjectURL(blob)).play(); })
                .catch(err => console.error('Curation audio failed:', err));
        }

        function playCurationPreview(char) {
            fetch(`/api/tone_audio_preview?char=${encodeURIComponent(char)}`)
                .then(r => r.blob())
                .then(blob => { new Audio(URL.createObjectURL(blob)).play(); })
                .catch(err => console.error('Preview audio failed:', err));
        }

        function playEspeakPreview(syllable, tone) {
            fetch(`/api/tone_audio_espeak_preview?pinyin=${encodeURIComponent(syllable)}&tone=${tone}`)
                .then(r => r.blob())
                .then(blob => { new Audio(URL.createObjectURL(blob)).play(); })
                .catch(err => console.error('Espeak preview failed:', err));
        }

        function curationAction(syllable, tone, action) {
            if (action === 'reset') {
                fetch('/api/tone_curation/reset', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({syllable, tone})
                })
                .then(r => r.json())
                .then(data => { if (data.success) loadCurationItems(); });
            } else {
                fetch('/api/tone_curation/update', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({syllable, tone, action})
                })
                .then(r => r.json())
                .then(data => { if (data.success) loadCurationItems(); });
            }
        }

        function replaceCurationChar(syllable, tone, newChar) {
            fetch('/api/tone_curation/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({syllable, tone, action: 'replace', new_char: newChar})
            })
            .then(r => r.json())
            .then(data => { if (data.success) loadCurationItems(); });
        }

        function editWord(index, english, pinyin, dictPinyin, pypinyinPinyin) {
            const englishSpan = document.getElementById(`english-${index}`);
            const pinyinSpan = document.getElementById(`pinyin-${index}`);
            const item = document.getElementById(`vocab-item-${index}`);

            // Replace English with input
            englishSpan.innerHTML = `<input type="text" id="edit-english-${index}" value="${esc(english)}" style="width: 150px;">`;

            // Replace pinyin with selector if options exist
            if (dictPinyin && pypinyinPinyin && dictPinyin !== pypinyinPinyin) {
                const isDict = pinyin === dictPinyin;
                pinyinSpan.innerHTML = `
                    <select id="edit-pinyin-${index}">
                        <option value="${esc(dictPinyin)}" ${isDict ? 'selected' : ''}>dict: ${esc(dictPinyin)}</option>
                        <option value="${esc(pypinyinPinyin)}" ${!isDict ? 'selected' : ''}>pypinyin: ${esc(pypinyinPinyin)}</option>
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
        // Clamps stats to maxCount so lowering the setting takes effect immediately
        function calcWeight(stats) {
            const correct = Math.min(quizSettings.maxCount, stats?.correct || 0);
            const wrong = Math.min(quizSettings.maxCount, stats?.wrong || 0);
            const weight = 1 + quizSettings.wrongWeight * Math.log(1 + wrong) - quizSettings.correctWeight * Math.log(1 + correct);
            // New words (0 attempts) get a boost to ensure they're introduced
            const attempts = (stats?.correct || 0) + (stats?.wrong || 0);
            const newnessBoost = attempts === 0 ? 0.5 : 0;
            return Math.max(0.1, weight + newnessBoost);  // Floor at 0.1
        }

        // Fisher-Yates shuffle for uniform random ordering
        function shuffle(array) {
            const arr = [...array];
            for (let i = arr.length - 1; i > 0; i--) {
                const j = Math.floor(Math.random() * (i + 1));
                [arr[i], arr[j]] = [arr[j], arr[i]];
            }
            return arr;
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
            clearQuizLookup();
            const tagFilter = document.getElementById('quiz-tag-filter').value;
            const tagParam = tagFilter ? '?tag=' + encodeURIComponent(tagFilter) : '';
            fetch('/api/list' + tagParam)
                .then(r => r.json())
                .then(data => {
                    if (data.vocab.length < 1) {
                        alert('Need at least 1 vocabulary entry');
                        return;
                    }

                    // Entries already have _index from backend (original vocab position)
                    let entriesWithIndex = data.vocab;

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
                        quizEntries = shuffle(entriesWithIndex);
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

            // Collapse lookup panel for fresh start
            document.getElementById('quiz-lookup-panel').classList.add('collapsed');

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
                prompt.innerHTML = makeCharsClickable(currentEntry.characters || '?');
                prompt.className = 'quiz-prompt chinese';
            } else if (showMode === 'pinyin') {
                prompt.innerHTML = '';
                const mainSpan = document.createElement('span');
                mainSpan.textContent = currentEntry.pinyin || '?';
                prompt.appendChild(mainSpan);
                if (currentEntry.alt_pinyin && currentEntry.alt_pinyin.length > 1) {
                    const altSpan = document.createElement('span');
                    altSpan.style.cssText = 'font-size: 0.5em; color: #999; display: block; margin-top: 4px;';
                    const others = currentEntry.alt_pinyin.filter(p => p !== currentEntry.pinyin);
                    if (others.length > 0) {
                        altSpan.textContent = `also: ${others.join(', ')}`;
                        prompt.appendChild(altSpan);
                    }
                }
                prompt.className = 'quiz-prompt pinyin';
            } else if (showMode === 'pinyin_characters') {
                prompt.innerHTML = '';
                const pinyinSpan = document.createElement('span');
                pinyinSpan.textContent = currentEntry.pinyin || '?';
                prompt.appendChild(pinyinSpan);
                const charSpan = document.createElement('span');
                charSpan.innerHTML = ` ${makeCharsClickable(currentEntry.characters || '')}`;
                charSpan.style.cssText = 'font-size: 0.6em; color: #999; margin-left: 8px;';
                prompt.appendChild(charSpan);
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
                <input type="text" id="quiz-edit-english" value="${esc(currentEnglish)}" style="width: 200px;">
                <button class="secondary" onclick="quizSaveEdit()" style="padding: 2px 8px; font-size: 12px;">Save</button>
                <button onclick="quizCancelEdit('${esc(currentEnglish.replace(/'/g, "\\'"))}')" style="padding: 2px 8px; font-size: 12px;">Cancel</button>
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

        function quizOverride(markCorrect) {
            if (!lastAnswerStats) return;
            // Prevent overriding to same state
            if (markCorrect === lastAnswerStats.wasCorrect) return;

            // Send override to backend - apply correct/wrong from original stats
            fetch('/api/update_stats', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    index: lastAnswerStats.index,
                    correct: markCorrect,
                    maxCount: quizSettings.maxCount,
                    decay: quizSettings.decay,
                    statType: lastAnswerStats.statType,
                    override: lastAnswerStats.originalStats  // Backend will use these as base
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    // Update score display
                    if (markCorrect) {
                        quizCorrect++;
                    } else {
                        quizCorrect--;
                    }
                    document.getElementById('quiz-score').textContent = 'Score: ' + quizCorrect + '/' + quizTotal;

                    // Update feedback display
                    const feedback = document.getElementById('quiz-feedback');
                    const newStatsStr = `[✓${data.newStats.correct} ✗${data.newStats.wrong} w:${calcWeight(data.newStats).toFixed(2)}]`;

                    if (markCorrect) {
                        feedback.className = 'quiz-feedback correct';
                        feedback.innerHTML = feedback.innerHTML
                            .replace('✗ Wrong.', '✓ Overridden to Correct!')
                            .replace(/\[.*?✓\d+ ✗\d+ w:[\d.]+\]/, newStatsStr)
                            .replace(/<button[^>]*>✓ Mark Correct<\/button>/, '<span style="color: #999; font-size: 12px;">(overridden)</span>');
                    } else {
                        feedback.className = 'quiz-feedback wrong';
                        feedback.innerHTML = feedback.innerHTML
                            .replace('✓ Correct!', '✗ Overridden to Wrong.')
                            .replace(/\[.*?✓\d+ ✗\d+ w:[\d.]+\]/, newStatsStr)
                            .replace(/<button[^>]*>✗ Mark Wrong<\/button>/, '<span style="color: #999; font-size: 12px;">(overridden)</span>');
                    }

                    lastAnswerStats.wasCorrect = markCorrect;  // Prevent double override
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
                // Also accept English from other entries with same pinyin or characters
                if (!correct) {
                    const showMode = document.getElementById('quiz-show').value;
                    if (showMode === 'pinyin') {
                        correct = quizAllEntries.some(e =>
                            e.pinyin === currentEntry.pinyin && matchEnglish(answer, e.english)
                        );
                    } else if (showMode === 'characters' || showMode === 'pinyin_characters') {
                        correct = quizAllEntries.some(e =>
                            e.characters === currentEntry.characters && matchEnglish(answer, e.english)
                        );
                    } else if (showMode === 'audio') {
                        correct = quizAllEntries.some(e =>
                            e.characters === currentEntry.characters && matchEnglish(answer, e.english)
                        );
                    }
                }
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
            let pinyinDisplay = esc(currentEntry.pinyin || '');
            if (currentEntry.pinyin_pypinyin && currentEntry.pinyin_dict) {
                pinyinDisplay = `${esc(currentEntry.pinyin)} <span style="color: #999; font-size: 14px;">(dict: ${esc(currentEntry.pinyin_dict)} | pypinyin: ${esc(currentEntry.pinyin_pypinyin)})</span>`;
            }
            // Find alternative meanings from other entries with same characters or pinyin
            const altMeanings = quizAllEntries
                .filter(e => e !== currentEntry && (
                    (e.characters && e.characters === currentEntry.characters) ||
                    (e.pinyin && e.pinyin === currentEntry.pinyin)
                ))
                .map(e => e.english);
            const altDisplay = altMeanings.length > 0
                ? ` <span style="color: #999; font-size: 14px;">(also: ${altMeanings.map(x => esc(x)).join('; ')})</span>`
                : '';

            const entryInfo = `<span class="chinese">${makeCharsClickable(currentEntry.characters || '')}</span> ` +
                `<span class="pinyin">(${pinyinDisplay})</span> - <span id="quiz-english-display">${esc(currentEntry.english)}</span>${altDisplay}`;

            // Determine which stats to use based on quiz mode
            const useCharStats = quizUsesCharacters();
            const currentStats = useCharStats ? currentEntry.char_stats : currentEntry.stats;

            // Save original stats for potential override
            lastAnswerStats = {
                index: currentEntry._index,
                originalStats: {correct: currentStats?.correct || 0, wrong: currentStats?.wrong || 0},
                statType: useCharStats ? 'char_stats' : 'stats',
                wasCorrect: correct
            };

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

            // Override button - to fix false positives/negatives (typos, fuzzy match errors)
            const overrideBtn = correct
                ? `<button class="danger" onclick="quizOverride(false)" style="padding: 2px 8px; font-size: 12px; margin-left: 10px;">✗ Mark Wrong</button>`
                : `<button class="secondary" onclick="quizOverride(true)" style="padding: 2px 8px; font-size: 12px; margin-left: 10px;">✓ Mark Correct</button>`;

            // Show audio button after answering (was hidden in English mode)
            if (currentAudio) {
                document.getElementById('quiz-play-audio').style.display = 'inline-block';
            }

            const yourAnswer = `<span style="font-size: 13px; color: ${correct ? '#666' : '#c00'};"> (you said: "${esc(answer)}")</span>`;
            if (correct) {
                quizCorrect++;
                feedback.innerHTML = '✓ Correct!' + yourAnswer + ' ' + entryInfo + statsInfo + overrideBtn + editBtns;
                feedback.className = 'quiz-feedback correct';
            } else {
                feedback.innerHTML = '✗ Wrong.' + yourAnswer + ' ' + entryInfo + statsInfo + overrideBtn + editBtns;
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

        // QUIZ LOOKUP PANEL
        let quizLookupQuery = '';
        let quizLookupDictOffset = 0;

        function toggleQuizLookup() {
            const panel = document.getElementById('quiz-lookup-panel');
            panel.classList.toggle('collapsed');
            if (!panel.classList.contains('collapsed')) {
                document.getElementById('quiz-lookup-input').focus();
            }
        }

        function doQuizLookup(loadMore = false) {
            const input = document.getElementById('quiz-lookup-input');
            const query = input.value.trim();
            if (!query) return;

            if (!loadMore) {
                quizLookupQuery = query;
                quizLookupDictOffset = 0;
            }

            fetch('/api/lookup?q=' + encodeURIComponent(quizLookupQuery) + '&offset=' + quizLookupDictOffset)
                .then(r => r.json())
                .then(data => {
                    const vocabSection = document.getElementById('quiz-lookup-vocab-section');
                    const dictSection = document.getElementById('quiz-lookup-dict-section');
                    const componentsSection = document.getElementById('quiz-lookup-components-section');
                    const emptyMsg = document.getElementById('quiz-lookup-empty');

                    if (!loadMore) {
                        // Render vocabulary results
                        let vocabHtml = '';
                        data.vocab.forEach(v => {
                            vocabHtml += `<div class="vocab-item">
                                <span class="vocab-english">${esc(v.english)}</span>
                                <span class="vocab-chars chinese">${makeCharsClickable(v.characters || '')}</span>
                                <span class="vocab-pinyin pinyin">${esc(v.pinyin || '')}</span>
                                ${v.audio
                                    ? `<button class="audio-btn" onclick="event.stopPropagation(); playAudio('${esc(v.audio)}')">&#128266;</button>`
                                    : (v.characters
                                        ? `<button class="audio-btn" onclick="event.stopPropagation(); previewAudio('${esc(v.characters)}')" style="opacity: 0.6;">&#128266;</button>`
                                        : '')}
                            </div>`;
                        });
                        vocabSection.style.display = data.vocab.length > 0 ? 'block' : 'none';
                        document.getElementById('quiz-lookup-vocab').innerHTML = vocabHtml;

                        // Auto-decompose: if query is multi-character Chinese, look up components
                        const chineseChars = quizLookupQuery.match(/[\u4e00-\u9fff]/g);
                        if (chineseChars && chineseChars.length > 1) {
                            decomposeComponents(chineseChars);
                        } else {
                            componentsSection.style.display = 'none';
                        }
                    }

                    // Render dictionary results
                    let dictHtml = '';
                    data.dict.forEach(d => {
                        dictHtml += `<div class="vocab-item">
                            <span class="vocab-chars chinese">${makeCharsClickable(d.simplified)}</span>
                            <span class="vocab-pinyin pinyin">${esc(d.pinyin)}</span>
                            <span>${d.definitions.slice(0, 3).map(x => esc(x)).join(', ')}</span>
                            <button class="audio-btn" onclick="event.stopPropagation(); previewAudio('${esc(d.simplified)}')" style="opacity: 0.6;">&#128266;</button>
                        </div>`;
                    });

                    const showing = data.dict_offset + data.dict.length;
                    let countHtml = data.dict_total > 0
                        ? `<p style="color: #666; font-size: 13px;">Showing ${showing} of ${data.dict_total}</p>`
                        : '';

                    if (data.dict_has_more) {
                        dictHtml += `<button class="secondary" onclick="loadMoreQuizLookup()" style="margin-top: 8px; padding: 5px 12px; font-size: 13px;">Load More</button>`;
                    }

                    if (loadMore) {
                        const container = document.getElementById('quiz-lookup-dict');
                        const oldBtn = container.querySelector('button.secondary');
                        if (oldBtn) oldBtn.remove();
                        container.insertAdjacentHTML('beforeend', dictHtml);
                        document.getElementById('quiz-lookup-dict-count').innerHTML = countHtml;
                    } else {
                        dictSection.style.display = data.dict.length > 0 ? 'block' : 'none';
                        document.getElementById('quiz-lookup-dict-count').innerHTML = countHtml;
                        document.getElementById('quiz-lookup-dict').innerHTML = dictHtml;
                    }

                    // Show empty message if no results at all
                    if (!loadMore && data.vocab.length === 0 && data.dict.length === 0) {
                        emptyMsg.style.display = 'block';
                    } else {
                        emptyMsg.style.display = 'none';
                    }
                });
        }

        function loadMoreQuizLookup() {
            quizLookupDictOffset += 10;
            doQuizLookup(true);
        }

        function decomposeComponents(chars) {
            const section = document.getElementById('quiz-lookup-components-section');
            const container = document.getElementById('quiz-lookup-components');
            container.innerHTML = '<p style="color: #999; font-size: 13px;">Loading...</p>';
            section.style.display = 'block';

            Promise.all(chars.map(ch =>
                fetch('/api/lookup?q=' + encodeURIComponent(ch))
                    .then(r => r.json())
                    .then(data => ({ char: ch, data }))
            )).then(results => {
                let html = '';
                results.forEach(({ char, data }) => {
                    // Prefer vocab entry, fall back to dictionary
                    const vocabMatch = data.vocab.find(v => v.characters === char);
                    const dictMatch = data.dict.find(d => d.simplified === char);

                    let pinyin = '', meaning = '', audioBtn = '';
                    if (vocabMatch) {
                        pinyin = esc(vocabMatch.pinyin || '');
                        meaning = esc(vocabMatch.english);
                        audioBtn = vocabMatch.audio
                            ? `<button class="audio-btn" onclick="event.stopPropagation(); playAudio('${esc(vocabMatch.audio)}')">&#128266;</button>`
                            : `<button class="audio-btn" onclick="event.stopPropagation(); previewAudio('${esc(char)}')" style="opacity: 0.6;">&#128266;</button>`;
                    } else if (dictMatch) {
                        pinyin = esc(dictMatch.pinyin);
                        meaning = dictMatch.definitions.slice(0, 3).map(x => esc(x)).join(', ');
                        audioBtn = `<button class="audio-btn" onclick="event.stopPropagation(); previewAudio('${esc(char)}')" style="opacity: 0.6;">&#128266;</button>`;
                    } else {
                        meaning = '(not found)';
                    }

                    html += `<div class="vocab-item">
                        <span class="vocab-chars chinese">${makeCharsClickable(char)}</span>
                        <span class="vocab-pinyin pinyin">${pinyin}</span>
                        <span>${meaning}</span>
                        ${audioBtn}
                    </div>`;
                });
                container.innerHTML = html;
            });
        }

        // Clickable characters utility
        function makeCharsClickable(text) {
            if (!text) return '';
            // Escape non-CJK characters, then make CJK characters clickable
            return esc(text).replace(/[\u4e00-\u9fff]/g,
                char => `<span class="clickable-char" onclick="event.stopPropagation(); charLookup('${char}')">${char}</span>`);
        }

        function charLookup(char) {
            // Context-aware: quiz tab uses quiz lookup panel, vocab tab uses vocab search
            const learnSection = document.getElementById('section-learn');
            if (learnSection && learnSection.classList.contains('active')) {
                // On learn section: use quiz lookup panel
                const panel = document.getElementById('quiz-lookup-panel');
                if (panel.classList.contains('collapsed')) {
                    panel.classList.remove('collapsed');
                }
                document.getElementById('quiz-lookup-input').value = char;
                doQuizLookup();
            } else {
                // On vocab/other section: use vocab search, switch to Lookup tab
                const vocabSection = document.getElementById('section-vocabulary');
                if (vocabSection) {
                    const lookupTab = document.getElementById('vocabulary-lookup');
                    if (lookupTab && !lookupTab.classList.contains('active')) {
                        // Coming from List (or other) tab — push sentinel for back navigation
                        lookupHistory = ['__LIST__'];
                        vocabSection.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                        vocabSection.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
                        lookupTab.classList.add('active');
                        const tabBtn = vocabSection.querySelector('.tab[onclick*="lookup"]');
                        if (tabBtn) tabBtn.classList.add('active');
                    }
                }
                document.getElementById('search-input').value = char;
                doSearch();
            }
        }

        // Keyboard handler for quiz lookup input
        document.getElementById('quiz-lookup-input').addEventListener('keydown', e => {
            e.stopPropagation();
            if (e.key === 'Enter') {
                doQuizLookup();
            }
        });

        function clearQuizLookup() {
            document.getElementById('quiz-lookup-vocab').innerHTML = '';
            document.getElementById('quiz-lookup-dict').innerHTML = '';
            document.getElementById('quiz-lookup-components').innerHTML = '';
            document.getElementById('quiz-lookup-vocab-section').style.display = 'none';
            document.getElementById('quiz-lookup-dict-section').style.display = 'none';
            document.getElementById('quiz-lookup-components-section').style.display = 'none';
            document.getElementById('quiz-lookup-empty').style.display = 'none';
            document.getElementById('quiz-lookup-input').value = '';
        }

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

        // ===== PINYIN CHART =====

        // Valid pinyin syllables organized by initial
        const pinyinData = {
            '': {
                name: 'Standalone vowels',
                group: 'none',
                syllables: ['a', 'o', 'e', 'ai', 'ei', 'ao', 'ou', 'an', 'en', 'ang', 'eng', 'er']
            },
            'b': { name: 'b', group: 'labial', syllables: ['ba', 'bo', 'bai', 'bei', 'bao', 'ban', 'ben', 'bang', 'beng', 'bi', 'bie', 'biao', 'bian', 'bin', 'bing', 'bu'] },
            'p': { name: 'p', group: 'labial', syllables: ['pa', 'po', 'pai', 'pei', 'pao', 'pou', 'pan', 'pen', 'pang', 'peng', 'pi', 'pie', 'piao', 'pian', 'pin', 'ping', 'pu'] },
            'm': { name: 'm', group: 'labial', syllables: ['ma', 'mo', 'me', 'mai', 'mei', 'mao', 'mou', 'man', 'men', 'mang', 'meng', 'mi', 'mie', 'miao', 'miu', 'mian', 'min', 'ming', 'mu'] },
            'f': { name: 'f', group: 'labial', syllables: ['fa', 'fo', 'fei', 'fou', 'fan', 'fen', 'fang', 'feng', 'fu'] },
            'd': { name: 'd', group: 'alveolar', syllables: ['da', 'de', 'dai', 'dei', 'dao', 'dou', 'dan', 'den', 'dang', 'deng', 'dong', 'di', 'die', 'diao', 'diu', 'dian', 'ding', 'du', 'duo', 'dui', 'duan', 'dun'] },
            't': { name: 't', group: 'alveolar', syllables: ['ta', 'te', 'tai', 'tei', 'tao', 'tou', 'tan', 'tang', 'teng', 'tong', 'ti', 'tie', 'tiao', 'tian', 'ting', 'tu', 'tuo', 'tui', 'tuan', 'tun'] },
            'n': { name: 'n', group: 'alveolar', syllables: ['na', 'ne', 'nai', 'nei', 'nao', 'nou', 'nan', 'nen', 'nang', 'neng', 'nong', 'ni', 'nie', 'niao', 'niu', 'nian', 'nin', 'niang', 'ning', 'nu', 'nuo', 'nuan', 'nü', 'nüe'] },
            'l': { name: 'l', group: 'alveolar', syllables: ['la', 'le', 'lai', 'lei', 'lao', 'lou', 'lan', 'lang', 'leng', 'long', 'li', 'lia', 'lie', 'liao', 'liu', 'lian', 'lin', 'liang', 'ling', 'lu', 'luo', 'luan', 'lun', 'lü', 'lüe'] },
            'g': { name: 'g', group: 'velar', syllables: ['ga', 'ge', 'gai', 'gei', 'gao', 'gou', 'gan', 'gen', 'gang', 'geng', 'gong', 'gu', 'gua', 'guo', 'guai', 'gui', 'guan', 'gun', 'guang'] },
            'k': { name: 'k', group: 'velar', syllables: ['ka', 'ke', 'kai', 'kei', 'kao', 'kou', 'kan', 'ken', 'kang', 'keng', 'kong', 'ku', 'kua', 'kuo', 'kuai', 'kui', 'kuan', 'kun', 'kuang'] },
            'h': { name: 'h', group: 'velar', syllables: ['ha', 'he', 'hai', 'hei', 'hao', 'hou', 'han', 'hen', 'hang', 'heng', 'hong', 'hu', 'hua', 'huo', 'huai', 'hui', 'huan', 'hun', 'huang'] },
            'j': { name: 'j', group: 'palatal', syllables: ['ji', 'jia', 'jie', 'jiao', 'jiu', 'jian', 'jin', 'jiang', 'jing', 'jiong', 'ju', 'jue', 'juan', 'jun'] },
            'q': { name: 'q', group: 'palatal', syllables: ['qi', 'qia', 'qie', 'qiao', 'qiu', 'qian', 'qin', 'qiang', 'qing', 'qiong', 'qu', 'que', 'quan', 'qun'] },
            'x': { name: 'x', group: 'palatal', syllables: ['xi', 'xia', 'xie', 'xiao', 'xiu', 'xian', 'xin', 'xiang', 'xing', 'xiong', 'xu', 'xue', 'xuan', 'xun'] },
            'zh': { name: 'zh', group: 'retroflex', syllables: ['zha', 'zhe', 'zhi', 'zhai', 'zhei', 'zhao', 'zhou', 'zhan', 'zhen', 'zhang', 'zheng', 'zhong', 'zhu', 'zhua', 'zhuo', 'zhuai', 'zhui', 'zhuan', 'zhun', 'zhuang'] },
            'ch': { name: 'ch', group: 'retroflex', syllables: ['cha', 'che', 'chi', 'chai', 'chao', 'chou', 'chan', 'chen', 'chang', 'cheng', 'chong', 'chu', 'chua', 'chuo', 'chuai', 'chui', 'chuan', 'chun', 'chuang'] },
            'sh': { name: 'sh', group: 'retroflex', syllables: ['sha', 'she', 'shi', 'shai', 'shei', 'shao', 'shou', 'shan', 'shen', 'shang', 'sheng', 'shu', 'shua', 'shuo', 'shuai', 'shui', 'shuan', 'shun', 'shuang'] },
            'r': { name: 'r', group: 'retroflex', syllables: ['re', 'ri', 'rao', 'rou', 'ran', 'ren', 'rang', 'reng', 'rong', 'ru', 'ruo', 'rui', 'ruan', 'run'] },
            'z': { name: 'z', group: 'dental', syllables: ['za', 'ze', 'zi', 'zai', 'zei', 'zao', 'zou', 'zan', 'zen', 'zang', 'zeng', 'zong', 'zu', 'zuo', 'zui', 'zuan', 'zun'] },
            'c': { name: 'c', group: 'dental', syllables: ['ca', 'ce', 'ci', 'cai', 'cao', 'cou', 'can', 'cen', 'cang', 'ceng', 'cong', 'cu', 'cuo', 'cui', 'cuan', 'cun'] },
            's': { name: 's', group: 'dental', syllables: ['sa', 'se', 'si', 'sai', 'sao', 'sou', 'san', 'sen', 'sang', 'seng', 'song', 'su', 'suo', 'sui', 'suan', 'sun'] },
            'y': { name: 'y', group: 'semivowel', syllables: ['ya', 'yo', 'ye', 'yai', 'yao', 'you', 'yan', 'yin', 'yang', 'ying', 'yong', 'yi', 'yu', 'yue', 'yuan', 'yun'] },
            'w': { name: 'w', group: 'semivowel', syllables: ['wa', 'wo', 'wai', 'wei', 'wan', 'wen', 'wang', 'weng', 'wu'] }
        };

        // Tone marks for each vowel
        const toneMarks = {
            'a': ['ā', 'á', 'ǎ', 'à'],
            'e': ['ē', 'é', 'ě', 'è'],
            'i': ['ī', 'í', 'ǐ', 'ì'],
            'o': ['ō', 'ó', 'ǒ', 'ò'],
            'u': ['ū', 'ú', 'ǔ', 'ù'],
            'ü': ['ǖ', 'ǘ', 'ǚ', 'ǜ']
        };

        // Add tone mark to pinyin syllable
        function addToneMark(syllable, tone) {
            if (tone < 1 || tone > 4) return syllable;

            // Find vowel to mark (rules: a/e first, then ou marks o, else last vowel)
            let vowelIdx = -1;
            let vowelChar = '';

            for (let i = 0; i < syllable.length; i++) {
                const c = syllable[i];
                if (c === 'a' || c === 'e') {
                    vowelIdx = i;
                    vowelChar = c;
                    break;
                }
                if (c === 'o' && syllable[i + 1] === 'u') {
                    vowelIdx = i;
                    vowelChar = 'o';
                    break;
                }
                if ('iouü'.includes(c)) {
                    vowelIdx = i;
                    vowelChar = c;
                }
            }

            if (vowelIdx === -1) return syllable;

            const marked = toneMarks[vowelChar][tone - 1];
            return syllable.slice(0, vowelIdx) + marked + syllable.slice(vowelIdx + 1);
        }

        let currentPinyinFilter = 'all';
        let expandedCell = null;

        function filterPinyinChart() {
            currentPinyinFilter = document.getElementById('tones-initial-filter').value;
            renderPinyinChart();
        }

        function renderPinyinChart() {
            const container = document.getElementById('pinyin-chart');
            container.innerHTML = '';

            const initials = Object.keys(pinyinData);

            for (const initial of initials) {
                const data = pinyinData[initial];

                // Apply filter
                if (currentPinyinFilter !== 'all' && data.group !== currentPinyinFilter) {
                    continue;
                }

                // Add header for this initial group
                const header = document.createElement('div');
                header.className = 'pinyin-initial-header';
                header.textContent = initial ? initial.toUpperCase() + ' -' : 'Standalone Vowels';
                container.appendChild(header);

                // Add syllable cells
                for (const syllable of data.syllables) {
                    const cell = document.createElement('div');
                    cell.className = 'pinyin-cell';
                    cell.dataset.syllable = syllable;

                    const syllableSpan = document.createElement('div');
                    syllableSpan.className = 'pinyin-syllable';
                    syllableSpan.textContent = syllable;
                    cell.appendChild(syllableSpan);

                    // Tone buttons (hidden until expanded)
                    const tonesDiv = document.createElement('div');
                    tonesDiv.className = 'pinyin-tones';
                    for (let t = 1; t <= 4; t++) {
                        const btn = document.createElement('button');
                        btn.className = 'tone-btn';
                        btn.textContent = t;
                        btn.title = addToneMark(syllable, t);
                        btn.onclick = (e) => {
                            e.stopPropagation();
                            playPinyinTone(syllable, t, btn);
                        };
                        tonesDiv.appendChild(btn);
                    }
                    cell.appendChild(tonesDiv);

                    cell.onclick = () => togglePinyinCell(cell);
                    container.appendChild(cell);
                }
            }
        }

        function togglePinyinCell(cell) {
            if (expandedCell && expandedCell !== cell) {
                expandedCell.classList.remove('expanded');
            }
            cell.classList.toggle('expanded');
            expandedCell = cell.classList.contains('expanded') ? cell : null;
        }

        function playPinyinTone(syllable, tone, btn) {
            // Create toned pinyin for display
            const tonedPinyin = addToneMark(syllable, tone);

            // Mark button as playing
            btn.classList.add('playing');

            // Use the tone audio API
            fetch('/api/tone_audio?pinyin=' + encodeURIComponent(syllable) + '&tone=' + tone)
                .then(r => r.blob())
                .then(blob => {
                    const url = URL.createObjectURL(blob);
                    const audio = new Audio(url);
                    audio.onended = () => btn.classList.remove('playing');
                    audio.onerror = () => btn.classList.remove('playing');
                    audio.play();
                })
                .catch(err => {
                    console.error('Tone audio failed:', err);
                    btn.classList.remove('playing');
                });
        }

        // Initialize chart when Tones tab is shown
        document.addEventListener('DOMContentLoaded', () => {
            // Render chart on first tab switch
            const tonesTab = document.querySelector('[onclick*="showSubTab(\'learn\', \'tones\')"]');
            if (tonesTab) {
                tonesTab.addEventListener('click', () => {
                    if (!document.getElementById('pinyin-chart').children.length) {
                        renderPinyinChart();
                    }
                });
            }
        });

        // ===== TONE PRACTICE =====

        let tonePracticeState = {
            current: null,      // Current question data
            index: 0,           // Current question index
            total: 0,           // Total questions
            correct: 0,         // Correct answers
            wrong: 0,           // Wrong answers
            answered: false     // Whether current question is answered
        };

        function showTonesSubTab(tabId) {
            // Update sub-tab buttons
            const container = document.getElementById('learn-tones');
            container.querySelectorAll('.sub-tabs .tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');

            // Show sub-tab content
            container.querySelectorAll('.tones-subtab').forEach(t => t.classList.remove('active'));
            document.getElementById('tones-' + tabId).classList.add('active');

            // Initialize chart if needed
            if (tabId === 'chart' && !document.getElementById('pinyin-chart').children.length) {
                renderPinyinChart();
            }
        }

        function startTonePractice() {
            const count = parseInt(document.getElementById('tone-practice-count').value);

            // Reset state
            tonePracticeState = {
                current: null,
                index: 0,
                total: count || 999,  // 0 = unlimited
                correct: 0,
                wrong: 0,
                answered: false
            };

            // Show practice area, hide completion
            document.getElementById('tone-practice-area').style.display = 'block';
            document.getElementById('tone-practice-complete').style.display = 'none';

            // Load first question
            loadTonePracticeQuestion();
        }

        function loadTonePracticeQuestion() {
            const mode = document.getElementById('tone-practice-mode').value;
            const initial = document.getElementById('tone-practice-initial').value;
            const tones = document.getElementById('tone-practice-tones').value;

            const params = new URLSearchParams({
                mode: mode,
                initial: initial,
                tones: tones,
                weighted: 'true'
            });

            fetch('/api/tone_practice/question?' + params)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        alert('Error: ' + data.error);
                        return;
                    }

                    tonePracticeState.current = data;
                    tonePracticeState.answered = false;
                    tonePracticeState.index++;

                    renderTonePracticeQuestion(data);
                })
                .catch(err => console.error('Failed to load question:', err));
        }

        function renderTonePracticeQuestion(data) {
            // Update hint based on what's revealed
            const hintEl = document.getElementById('tone-practice-hint');
            const questionEl = document.getElementById('tone-practice-question');

            let hintHtml = '';
            if (data.reveal.syllable) {
                hintHtml = `<span class="pinyin">${esc(data.reveal.syllable)}</span>`;
            } else if (data.reveal.tone !== undefined) {
                const toneMarker = ['‾', '/', 'ˇ', '\\'][data.reveal.tone - 1] || '';
                hintHtml = `<span class="tone-number">Tone ${data.reveal.tone}</span>`;
                if (data.reveal.final) {
                    hintHtml += ` <span class="final-hint">-${esc(data.reveal.final)}</span>`;
                }
            } else if (data.ask === 'full') {
                hintHtml = '🔊';
            }
            hintEl.innerHTML = hintHtml || '🔊';

            // Update question text
            if (data.ask === 'tone') {
                questionEl.textContent = 'Which tone did you hear?';
            } else if (data.ask === 'syllable') {
                questionEl.textContent = 'Which syllable did you hear?';
            } else if (data.ask === 'initial') {
                questionEl.textContent = 'Which initial consonant did you hear?';
            } else if (data.ask === 'full') {
                questionEl.textContent = 'Type what you heard (e.g., ma3):';
            }

            // Render options
            const optionsEl = document.getElementById('tone-practice-options');
            optionsEl.innerHTML = '';

            if (data.ask === 'full') {
                // Text input for full recognition
                optionsEl.innerHTML = `
                    <div class="tone-practice-input">
                        <input type="text" id="tone-practice-text-input" placeholder="e.g., ma3" autocomplete="off">
                        <button onclick="submitTonePracticeText()">Submit</button>
                    </div>`;
                // Focus and add enter key listener
                setTimeout(() => {
                    const input = document.getElementById('tone-practice-text-input');
                    if (input) {
                        input.focus();
                        input.onkeypress = (e) => {
                            if (e.key === 'Enter') submitTonePracticeText();
                        };
                    }
                }, 100);
            } else if (data.ask === 'tone') {
                // Tone buttons
                for (const opt of data.options) {
                    const btn = document.createElement('button');
                    btn.className = 'tone-option-btn';
                    btn.innerHTML = `<span class="tone-num">${esc(opt)}</span><span class="tone-mark">${['‾', '/', 'ˇ', '\\'][opt - 1] || ''}</span>`;
                    btn.onclick = () => checkTonePracticeAnswer(opt);
                    optionsEl.appendChild(btn);
                }
            } else {
                // Syllable or initial buttons
                for (const opt of data.options) {
                    const btn = document.createElement('button');
                    btn.className = 'tone-option-btn syllable-btn';
                    btn.textContent = opt || '(none)';
                    btn.onclick = () => checkTonePracticeAnswer(opt);
                    optionsEl.appendChild(btn);
                }
            }

            // Clear feedback
            const feedbackEl = document.getElementById('tone-practice-feedback');
            feedbackEl.textContent = '';
            feedbackEl.className = 'tone-practice-feedback';

            // Hide controls and curate panel until answered
            document.getElementById('tone-practice-controls').style.display = 'none';
            document.getElementById('tone-curate-panel').style.display = 'none';

            // Update score
            updateTonePracticeScore();

            // Auto-play audio
            playTonePracticeAudio();
        }

        function playTonePracticeAudio() {
            if (!tonePracticeState.current) return;

            const { syllable, tone } = tonePracticeState.current;
            fetch(`/api/tone_audio?pinyin=${encodeURIComponent(syllable)}&tone=${tone}`)
                .then(r => {
                    const source = r.headers.get('X-Audio-Source');
                    const playBtn = document.getElementById('tone-practice-play');
                    if (playBtn) {
                        playBtn.title = source === 'espeak-ng' ? 'Synthetic audio (espeak-ng fallback)' : 'Natural audio (gTTS)';
                        playBtn.classList.toggle('audio-fallback', source === 'espeak-ng');
                    }
                    return r.blob();
                })
                .then(blob => {
                    const url = URL.createObjectURL(blob);
                    new Audio(url).play();
                })
                .catch(err => console.error('Audio playback failed:', err));
        }

        function submitTonePracticeText() {
            const input = document.getElementById('tone-practice-text-input');
            if (input && input.value.trim()) {
                checkTonePracticeAnswer(input.value.trim());
            }
        }

        function checkTonePracticeAnswer(answer) {
            if (tonePracticeState.answered || !tonePracticeState.current) return;
            tonePracticeState.answered = true;

            const data = tonePracticeState.current;

            fetch('/api/tone_practice/answer', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    syllable: data.syllable,
                    tone: data.tone,
                    answer: answer,
                    ask: data.ask
                })
            })
            .then(r => r.json())
            .then(result => {
                const feedbackEl = document.getElementById('tone-practice-feedback');
                const optionsEl = document.getElementById('tone-practice-options');

                if (result.correct) {
                    tonePracticeState.correct++;
                    feedbackEl.textContent = '✓ Correct!';
                    feedbackEl.className = 'tone-practice-feedback correct';
                } else {
                    tonePracticeState.wrong++;
                    const tonedPinyin = addToneMark(data.syllable, data.tone);
                    feedbackEl.innerHTML = `✗ Wrong. The answer was: <strong>${esc(tonedPinyin)}</strong> (${esc(data.syllable)}${data.tone})`;
                    feedbackEl.className = 'tone-practice-feedback wrong';
                }

                // Mark correct/wrong on buttons
                if (data.ask !== 'full') {
                    optionsEl.querySelectorAll('.tone-option-btn').forEach(btn => {
                        const btnValue = data.ask === 'tone'
                            ? parseInt(btn.querySelector('.tone-num')?.textContent || btn.textContent)
                            : btn.textContent === '(none)' ? '' : btn.textContent;

                        if (btnValue === result.correctAnswer || btnValue === String(result.correctAnswer)) {
                            btn.classList.add('correct');
                        } else if (btnValue === answer || btnValue === String(answer)) {
                            btn.classList.add('wrong');
                        }
                    });
                }

                // Show controls
                document.getElementById('tone-practice-controls').style.display = 'flex';

                // Update score
                updateTonePracticeScore();
            })
            .catch(err => console.error('Failed to submit answer:', err));
        }

        function updateTonePracticeScore() {
            const total = tonePracticeState.correct + tonePracticeState.wrong;
            const scoreEl = document.getElementById('tone-practice-score');
            if (tonePracticeState.total > 0 && tonePracticeState.total < 999) {
                scoreEl.textContent = `Question ${tonePracticeState.index}/${tonePracticeState.total} · Score: ${tonePracticeState.correct}/${total}`;
            } else {
                scoreEl.textContent = `Question ${tonePracticeState.index} · Score: ${tonePracticeState.correct}/${total}`;
            }
        }

        function nextTonePractice() {
            // Check if practice is complete
            if (tonePracticeState.total > 0 &&
                tonePracticeState.total < 999 &&
                tonePracticeState.index >= tonePracticeState.total) {
                showTonePracticeComplete();
                return;
            }

            loadTonePracticeQuestion();
        }

        function showTonePracticeComplete() {
            document.getElementById('tone-practice-area').style.display = 'none';
            document.getElementById('tone-practice-complete').style.display = 'block';

            const summaryEl = document.getElementById('tone-practice-summary');
            const total = tonePracticeState.correct + tonePracticeState.wrong;
            const percentage = total > 0 ? Math.round((tonePracticeState.correct / total) * 100) : 0;

            summaryEl.innerHTML = `
                <p>You got <span class="stat-correct">${tonePracticeState.correct}</span> correct and
                <span class="stat-wrong">${tonePracticeState.wrong}</span> wrong.</p>
                <p>Accuracy: <strong>${percentage}%</strong></p>
            `;
        }

        function showToneReference() {
            if (!tonePracticeState.current) return;

            const syllable = tonePracticeState.current.syllable;
            const feedbackEl = document.getElementById('tone-practice-feedback');

            // Add reference buttons below feedback
            let refHtml = feedbackEl.innerHTML;
            refHtml += `
                <div class="tone-reference">
                    <span style="color: #666; font-size: 14px; margin-right: 10px;">Compare:</span>
            `;

            for (let t = 1; t <= 4; t++) {
                const isCorrect = t === tonePracticeState.current.tone;
                const highlight = isCorrect ? ' highlight' : '';
                refHtml += `<button class="tone-reference-btn${highlight}" onclick="playToneReferenceAudio('${esc(syllable)}', ${t})">${esc(addToneMark(syllable, t))}</button>`;
            }
            refHtml += '</div>';

            feedbackEl.innerHTML = refHtml;
        }

        function playToneReferenceAudio(syllable, tone) {
            fetch(`/api/tone_audio?pinyin=${encodeURIComponent(syllable)}&tone=${tone}`)
                .then(r => r.blob())
                .then(blob => {
                    const url = URL.createObjectURL(blob);
                    new Audio(url).play();
                })
                .catch(err => console.error('Reference audio failed:', err));
        }

        // ===== TONE PRACTICE CURATE PANEL =====

        function showToneCurate() {
            if (!tonePracticeState.current) return;

            const syllable = tonePracticeState.current.syllable;
            const panelEl = document.getElementById('tone-curate-panel');

            // Toggle off if already showing for same syllable
            if (panelEl.style.display === 'block' && panelEl.dataset.syllable === syllable) {
                panelEl.style.display = 'none';
                return;
            }

            panelEl.dataset.syllable = syllable;
            panelEl.innerHTML = '<p style="color: #666; font-size: 13px;">Loading...</p>';
            panelEl.style.display = 'block';

            loadToneCuratePanel(syllable);
        }

        function loadToneCuratePanel(syllable) {
            fetch(`/api/tone_curation/status?syllable=${encodeURIComponent(syllable)}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('tone-curate-panel').innerHTML = `<p style="color: #c00;">${esc(data.error)}</p>`;
                        return;
                    }
                    renderToneCuratePanel(data);
                })
                .catch(err => {
                    document.getElementById('tone-curate-panel').innerHTML = `<p style="color: #c00;">Error: ${esc(err.message)}</p>`;
                });
        }

        function renderToneCuratePanel(data) {
            const panelEl = document.getElementById('tone-curate-panel');
            const currentTone = tonePracticeState.current?.tone;

            let html = `<div class="curate-panel-header">Curate: <strong>${esc(data.syllable)}</strong></div>`;
            html += '<div class="curate-panel-tones">';

            data.tones.forEach((t, idx) => {
                const isCurrent = t.tone === currentTone;
                const highlight = isCurrent ? ' curate-tone-current' : '';

                // Action buttons
                let actions = '';
                if (t.status === 'accepted' || t.status === 'espeak') {
                    actions = `<button class="curation-action-btn" onclick="event.stopPropagation(); toneCurateAction('${esc(data.syllable)}', ${t.tone}, 'reset')">Reset</button>`;
                } else {
                    actions = `<button class="curation-action-btn" onclick="event.stopPropagation(); toneCurateAction('${esc(data.syllable)}', ${t.tone}, 'accept')">Accept</button>`;
                    actions += `<button class="curation-action-btn" onclick="event.stopPropagation(); playEspeakPreview('${esc(data.syllable)}', ${t.tone})" title="Preview espeak-ng">▶es</button>`;
                    actions += `<button class="curation-action-btn curation-espeak-btn" onclick="event.stopPropagation(); toneCurateAction('${esc(data.syllable)}', ${t.tone}, 'espeak')">Espeak</button>`;
                }

                const altsCount = (t.alternatives || []).length;
                const altsToggle = altsCount > 0
                    ? `<button class="curation-action-btn" onclick="event.stopPropagation(); toggleCurationAlts('tc-${idx}')">Alts(${altsCount})</button>`
                    : '';

                let altsPanel = '';
                if (altsCount > 0) {
                    altsPanel = `<div id="curation-alts-tc-${idx}" class="curation-alts-panel" style="display: none;">
                        ${t.alternatives.map(alt =>
                            `<div class="curation-alt-row">
                                <button class="audio-btn" onclick="event.stopPropagation(); playCurationPreview('${esc(alt.char)}')" style="padding: 2px 6px; font-size: 11px;">▶</button>
                                <span class="chinese" style="font-size: 16px;">${esc(alt.char)}</span>
                                <span style="color: #666; font-size: 12px;">${esc(alt.definition)}</span>
                                ${alt.polyphone ? '<span style="font-size: 10px; padding: 1px 4px; border-radius: 6px; background: #2196F3; color: white;">POLY</span>' : ''}
                                <button class="curation-action-btn" style="margin-left: auto;" onclick="event.stopPropagation(); toneCurateReplace('${esc(data.syllable)}', ${t.tone}, '${esc(alt.char)}')">Use</button>
                            </div>`
                        ).join('')}
                    </div>`;
                }

                const badges = t.flags.length ? `<div style="margin-top: 2px;">${flagBadgesHtml(t.flags)}</div>` : '';

                html += `<div class="curation-tone-cell${highlight}">
                    <div class="curation-tone-header">
                        <span style="font-size: 12px; color: #999;">T${t.tone}</span>
                        ${statusIndicator(t.status)}
                    </div>
                    <div style="display: flex; align-items: center; gap: 4px;">
                        <button class="audio-btn" onclick="event.stopPropagation(); playCurationAudio('${esc(data.syllable)}', ${t.tone})" style="padding: 2px 6px; font-size: 11px;">▶</button>
                        <span class="chinese" style="font-size: 20px;">${esc(t.char)}</span>
                    </div>
                    ${badges}
                    <div class="curation-tone-actions">${altsToggle}${actions}</div>
                    ${altsPanel}
                </div>`;
            });

            html += '</div>';
            panelEl.innerHTML = html;
        }

        function toneCurateAction(syllable, tone, action) {
            if (action === 'reset') {
                fetch('/api/tone_curation/reset', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({syllable, tone})
                })
                .then(r => r.json())
                .then(data => { if (data.success) loadToneCuratePanel(syllable); });
            } else {
                fetch('/api/tone_curation/update', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({syllable, tone, action})
                })
                .then(r => r.json())
                .then(data => { if (data.success) loadToneCuratePanel(syllable); });
            }
        }

        function toneCurateReplace(syllable, tone, newChar) {
            fetch('/api/tone_curation/update', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({syllable, tone, action: 'replace', new_char: newChar})
            })
            .then(r => r.json())
            .then(data => { if (data.success) loadToneCuratePanel(syllable); });
        }

        // ===== IMPORT =====

        let importPreviewData = null;

        function refreshImportLessons() {
            fetch('/api/import/lessons')
                .then(r => r.json())
                .then(data => {
                    const dropdown = document.getElementById('import-lesson-dropdown');
                    dropdown.innerHTML = '<option value="">-- Select a folder --</option>';

                    if (data.lessons && data.lessons.length > 0) {
                        // Group by textbook if multiple sources
                        const byTextbook = {};
                        data.lessons.forEach(lesson => {
                            const tb = lesson.textbook || 'Unknown Source';
                            if (!byTextbook[tb]) byTextbook[tb] = [];
                            byTextbook[tb].push(lesson);
                        });

                        const textbooks = Object.keys(byTextbook);
                        // Always use optgroups to show textbook name
                        textbooks.forEach(tb => {
                            const group = document.createElement('optgroup');
                            group.label = tb;
                            byTextbook[tb].forEach(lesson => {
                                const opt = document.createElement('option');
                                opt.value = lesson.id;
                                opt.textContent = `${lesson.display} (${lesson.vocab_count} vocab)`;
                                if (lesson.error) opt.disabled = true;
                                group.appendChild(opt);
                            });
                            dropdown.appendChild(group);
                        });
                        document.getElementById('import-no-lessons').style.display = 'none';
                    } else {
                        document.getElementById('import-no-lessons').style.display = 'block';
                    }
                    document.getElementById('import-preview').style.display = 'none';
                })
                .catch(err => console.error('Failed to load lessons:', err));
        }

        function loadImportPreview() {
            const lessonId = document.getElementById('import-lesson-dropdown').value;

            if (!lessonId) {
                document.getElementById('import-preview').style.display = 'none';
                return;
            }

            fetch(`/api/import/preview?lesson=${encodeURIComponent(lessonId)}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        alert('Error: ' + data.error);
                        return;
                    }

                    importPreviewData = data;
                    renderImportPreview(data);
                    document.getElementById('import-preview').style.display = 'block';
                })
                .catch(err => console.error('Failed to load preview:', err));
        }

        function renderImportPreview(data) {
            // Source info
            const sourceEl = document.getElementById('import-source-info');
            const source = data.source || {};

            let sourceHtml = '';
            if (source.textbook) {
                sourceHtml += `<div style="font-size: 13px; color: #666; margin-bottom: 5px;">📚 ${esc(source.textbook)}</div>`;
            }
            sourceHtml += `<strong>Lesson ${esc(source.lesson || '?')}</strong>: ${esc(source.title || 'Untitled')}`;
            sourceHtml += `<br><small style="color: #888;">Extracted: ${esc(source.extracted_date || 'Unknown')} via ${esc(source.extracted_by || 'unknown')}</small>`;

            // Show what content is available
            const features = [];
            if (data.dialogues?.length) features.push(`${data.dialogues.length} dialogue(s)`);
            if (data.grammar_patterns?.length) features.push(`${data.grammar_patterns.length} grammar pattern(s)`);
            if (features.length) {
                sourceHtml += `<br><small style="color: #2196F3;">Also includes: ${features.join(', ')}</small>`;
            }

            sourceEl.innerHTML = sourceHtml;

            // Summary
            const summaryEl = document.getElementById('import-summary');
            const s = data.summary || {};
            const nonIdenticalDups = (s.duplicate || 0) - (s.identical || 0);
            let dupText = '';
            if (s.identical > 0 && nonIdenticalDups > 0) {
                dupText = `${nonIdenticalDups} duplicates, ${s.identical} identical (hidden)`;
            } else if (s.identical > 0) {
                dupText = `${s.identical} identical (hidden)`;
            } else {
                dupText = `${s.duplicate || 0} duplicates`;
            }
            summaryEl.innerHTML = `
                <span style="color: #4CAF50;">● ${s.new || 0} new</span> ·
                <span style="color: #8BC34A;">● ${s.sandhi || 0} sandhi</span> ·
                <span style="color: #FF9800;">● ${s.new_not_in_dict || 0} not in dict</span> ·
                <span style="color: #f44336;">● ${s.conflict || 0} conflicts</span> ·
                <span style="color: #999;">● ${dupText}</span>
                ${s.identical > 0 ? `<br><label style="font-size: 12px; color: #888; cursor: pointer; margin-top: 4px; display: inline-block;"><input type="checkbox" id="show-identical-toggle" onchange="toggleIdenticalDuplicates()" style="margin-right: 4px;">Show identical duplicates</label>` : ''}
            `;

            // Items list
            const listEl = document.getElementById('import-items-list');
            listEl.innerHTML = '';

            (data.items || []).forEach((item, i) => {
                const row = document.createElement('div');
                row.className = 'import-item';
                row.dataset.index = i;

                // Hide identical duplicates by default
                if (item.status === 'duplicate' && item.identical) {
                    row.classList.add('identical-duplicate');
                    row.style.display = 'none';
                }

                let statusBadge = '';
                let statusColor = '#4CAF50';
                let canSelect = true;

                switch (item.status) {
                    case 'new':
                        statusBadge = 'NEW';
                        break;
                    case 'sandhi':
                        statusBadge = 'NEW (sandhi)';
                        statusColor = '#8BC34A';  // Light green - recognised sandhi
                        break;
                    case 'new_not_in_dict':
                        statusBadge = 'NEW (not in dict)';
                        statusColor = '#FF9800';
                        break;
                    case 'conflict':
                        statusBadge = 'CONFLICT';
                        statusColor = '#f44336';
                        break;
                    case 'duplicate':
                        statusBadge = 'EXISTS';
                        statusColor = '#9e9e9e';
                        // Allow selection but uncheck by default
                        break;
                }

                let extraInfo = '';
                if (item.status === 'conflict') {
                    // Show pypinyin (reliable) as reference; dict_pinyin may have rare/alternate reading
                    const expectedPinyin = item.pypinyin || item.dict_pinyin;
                    const radioName = `conflict-action-${i}`;
                    extraInfo = `
                        <div style="font-size: 12px; margin-top: 5px; padding: 8px; background: #fff3e0; border-radius: 4px;">
                            <div style="margin-bottom: 6px; color: #666;">Pinyin mismatch — choose which to use:</div>
                            <div style="padding-left: 8px;">
                                <label style="display: block; padding: 4px 0;">
                                    <input type="radio" name="${radioName}" value="textbook" class="conflict-action-radio" data-index="${i}" checked>
                                    Textbook: <strong>${esc(item.pinyin)}</strong>
                                </label>
                                <label style="display: block; padding: 4px 0;">
                                    <input type="radio" name="${radioName}" value="dictionary" class="conflict-action-radio" data-index="${i}">
                                    Dictionary: <strong>${esc(expectedPinyin)}</strong>
                                </label>
                                <label style="display: block; padding: 4px 0;">
                                    <input type="radio" name="${radioName}" value="both" class="conflict-action-radio" data-index="${i}">
                                    Add both as separate entries
                                </label>
                                <label style="display: block; padding: 4px 0; border-top: 1px solid #e0c080; margin-top: 4px;">
                                    <input type="radio" name="${radioName}" value="skip" class="conflict-action-radio" data-index="${i}">
                                    Skip (don't import)
                                </label>
                            </div>
                        </div>
                    `;
                } else if (item.status === 'sandhi' && item.note) {
                    extraInfo = `
                        <div style="font-size: 12px; margin-top: 5px; padding: 8px; background: #e8f5e9; border-radius: 4px;">
                            <em>${esc(item.note)}</em> — Citation form: ${esc(item.dict_pinyin)}
                        </div>
                    `;
                } else if (item.status === 'duplicate' && item.existing) {
                    // existing is now an array of all matching entries
                    const existingList = Array.isArray(item.existing) ? item.existing : [item.existing];
                    const radioName = `dup-action-${i}`;

                    let existingHtml = existingList.map((ex, j) => {
                        const isDiff = item.english !== ex.english || item.pinyin !== ex.pinyin;
                        const diffClass = isDiff ? 'color: #c62828;' : '';
                        return `
                            <div style="display: flex; align-items: center; padding: 4px 0; ${j > 0 ? 'border-top: 1px solid #e0e0e0; margin-top: 4px;' : ''}">
                                <label style="flex: 1; ${diffClass}">
                                    <input type="radio" name="${radioName}" value="replace-${ex.index}" class="dup-action-radio" data-index="${i}" data-replace-index="${ex.index}">
                                    Replace: ${esc(ex.pinyin)} — ${esc(ex.english)}
                                </label>
                            </div>
                        `;
                    }).join('');

                    extraInfo = `
                        <div style="font-size: 12px; margin-top: 5px; padding: 8px; background: #f5f5f5; border-radius: 4px;">
                            <div style="margin-bottom: 8px; padding-bottom: 6px; border-bottom: 1px solid #ddd;">
                                <strong>From textbook:</strong> ${esc(item.pinyin)} — ${esc(item.english)}
                            </div>
                            <div style="margin-bottom: 6px; color: #666;">In your vocabulary:</div>
                            <div style="margin-bottom: 8px; padding-left: 8px;">
                                <label style="display: block; padding: 4px 0;">
                                    <input type="radio" name="${radioName}" value="skip" class="dup-action-radio" data-index="${i}" checked>
                                    Keep existing (don't import)
                                </label>
                                ${existingHtml}
                                <label style="display: block; padding: 4px 0; border-top: 1px solid #e0e0e0; margin-top: 4px;">
                                    <input type="radio" name="${radioName}" value="add" class="dup-action-radio" data-index="${i}">
                                    Add as new entry
                                </label>
                            </div>
                        </div>
                    `;
                }

                // For duplicates and conflicts, hide main checkbox since we use radio buttons
                const showMainCheckbox = item.status !== 'duplicate' && item.status !== 'conflict';
                const isCheckedByDefault = canSelect && item.status !== 'conflict' && item.status !== 'duplicate';

                row.innerHTML = `
                    <div style="display: flex; align-items: flex-start; padding: 12px; border-bottom: 1px solid #eee; ${!canSelect ? 'opacity: 0.5;' : ''}">
                        <input type="checkbox" class="import-checkbox" data-index="${i}" ${canSelect ? '' : 'disabled'} ${isCheckedByDefault ? 'checked' : ''} onchange="updateImportCount()" style="margin-right: 12px; margin-top: 4px; ${showMainCheckbox ? '' : 'visibility: hidden;'}">
                        <div style="flex: 1;">
                            <span class="chinese" style="font-size: 20px;">${esc(item.characters)}</span>
                            <span class="pinyin import-pinyin-display" data-index="${i}" style="margin-left: 10px;">${esc(item.pinyin || '(no pinyin)')}</span>
                            <span class="import-english-display" data-index="${i}" style="margin-left: 15px; color: #666;">${esc(item.english)}</span>
                            <span style="float: right; font-size: 12px; padding: 2px 8px; border-radius: 10px; background: ${statusColor}; color: white;">${statusBadge}</span>
                            <button onclick="toggleImportEdit(${i})" style="float: right; margin-right: 8px; font-size: 11px; padding: 2px 8px; border: 1px solid #999; border-radius: 4px; background: #f0f0f0; color: #333; cursor: pointer;">Edit</button>
                            <div class="import-edit-panel" data-index="${i}" style="display: none; margin-top: 8px; padding: 8px; background: #fafafa; border: 1px solid #e0e0e0; border-radius: 4px;">
                                <div style="display: flex; gap: 10px; align-items: center;">
                                    <label style="font-size: 12px; color: #666;">Pinyin:
                                        <input type="text" class="import-edit-pinyin" data-index="${i}" value="${esc(item.pinyin || '')}" style="width: 150px; padding: 3px 6px; border: 1px solid #ccc; border-radius: 3px; font-size: 13px;">
                                    </label>
                                    <label style="font-size: 12px; color: #666;">English:
                                        <input type="text" class="import-edit-english" data-index="${i}" value="${esc(item.english || '')}" style="width: 200px; padding: 3px 6px; border: 1px solid #ccc; border-radius: 3px; font-size: 13px;">
                                    </label>
                                    <button onclick="applyImportEdit(${i})" style="font-size: 11px; padding: 3px 10px; background: #4CAF50; color: white; border: none; border-radius: 3px; cursor: pointer;">Apply</button>
                                    <button onclick="toggleImportEdit(${i})" style="font-size: 11px; padding: 3px 10px; border: 1px solid #ccc; border-radius: 3px; background: #fff; cursor: pointer;">Cancel</button>
                                </div>
                            </div>
                            ${extraInfo}
                        </div>
                    </div>
                `;

                listEl.appendChild(row);
            });

            // Add event delegation for duplicate and conflict radio buttons
            listEl.addEventListener('change', (e) => {
                if (e.target.classList.contains('dup-action-radio') ||
                    e.target.classList.contains('conflict-action-radio')) {
                    updateImportCount();
                }
            });

            updateImportCount();
        }

        function selectAllImport(selectNew) {
            const checkboxes = document.querySelectorAll('.import-checkbox:not([disabled])');
            checkboxes.forEach(cb => {
                if (selectNew) {
                    const idx = parseInt(cb.dataset.index);
                    const item = importPreviewData?.items?.[idx];
                    cb.checked = item && (item.status === 'new' || item.status === 'sandhi' || item.status === 'new_not_in_dict');
                } else {
                    cb.checked = false;
                }
            });
            updateImportCount();
        }

        function toggleImportEdit(idx) {
            const panel = document.querySelector(`.import-edit-panel[data-index="${idx}"]`);
            if (!panel) return;
            const isHidden = panel.style.display === 'none';
            if (isHidden) {
                // Smart pre-fill based on context
                const item = importPreviewData?.items?.[idx];
                if (item && item.status === 'duplicate') {
                    const selectedRadio = document.querySelector(`input[name="dup-action-${idx}"]:checked`);
                    if (selectedRadio && selectedRadio.value === 'skip') {
                        // Keep existing selected — pre-fill with existing values
                        const existing = item.existing?.[0];
                        if (existing) {
                            panel.querySelector('.import-edit-pinyin').value = existing.pinyin || '';
                            panel.querySelector('.import-edit-english').value = existing.english || '';
                        }
                    } else {
                        // Replace or Add as new — pre-fill with import values
                        panel.querySelector('.import-edit-pinyin').value = item.pinyin || '';
                        panel.querySelector('.import-edit-english').value = item.english || '';
                    }
                }
                // For non-duplicates, the fields already have the import values from rendering
            }
            panel.style.display = isHidden ? '' : 'none';
        }

        function applyImportEdit(idx) {
            const panel = document.querySelector(`.import-edit-panel[data-index="${idx}"]`);
            if (!panel) return;
            const newPinyin = panel.querySelector('.import-edit-pinyin').value.trim();
            const newEnglish = panel.querySelector('.import-edit-english').value.trim();

            // Update the preview data so confirmImport sends edited values
            if (importPreviewData?.items?.[idx]) {
                importPreviewData.items[idx].pinyin = newPinyin;
                importPreviewData.items[idx].english = newEnglish;
            }

            // Update the display text
            const pinyinDisplay = document.querySelector(`.import-pinyin-display[data-index="${idx}"]`);
            const englishDisplay = document.querySelector(`.import-english-display[data-index="${idx}"]`);
            if (pinyinDisplay) pinyinDisplay.textContent = newPinyin || '(no pinyin)';
            if (englishDisplay) englishDisplay.textContent = newEnglish;

            // Close the edit panel
            panel.style.display = 'none';
        }

        function toggleIdenticalDuplicates() {
            const show = document.getElementById('show-identical-toggle')?.checked;
            document.querySelectorAll('.identical-duplicate').forEach(row => {
                row.style.display = show ? '' : 'none';
            });
        }

        function updateImportCount() {
            // Count checked non-duplicate items
            let count = 0;
            document.querySelectorAll('.import-checkbox:checked').forEach(cb => {
                const idx = parseInt(cb.dataset.index);
                const item = importPreviewData?.items?.[idx];
                if (item && item.status !== 'duplicate' && item.status !== 'conflict') {
                    count++;
                }
            });

            // Count duplicate items with add/replace selected
            document.querySelectorAll('.dup-action-radio:checked').forEach(radio => {
                if (radio.value !== 'skip') {
                    count++;
                }
            });

            // Count conflict items with textbook/dictionary/both selected (not skip)
            document.querySelectorAll('.conflict-action-radio:checked').forEach(radio => {
                if (radio.value === 'both') {
                    count += 2;  // Adding two entries
                } else if (radio.value !== 'skip') {
                    count++;
                }
            });

            document.getElementById('import-selected-count').textContent = count;
        }

        function confirmImport() {
            if (!importPreviewData) return;

            const selectedItems = [];

            // Process regular items via checkboxes (not duplicates or conflicts)
            document.querySelectorAll('.import-checkbox:checked').forEach(cb => {
                const idx = parseInt(cb.dataset.index);
                const item = { ...importPreviewData.items[idx] };

                // Skip duplicates and conflicts - they're handled via radio buttons
                if (item.status === 'duplicate' || item.status === 'conflict') return;

                item.action = 'add';
                selectedItems.push(item);
            });

            // Process conflict items via radio buttons
            importPreviewData.items.forEach((item, idx) => {
                if (item.status !== 'conflict') return;

                const selectedRadio = document.querySelector(`input[name="conflict-action-${idx}"]:checked`);
                if (!selectedRadio) return;

                const value = selectedRadio.value;
                if (value === 'skip') return;

                if (value === 'both') {
                    // Add both versions as separate entries
                    const textbookItem = { ...item, action: 'add' };
                    const dictItem = { ...item, action: 'add', use_dictionary: true };
                    selectedItems.push(textbookItem);
                    selectedItems.push(dictItem);
                } else {
                    const importItem = { ...item };
                    importItem.action = 'add';
                    if (value === 'dictionary') {
                        importItem.use_dictionary = true;
                    }
                    selectedItems.push(importItem);
                }
            });

            // Process duplicate items via radio buttons
            importPreviewData.items.forEach((item, idx) => {
                if (item.status !== 'duplicate') return;

                const selectedRadio = document.querySelector(`input[name="dup-action-${idx}"]:checked`);
                if (!selectedRadio) return;

                const value = selectedRadio.value;
                if (value === 'skip') return;  // Don't include skipped items

                const importItem = { ...item };
                if (value === 'add') {
                    importItem.action = 'add';
                } else if (value.startsWith('replace-')) {
                    importItem.action = 'replace';
                    importItem.replace_index = parseInt(value.replace('replace-', ''));
                }
                selectedItems.push(importItem);
            });

            if (selectedItems.length === 0) {
                alert('No items selected for import.');
                return;
            }

            const addCount = selectedItems.filter(i => i.action === 'add').length;
            const replaceCount = selectedItems.filter(i => i.action === 'replace').length;
            let confirmMsg = `Import ${selectedItems.length} vocabulary items?`;
            if (replaceCount > 0) {
                confirmMsg = `Add ${addCount} new items and replace ${replaceCount} existing items?`;
            }

            if (!confirm(confirmMsg)) {
                return;
            }

            fetch('/api/import/confirm', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ items: selectedItems })
            })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    alert('Error: ' + data.error);
                    return;
                }

                let resultMsg = [];
                if (data.imported > 0) resultMsg.push(`${data.imported} added`);
                if (data.replaced > 0) resultMsg.push(`${data.replaced} replaced`);
                if (data.skipped > 0) resultMsg.push(`${data.skipped} skipped`);
                alert(`Import complete: ${resultMsg.join(', ')}.`);

                // Reload preview to update statuses
                loadImportPreview();
            })
            .catch(err => {
                console.error('Import failed:', err);
                alert('Import failed: ' + err);
            });
        }

        // Load import lessons when section is shown
        document.addEventListener('DOMContentLoaded', () => {
            const importNav = document.querySelector('[onclick*="showSection(\'import\')"]');
            if (importNav) {
                importNav.addEventListener('click', refreshImportLessons);
            }
        });

        // ==================== CONVERSATION PRACTICE ====================

        let conversationState = {
            lessonId: null,
            dialogueId: null,
            dialogue: null,
            userRole: null,
            currentLineIndex: 0,
            inputMode: 'characters',
            displayMode: 'all',
            validation: {
                allowProperNouns: true,
                allowSynonyms: true,
                tolerateTypos: true,
                forgiveToneErrors: true,
                structure: 'meaning'  // 'meaning' or 'grammar'
            },
            score: { correct: 0, total: 0 },
            previewExpanded: false
        };

        let conversationLessons = [];

        function applyValidationPreset() {
            const preset = document.getElementById('conversation-preset').value;
            const optionsEl = document.getElementById('conversation-validation-options');

            if (preset === 'gentle') {
                document.getElementById('val-proper-nouns').checked = true;
                document.getElementById('val-synonyms').checked = true;
                document.getElementById('val-typos').checked = true;
                document.getElementById('val-tone-errors').checked = true;
                document.getElementById('val-structure').value = 'meaning';
            } else if (preset === 'strict') {
                document.getElementById('val-proper-nouns').checked = true;
                document.getElementById('val-synonyms').checked = true;
                document.getElementById('val-typos').checked = false;
                document.getElementById('val-tone-errors').checked = false;
                document.getElementById('val-structure').value = 'grammar';
            }
            // 'custom' - leave as-is

            // Show/hide options based on preset
            optionsEl.style.display = (preset === 'custom') ? 'block' : 'none';
        }

        function getValidationOptions() {
            return {
                allowProperNouns: document.getElementById('val-proper-nouns').checked,
                allowSynonyms: document.getElementById('val-synonyms').checked,
                tolerateTypos: document.getElementById('val-typos').checked,
                forgiveToneErrors: document.getElementById('val-tone-errors').checked,
                structure: document.getElementById('val-structure').value
            };
        }

        function loadConversationLessons() {
            fetch('/api/conversation/lessons')
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error loading conversation lessons:', data.error);
                        return;
                    }
                    conversationLessons = data.lessons || [];
                    const select = document.getElementById('conversation-lesson');
                    select.innerHTML = '<option value="">-- Select a lesson --</option>';
                    conversationLessons.forEach(lesson => {
                        const opt = document.createElement('option');
                        opt.value = lesson.id;
                        opt.textContent = `Lesson ${lesson.lesson}: ${lesson.title}`;
                        select.appendChild(opt);
                    });

                    // Check API key
                    checkConversationApiKey();
                })
                .catch(err => {
                    console.error('Failed to load conversation lessons:', err);
                });
        }

        function checkConversationApiKey() {
            fetch('/api/config/test_api_key')
                .then(r => r.json())
                .then(data => {
                    const setupEl = document.getElementById('conversation-setup');
                    const noKeyEl = document.getElementById('conversation-no-api-key');
                    if (data.valid) {
                        setupEl.style.display = 'block';
                        noKeyEl.style.display = 'none';
                    } else {
                        setupEl.style.display = 'none';
                        noKeyEl.style.display = 'block';
                    }
                })
                .catch(() => {
                    // If check fails, show setup anyway
                });
        }

        function loadDialogueOptions() {
            const lessonId = document.getElementById('conversation-lesson').value;
            const dialogueSelect = document.getElementById('conversation-dialogue');
            const roleSelect = document.getElementById('conversation-role');
            const previewEl = document.getElementById('conversation-dialogue-preview');
            const startBtn = document.getElementById('start-conversation-btn');

            dialogueSelect.innerHTML = '<option value="">-- Select dialogue --</option>';
            roleSelect.innerHTML = '<option value="">-- Select dialogue first --</option>';
            previewEl.style.display = 'none';
            startBtn.disabled = true;

            if (!lessonId) return;

            const lesson = conversationLessons.find(l => l.id === lessonId);
            if (!lesson || !lesson.dialogues) return;

            lesson.dialogues.forEach(d => {
                const opt = document.createElement('option');
                opt.value = d.id;
                opt.textContent = d.title || d.id;
                dialogueSelect.appendChild(opt);
            });

            // Auto-select if only one dialogue
            if (lesson.dialogues.length === 1) {
                dialogueSelect.value = lesson.dialogues[0].id;
                loadDialogueDetails();
            }
        }

        function loadDialogueDetails() {
            const lessonId = document.getElementById('conversation-lesson').value;
            const dialogueId = document.getElementById('conversation-dialogue').value;
            const roleSelect = document.getElementById('conversation-role');
            const previewEl = document.getElementById('conversation-dialogue-preview');
            const startBtn = document.getElementById('start-conversation-btn');

            roleSelect.innerHTML = '<option value="">-- Select role --</option>';
            previewEl.style.display = 'none';
            startBtn.disabled = true;

            if (!lessonId || !dialogueId) return;

            fetch(`/api/conversation/dialogue?lesson=${encodeURIComponent(lessonId)}&dialogue=${encodeURIComponent(dialogueId)}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        console.error('Error loading dialogue:', data.error);
                        return;
                    }

                    conversationState.dialogue = data;

                    // Populate role selector
                    const speakers = data.speakers || [];
                    speakers.forEach(speaker => {
                        const opt = document.createElement('option');
                        opt.value = speaker;
                        opt.textContent = speaker;
                        roleSelect.appendChild(opt);
                    });

                    // Show preview (will be updated based on input mode)
                    updateConversationPreview();
                    previewEl.style.display = 'block';

                    // Auto-select first role
                    if (speakers.length > 0) {
                        roleSelect.value = speakers[0];
                        updateStartButton();
                    }
                })
                .catch(err => {
                    console.error('Failed to load dialogue:', err);
                });
        }

        function updateStartButton() {
            const lessonId = document.getElementById('conversation-lesson').value;
            const dialogueId = document.getElementById('conversation-dialogue').value;
            const role = document.getElementById('conversation-role').value;
            const startBtn = document.getElementById('start-conversation-btn');

            startBtn.disabled = !(lessonId && dialogueId && role);
        }

        function updateConversationPreview() {
            const previewLines = document.getElementById('conversation-preview-lines');
            const previewEl = document.getElementById('conversation-dialogue-preview');
            if (!previewLines || !conversationState.dialogue) return;

            // Toggle expanded class
            if (conversationState.previewExpanded) {
                previewEl.classList.add('expanded');
            } else {
                previewEl.classList.remove('expanded');
            }

            const displayMode = document.getElementById('conversation-display-mode').value;
            const lines = conversationState.dialogue.lines || [];

            // Determine what to show based on display mode (same logic as partner messages)
            const showChinese = displayMode !== 'pinyin';
            const showPinyin = displayMode === 'all' || displayMode === 'chinese_pinyin' || displayMode === 'pinyin';
            const showEnglish = displayMode === 'all' || displayMode === 'chinese_english';

            previewLines.innerHTML = '';
            const showCount = conversationState.previewExpanded ? lines.length : 5;
            lines.slice(0, showCount).forEach(line => {
                const div = document.createElement('div');
                div.className = 'dialogue-preview-line';

                // Build text based on display mode
                let parts = [];
                if (showChinese && line.chinese) parts.push(line.chinese);
                if (showPinyin && line.pinyin) parts.push(line.pinyin);
                if (showEnglish && line.english) parts.push(`(${line.english})`);
                const text = parts.join(' — ') || line.chinese;

                // Add audio button if line has Chinese text
                const audioBtn = line.chinese
                    ? `<button class="audio-btn small" onclick="readConversationLine('${esc(line.chinese.replace(/'/g, "\\'"))}')">🔊</button>`
                    : '';
                div.innerHTML = `<span class="dialogue-preview-speaker">${esc(line.speaker)}:</span> <span class="dialogue-preview-text">${esc(text)}</span> ${audioBtn}`;
                previewLines.appendChild(div);
            });

            if (lines.length > showCount) {
                const div = document.createElement('div');
                div.className = 'dialogue-preview-line dialogue-preview-expand';
                div.style.color = '#666';
                div.style.cursor = 'pointer';
                if (conversationState.previewExpanded) {
                    div.textContent = '▲ Show less';
                    div.onclick = () => { conversationState.previewExpanded = false; updateConversationPreview(); };
                } else {
                    div.textContent = `▼ Show all ${lines.length} lines`;
                    div.onclick = () => { conversationState.previewExpanded = true; updateConversationPreview(); };
                }
                previewLines.appendChild(div);
            }
        }

        function stripToneMarks(pinyin) {
            // Convert toned vowels to plain vowels
            const toneMap = {
                'ā': 'a', 'á': 'a', 'ǎ': 'a', 'à': 'a',
                'ē': 'e', 'é': 'e', 'ě': 'e', 'è': 'e',
                'ī': 'i', 'í': 'i', 'ǐ': 'i', 'ì': 'i',
                'ō': 'o', 'ó': 'o', 'ǒ': 'o', 'ò': 'o',
                'ū': 'u', 'ú': 'u', 'ǔ': 'u', 'ù': 'u',
                'ǖ': 'ü', 'ǘ': 'ü', 'ǚ': 'ü', 'ǜ': 'ü'
            };
            return pinyin.split('').map(c => toneMap[c] || c).join('');
        }

        // Add change listener for role selector
        document.addEventListener('DOMContentLoaded', () => {
            const roleSelect = document.getElementById('conversation-role');
            if (roleSelect) {
                roleSelect.addEventListener('change', updateStartButton);
            }

            // Handle Enter key in conversation input
            const convInput = document.getElementById('conversation-input');
            if (convInput) {
                convInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter') {
                        submitConversationTurn();
                    }
                });
            }
        });

        function startConversation() {
            const lessonId = document.getElementById('conversation-lesson').value;
            const dialogueId = document.getElementById('conversation-dialogue').value;
            const userRole = document.getElementById('conversation-role').value;
            const inputMode = document.getElementById('conversation-input-mode').value;
            const displayMode = document.getElementById('conversation-display-mode').value;
            const validation = getValidationOptions();

            if (!lessonId || !dialogueId || !userRole) {
                alert('Please select lesson, dialogue, and role.');
                return;
            }

            conversationState.lessonId = lessonId;
            conversationState.dialogueId = dialogueId;
            conversationState.userRole = userRole;
            conversationState.inputMode = inputMode;
            conversationState.displayMode = displayMode;
            conversationState.validation = validation;
            conversationState.currentLineIndex = 0;
            conversationState.score = { correct: 0, total: 0 };

            // Hide setup, show conversation area
            document.getElementById('conversation-setup').style.display = 'none';
            document.getElementById('conversation-area').style.display = 'block';
            document.getElementById('conversation-complete').style.display = 'none';
            document.getElementById('conversation-input-section').style.display = 'block';
            document.getElementById('conversation-feedback').style.display = 'none';

            // Set title and role indicator
            document.getElementById('conversation-title').textContent = conversationState.dialogue.title || 'Dialogue Practice';
            document.getElementById('conversation-your-role').textContent = userRole;

            // Clear messages
            document.getElementById('conversation-messages').innerHTML = '';

            // Start the conversation
            advanceConversation();
        }

        function advanceConversation() {
            const dialogue = conversationState.dialogue;
            const lines = dialogue.lines || [];

            // Display partner's lines until it's user's turn
            while (conversationState.currentLineIndex < lines.length) {
                const line = lines[conversationState.currentLineIndex];

                if (line.speaker === conversationState.userRole) {
                    // User's turn - show input
                    document.getElementById('conversation-input-section').style.display = 'block';
                    document.getElementById('conversation-input').value = '';
                    document.getElementById('conversation-input').focus();
                    document.getElementById('conversation-feedback').style.display = 'none';
                    return;
                } else {
                    // Partner's line - display it
                    displayConversationMessage(line, false);
                    conversationState.currentLineIndex++;
                }
            }

            // Dialogue complete
            showConversationComplete();
        }

        function displayConversationMessage(line, isUser, isError = false, isCorrection = false) {
            const messagesEl = document.getElementById('conversation-messages');
            const div = document.createElement('div');
            div.className = 'conversation-message ' + (isUser ? 'user' : 'partner');
            if (isError) div.classList.add('error');
            if (isCorrection) div.classList.add('correction');

            // Get display mode (only applies to partner messages)
            const displayMode = document.getElementById('conversation-display-mode')?.value || 'all';

            let html = '';
            if (isCorrection) {
                html += `<div class="conversation-message-label">✓ Correct answer:</div>`;
            }
            html += `<div class="conversation-message-speaker">${esc(line.speaker)}</div>`;

            // User messages always show all info; partner messages respect display mode
            if (isUser && !isCorrection) {
                html += `<div class="conversation-message-chinese">${esc(line.chinese)}</div>`;
                if (line.pinyin) {
                    html += `<div class="conversation-message-pinyin">${esc(line.pinyin)}</div>`;
                }
                if (line.english) {
                    html += `<div class="conversation-message-english">${esc(line.english)}</div>`;
                }
            } else if (isCorrection) {
                // Correction shows full info plus audio
                html += `<div class="conversation-message-chinese">${esc(line.chinese)}</div>`;
                if (line.pinyin) {
                    html += `<div class="conversation-message-pinyin">${esc(line.pinyin)}</div>`;
                }
                if (line.english) {
                    html += `<div class="conversation-message-english">${esc(line.english)}</div>`;
                }
                if (line.chinese) {
                    html += `<button class="audio-btn small" onclick="readConversationLine('${esc(line.chinese.replace(/'/g, "\\'"))}')">🔊</button>`;
                }
            } else {
                // Partner message - respect display mode
                const showChinese = displayMode !== 'pinyin';
                const showPinyin = displayMode === 'all' || displayMode === 'chinese_pinyin' || displayMode === 'pinyin';
                const showEnglish = displayMode === 'all' || displayMode === 'chinese_english';

                if (showChinese && line.chinese) {
                    html += `<div class="conversation-message-chinese">${esc(line.chinese)}</div>`;
                }
                if (showPinyin && line.pinyin) {
                    html += `<div class="conversation-message-pinyin">${esc(line.pinyin)}</div>`;
                }
                if (showEnglish && line.english) {
                    html += `<div class="conversation-message-english">${esc(line.english)}</div>`;
                }
                // Add read button for partner messages
                if (line.chinese) {
                    html += `<button class="audio-btn small" onclick="readConversationLine('${esc(line.chinese.replace(/'/g, "\\'"))}')">🔊</button>`;
                }
            }

            div.innerHTML = html;
            messagesEl.appendChild(div);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        function readConversationLine(text) {
            // Use the existing preview_audio endpoint to read the line
            const audio = new Audio(`/api/preview_audio?text=${encodeURIComponent(text)}`);
            audio.play().catch(err => console.error('Audio playback failed:', err));
        }

        function submitConversationTurn() {
            const input = document.getElementById('conversation-input').value.trim();
            if (!input) return;

            const dialogue = conversationState.dialogue;
            const lines = dialogue.lines || [];
            const expectedLine = lines[conversationState.currentLineIndex];

            // Show loading state
            const submitBtn = document.querySelector('.conversation-input-row button');
            const originalText = submitBtn.textContent;
            submitBtn.textContent = '...';
            submitBtn.disabled = true;

            fetch('/api/conversation/turn', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    lesson_id: conversationState.lessonId,
                    dialogue_id: conversationState.dialogueId,
                    user_role: conversationState.userRole,
                    line_index: conversationState.currentLineIndex,
                    user_input: input,
                    input_mode: conversationState.inputMode,
                    validation: conversationState.validation
                })
            })
            .then(r => r.json())
            .then(data => {
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;

                // Update usage display if available
                if (data.usage) {
                    loadApiUsage();
                }

                if (data.error) {
                    showConversationFeedback(false, 'Error: ' + data.error, expectedLine);
                    return;
                }

                conversationState.score.total++;
                if (data.correct) {
                    conversationState.score.correct++;
                }

                // Display user's message
                displayConversationMessage({
                    speaker: conversationState.userRole,
                    chinese: data.correct ? expectedLine.chinese : input,
                    pinyin: data.correct ? expectedLine.pinyin : null,
                    english: data.correct ? expectedLine.english : null
                }, true, !data.correct);

                // Show feedback with Next button
                showConversationFeedback(data.correct, data.feedback, expectedLine, true);

                if (data.correct) {
                    conversationState.currentLineIndex++;
                } else {
                    // Show expected answer in conversation (so audio matches what's visible)
                    displayConversationMessage({
                        speaker: conversationState.userRole,
                        chinese: expectedLine.chinese,
                        pinyin: expectedLine.pinyin,
                        english: expectedLine.english
                    }, true, false, true);  // isCorrection = true
                    conversationState.currentLineIndex++;
                }
            })
            .catch(err => {
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
                console.error('Conversation turn failed:', err);
                showConversationFeedback(false, 'Network error. Please try again.', expectedLine);
            });
        }

        function showConversationFeedback(correct, feedback, expectedLine, showNext = false) {
            const feedbackEl = document.getElementById('conversation-feedback');
            feedbackEl.className = 'conversation-feedback ' + (correct ? 'correct' : 'incorrect');

            let html = `<div class="conversation-feedback-title">${correct ? '✓ Correct!' : '✗ Not quite'}</div>`;
            html += `<div class="conversation-feedback-text">${esc(feedback)}</div>`;

            if (!correct && expectedLine) {
                html += `<div class="conversation-feedback-expected">`;
                html += `<strong>Expected:</strong> ${esc(expectedLine.chinese)}`;
                if (expectedLine.pinyin) html += ` (${esc(expectedLine.pinyin)})`;
                if (expectedLine.chinese) {
                    html += ` <button class="audio-btn small" onclick="readConversationLine('${esc(expectedLine.chinese.replace(/'/g, "\\'"))}')">🔊</button>`;
                }
                html += `</div>`;
            }

            if (showNext) {
                html += `<div class="conversation-feedback-actions"><button onclick="nextConversationTurn()">Next →</button></div>`;
            }

            feedbackEl.innerHTML = html;
            feedbackEl.style.display = 'block';
        }

        function nextConversationTurn() {
            document.getElementById('conversation-feedback').style.display = 'none';
            advanceConversation();
        }

        function showConversationHint() {
            const dialogue = conversationState.dialogue;
            const lines = dialogue.lines || [];
            const expectedLine = lines[conversationState.currentLineIndex];

            if (!expectedLine) return;

            let hint = '';
            if (conversationState.inputMode === 'characters') {
                // Show pinyin as hint
                hint = expectedLine.pinyin || expectedLine.chinese;
            } else {
                // Show first few characters/syllables
                const text = conversationState.inputMode === 'pinyin_tones' ? expectedLine.pinyin : expectedLine.pinyin;
                hint = text ? text.split(' ').slice(0, 2).join(' ') + '...' : expectedLine.chinese.slice(0, 2) + '...';
            }

            const feedbackEl = document.getElementById('conversation-feedback');
            feedbackEl.className = 'conversation-feedback';
            feedbackEl.innerHTML = `<div class="conversation-feedback-title">💡 Hint</div><div class="conversation-feedback-text">${esc(hint)}</div>`;
            feedbackEl.style.display = 'block';
        }

        function skipConversationTurn() {
            const dialogue = conversationState.dialogue;
            const lines = dialogue.lines || [];
            const expectedLine = lines[conversationState.currentLineIndex];

            conversationState.score.total++;

            // Display the expected line as user's message (marked as skipped)
            displayConversationMessage({
                speaker: conversationState.userRole,
                chinese: expectedLine.chinese,
                pinyin: expectedLine.pinyin,
                english: expectedLine.english
            }, true, true);

            // Show what was expected with Next button
            showConversationFeedback(false, 'Skipped. Here\'s what you should have said:', expectedLine, true);

            conversationState.currentLineIndex++;
        }

        function showConversationComplete() {
            document.getElementById('conversation-input-section').style.display = 'none';
            document.getElementById('conversation-feedback').style.display = 'none';

            const completeEl = document.getElementById('conversation-complete');
            const summaryEl = document.getElementById('conversation-summary');

            const score = conversationState.score;
            const percentage = score.total > 0 ? Math.round(100 * score.correct / score.total) : 0;

            summaryEl.innerHTML = `
                <p>You completed the dialogue!</p>
                <p style="font-size: 24px; margin: 15px 0;">${score.correct} / ${score.total} correct (${percentage}%)</p>
            `;

            completeEl.style.display = 'block';
        }

        function restartConversation() {
            document.getElementById('conversation-complete').style.display = 'none';
            startConversation();
        }

        function endConversation() {
            document.getElementById('conversation-area').style.display = 'none';
            document.getElementById('conversation-setup').style.display = 'block';
        }