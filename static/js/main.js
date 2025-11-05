(() => {
    const chatBox = document.getElementById('chat');

    const input = document.getElementById('q');

    const btn = document.getElementById('askBtn');

    const suggestions = document.querySelectorAll('.suggest-btn');

    let lastQuery = "";

    function autosizeTextarea(el) {
        if (!el) return;
        el.style.height = 'auto';
        const newHeight = Math.min(el.scrollHeight, 160);
        el.style.height = newHeight + 'px';
    }

    autosizeTextarea(input);

    input.addEventListener('input', function () {
        autosizeTextarea(this);
    });

    input.addEventListener('focus', function () {
        requestAnimationFrame(() => autosizeTextarea(this));
    });


    function appendMessage(sender, text, isHTML = false) {
        const msg = document.createElement('div');
        msg.classList.add('message', sender);
        if (isHTML) msg.innerHTML = text;
        else msg.textContent = text;
        chatBox.appendChild(msg);
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    async function sendQuery(query) {
        if (!query.trim()) return;
        appendMessage('user', query);
        input.value = '';
        chatBox.scrollTop = chatBox.scrollHeight;
        appendMessage('aria', 'Thinking...');

        try {
            const res = await fetch('/api/check-compatibility', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query }),
            });

            const ct = (res.headers.get('Content-Type') || '').toLowerCase();
            const text = await res.text();
            chatBox.lastChild.remove();

            appendMessage('aria', text, ct.includes('text/html'));
        } catch (err) {
            chatBox.lastChild.remove();
            appendMessage('aria', 'Request failed: ' + err.message);
        }
    }

    btn.addEventListener('click', () => sendQuery(input.value));
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendQuery(input.value);
        }
    });

    suggestions.forEach((btn) => {
        btn.addEventListener('click', () => {
            sendQuery(btn.textContent);
        });
    });
})();
