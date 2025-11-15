(() => {
    const chatBox = document.getElementById('chat');
    const input = document.getElementById('q');
    const btn = document.getElementById('askBtn');
    const suggestions = document.querySelectorAll('.suggest-btn');

    function autoResizeTextarea(el) {
        if (!el) return;
        el.style.height = 'auto';
        const scrollH = el.scrollHeight;
        const maxH = Math.floor(window.innerHeight * 0.5);
        const newHeight = Math.min(scrollH, maxH);
        el.style.height = newHeight + 'px';
    }

    if (input) {
        input.style.minHeight = '48px';
        autoResizeTextarea(input);
    }

    if (input) {
        input.addEventListener('input', function () {
            autoResizeTextarea(this);
        }, { passive: true });

        input.addEventListener('focus', function () {
            requestAnimationFrame(() => {
                setTimeout(() => autoResizeTextarea(this), 80);
            });
        });

        window.addEventListener('resize', () => {
            autoResizeTextarea(input);
        });
    }

    function appendMessage(sender, text, isHTML = false) {
        const msg = document.createElement('div');
        msg.classList.add('message', sender);
        if (isHTML) msg.innerHTML = text;
        else msg.textContent = text;
        chatBox.appendChild(msg);
        chatBox.scrollTop = chatBox.scrollHeight;
        return msg;
    }

    function createBuildChipsArea(assistantMsg) {
        let existing = assistantMsg.querySelector('.build-chips-wrapper');
        if (existing) existing.remove();

        const wrapper = document.createElement('div');
        wrapper.className = 'build-chips-wrapper';

        const chipsRow = document.createElement('div');
        chipsRow.className = 'build-chips';
        wrapper.appendChild(chipsRow);

        const details = document.createElement('div');
        details.className = 'build-details';
        details.style.display = 'none';
        wrapper.appendChild(details);

        assistantMsg.appendChild(wrapper);
        return { wrapper, chipsRow, details };
    }

    function safeInnerHTML(container, html) {
        container.innerHTML = html;
    }

    function handleAssistantHtml(assistantMsg, htmlString) {
        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlString, 'text/html');
        const buildDivs = Array.from(doc.querySelectorAll('.build-option'));

        if (!buildDivs.length) {
            safeInnerHTML(assistantMsg, htmlString);
            return;
        }

        const { wrapper, chipsRow, details } = createBuildChipsArea(assistantMsg);
        const detailBlocks = [];

        buildDivs.forEach((div, idx) => {
            const h4 = div.querySelector('h4');
            const headerText = h4 ? h4.textContent.trim() : `Option ${idx + 1}`;
            const priceMatch = headerText.match(/(₱[\d,]+)/);
            const priceLabel = priceMatch ? ` — ${priceMatch[1]}` : '';
            const chipLabel = `Build ${idx + 1}${priceLabel}`;

            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'build-chip';
            chip.textContent = chipLabel;
            chipsRow.appendChild(chip);

            const detailHtml = div.outerHTML; 
            detailBlocks.push(detailHtml);

            chip.addEventListener('click', () => {
                chipsRow.querySelectorAll('.build-chip').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                safeInnerHTML(details, detailHtml);
                details.style.display = 'block';
                assistantMsg.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            });
        });

        const hint = document.createElement('div');
        hint.style.fontSize = '0.92rem';
        hint.style.color = '#666';
        hint.style.marginTop = '8px';
        hint.textContent = 'Click a build to reveal details.';
        wrapper.appendChild(hint);
    }

    async function sendQuery(query) {
        if (!query || !query.trim()) return;
        appendMessage('user', query);
        if (input) {
            input.value = '';
            autoResizeTextarea(input);
        }
        chatBox.scrollTop = chatBox.scrollHeight;
        const thinkingMsg = appendMessage('aria', 'Thinking...');

        try {
            const res = await fetch('/api/check-compatibility', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query }),
            });

            const ct = (res.headers.get('Content-Type') || '').toLowerCase();
            const text = await res.text();

            thinkingMsg.remove();

            if (ct.includes('text/html')) {
                const assistantMsg = appendMessage('aria', '', true);
                try {
                    handleAssistantHtml(assistantMsg, text);
                } catch (err) {
                    safeInnerHTML(assistantMsg, text);
                }
            } else {
                appendMessage('aria', text, false);
            }
        } catch (err) {
            thinkingMsg.remove();
            appendMessage('aria', 'Request failed: ' + err.message);
        } finally {
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    }

    if (btn) {
        btn.addEventListener('click', () => {
            sendQuery(input ? input.value : '');
        });
    }

    if (input) {
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendQuery(input.value);
            }
        });
    }

    suggestions.forEach((btnEl) => {
        btnEl.addEventListener('click', () => {
            sendQuery(btnEl.textContent);
        });
    });

    const pill = document.querySelector('.input-pill');
    if (pill && input) {
        pill.addEventListener('click', (e) => {
            if (e.target !== input) input.focus();
        });
    }
})();
