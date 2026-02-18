/* ═══════════════════════════════════════════════
   MUL AI Assistant — Frontend Logic
   ═══════════════════════════════════════════════ */

// ── State ──────────────────────────────────────
let threadId = null;
let isProcessing = false;

// ── DOM Elements ───────────────────────────────
const chatMessages = document.getElementById('chatMessages');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const quickActions = document.getElementById('quickActions');
const welcomeTime = document.getElementById('welcomeTime');

// Set welcome time
welcomeTime.textContent = formatTime(new Date());

// ── Auto-resize textarea ───────────────────────
messageInput.addEventListener('input', () => {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
});

// ── Enter to send (Shift+Enter for newline) ────
messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// ── Format time ────────────────────────────────
function formatTime(date) {
    return date.toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
    });
}

// ── Send message ───────────────────────────────
async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isProcessing) return;

    isProcessing = true;
    sendBtn.disabled = true;

    // Hide quick actions after first message
    quickActions.style.display = 'none';

    // Add user message to UI
    appendMessage('user', text);

    // Clear input
    messageInput.value = '';
    messageInput.style.height = 'auto';

    // Show status indicator
    const statusEl = showStatusIndicator();

    try {
        // Use SSE streaming endpoint
        const response = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                thread_id: threadId,
            }),
        });

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let finalResponse = null;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Parse SSE events from buffer
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));

                        if (data.type === 'status') {
                            updateStatusIndicator(statusEl, data.icon, data.text);
                        } else if (data.type === 'response') {
                            finalResponse = data.response;
                            threadId = data.thread_id;
                        } else if (data.type === 'error') {
                            finalResponse = data.response;
                            threadId = data.thread_id;
                        }
                    } catch (e) {
                        // Skip malformed JSON
                    }
                }
            }
        }

        // Remove status indicator and show response
        statusEl.remove();
        if (finalResponse) {
            appendMessage('bot', finalResponse);
        } else {
            appendMessage('bot', "I'm sorry, I couldn't process your request. Please try again.");
        }

    } catch (error) {
        console.error('Chat error:', error);
        statusEl.remove();
        appendMessage('bot', "I'm sorry, something went wrong. Please try again or visit [mul.edu.pk](https://mul.edu.pk) directly.");
    } finally {
        isProcessing = false;
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

// ── Quick message shortcut ─────────────────────
function sendQuickMessage(text) {
    messageInput.value = text;
    sendMessage();
}

// ── Append message to chat ─────────────────────
function appendMessage(type, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;

    const timeStr = formatTime(new Date());

    if (type === 'bot') {
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="16" cy="16" r="14" fill="#0d7c3d"/>
                    <text x="16" y="21" text-anchor="middle" fill="white" font-size="13" font-weight="bold" font-family="Inter">M</text>
                </svg>
            </div>
            <div class="message-content">
                <div class="message-bubble">${formatMarkdown(content)}</div>
                <span class="message-time">${timeStr}</span>
            </div>
        `;
    } else {
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-bubble">${escapeHtml(content)}</div>
                <span class="message-time">${timeStr}</span>
            </div>
        `;
    }

    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// ── Status Indicator (replaces old typing dots) ─
function showStatusIndicator() {
    const statusDiv = document.createElement('div');
    statusDiv.className = 'status-indicator';
    statusDiv.id = 'statusIndicator';
    statusDiv.innerHTML = `
        <div class="message-avatar">
            <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="16" cy="16" r="14" fill="#0d7c3d"/>
                <text x="16" y="21" text-anchor="middle" fill="white" font-size="13" font-weight="bold" font-family="Inter">M</text>
            </svg>
        </div>
        <div class="status-bubble">
            <div class="status-spinner"></div>
            <span class="status-text">Processing your question...</span>
        </div>
    `;
    chatMessages.appendChild(statusDiv);
    scrollToBottom();
    return statusDiv;
}

function updateStatusIndicator(statusEl, icon, text) {
    const statusText = statusEl.querySelector('.status-text');
    if (statusText) {
        // Animate the text change
        statusText.style.opacity = '0';
        setTimeout(() => {
            statusText.textContent = `${icon} ${text}`;
            statusText.style.opacity = '1';
        }, 150);
    }
    scrollToBottom();
}

// ── Scroll to bottom ───────────────────────────
function scrollToBottom() {
    const container = document.querySelector('.chat-container');
    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });
}

// ── Simple Markdown → HTML ─────────────────────
function formatMarkdown(text) {
    if (!text) return '';

    let html = escapeHtml(text);

    // Bold: **text**
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

    // Italic: *text*
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');

    // Links: [text](url) — only allow http/https to prevent javascript: XSS
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

    // Headers: ### text
    html = html.replace(/^### (.+)$/gm, '<strong style="font-size:1.05em;">$1</strong>');
    html = html.replace(/^## (.+)$/gm, '<strong style="font-size:1.1em;">$1</strong>');

    // Unordered lists: - item or * item
    html = html.replace(/^[\-\*] (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
    // Clean up nested ul tags
    html = html.replace(/<\/ul>\s*<ul>/g, '');

    // Numbered lists: 1. item
    html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

    // Line breaks
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');

    // Wrap in paragraphs
    if (!html.startsWith('<')) {
        html = '<p>' + html + '</p>';
    }

    return html;
}

// ── Escape HTML ────────────────────────────────
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
