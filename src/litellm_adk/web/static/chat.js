const chatMessages = document.getElementById('chat-messages');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const streamToggle = document.getElementById('stream-toggle');
const agentStatus = document.getElementById('agent-status');
const clearBtn = document.getElementById('clear-chat');
const newChatBtn = document.getElementById('new-chat');
const sessionContainer = document.getElementById('session-container');

let isProcessing = false;
let currentSessionId = `session_${Math.random().toString(36).substring(7)}`;
let activeSessions = new Set([currentSessionId]);

// Auto-resize textarea
userInput.addEventListener('input', function () {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

async function sendMessage() {
    const content = userInput.value.trim();
    if (!content || isProcessing) return;

    try {
        isProcessing = true;
        updateStatus('Thinking...', true);

        const welcomeHero = document.querySelector('.welcome-hero');
        if (welcomeHero) welcomeHero.style.display = 'none';

        appendMessage('user', content);
        userInput.value = '';
        userInput.style.height = 'auto';

        const streaming = streamToggle.checked;

        if (streaming) {
            await handleStreaming(content);
        } else {
            await handleStatic(content);
        }
    } catch (err) {
        console.error("Message error:", err);
        appendMessage('assistant', 'An unexpected error occurred.');
    } finally {
        isProcessing = false;
        updateStatus('Ready', false);
        refreshSessions();
    }
}

async function handleStatic(content) {
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: content, session_id: currentSessionId })
        });
        const data = await response.json();
        appendMessage('assistant', data.response);
    } catch (err) {
        appendMessage('assistant', 'Error: Could not connect to agent.');
    }
}

async function handleStreaming(content) {
    const messageDiv = appendMessage('assistant', '');
    const textElement = messageDiv.querySelector('.message-text');
    const toolContainer = messageDiv.querySelector('.tool-calls-container');
    let currentText = "";

    try {
        const response = await fetch('/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: content, session_id: currentSessionId })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (line.trim().startsWith('data: ')) {
                    const jsonStr = line.trim().substring(6);
                    try {
                        const data = JSON.parse(jsonStr);
                        if (data.type === 'delta') {
                            currentText += data.content;
                            if (textElement) {
                                if (textElement.style.display === 'none') textElement.style.display = 'block';
                                textElement.innerText = currentText;
                            }
                            chatMessages.scrollTop = chatMessages.scrollHeight;
                        } else if (data.type === 'tool_start') {
                            const toolDiv = document.createElement('div');
                            toolDiv.className = 'tool-call';
                            toolDiv.dataset.toolName = data.name;
                            toolDiv.innerHTML = `<span class="tool-icon">⚙️</span> Running tool: <strong>${data.name}</strong>...`;
                            toolContainer.appendChild(toolDiv);
                            chatMessages.scrollTop = chatMessages.scrollHeight;
                        } else if (data.type === 'tool_end') {
                            const activeTools = Array.from(toolContainer.querySelectorAll('.tool-call:not(.static)'));
                            if (activeTools.length > 0) {
                                const toolToMark = activeTools.find(div => div.dataset.toolName === data.name) || activeTools[0];
                                toolToMark.classList.add('static');
                                toolToMark.innerHTML = `<span class="tool-icon-static">✅</span> Tool Executed: <strong>${data.name || toolToMark.dataset.toolName}</strong>`;
                            }
                        } else if (data.type === 'done') {
                            // Safety: clear any lingering animated gears in this message
                            const lingering = toolContainer.querySelectorAll('.tool-call:not(.static)');
                            lingering.forEach(div => {
                                div.classList.add('static');
                                div.innerHTML = `<span class="tool-icon-static">✅</span> Tool Executed: <strong>${div.dataset.toolName}</strong>`;
                            });
                        }
                    } catch (e) { }
                }
            }
        }
    } catch (err) {
        textElement.innerText = 'Error: Streaming failed.';
    }
}

function appendMessage(role, content, toolCalls = []) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    let toolHtml = '';
    if (toolCalls && toolCalls.length > 0) {
        toolCalls.forEach(name => {
            toolHtml += `<div class="tool-call static">
                <span class="tool-icon-static">✅</span> Tool Executed: <strong>${name}</strong>
            </div>`;
        });
    }

    const contentHtml = content ? `<div class="message-text">${content}</div>` : `<div class="message-text" style="display:none"></div>`;

    div.innerHTML = `
        <div class="bubble">
            <div class="tool-calls-container">${toolHtml}</div>
            ${contentHtml}
        </div>
    `;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}

function updateStatus(text, loading) {
    if (agentStatus) agentStatus.innerText = text;
    const dot = document.querySelector('.dot-pulse');
    if (dot) {
        dot.style.background = loading ? '#faa61a' : '#10b981';
        dot.style.boxShadow = loading ? '0 0 10px #faa61a' : '0 0 10px #10b981';
        if (loading) {
            dot.style.animation = 'pulse 1.5s infinite';
        } else {
            dot.style.animation = 'none';
        }
    }
}

async function refreshSessions() {
    try {
        const response = await fetch('/sessions');
        const data = await response.json();
        const serverSessions = data.sessions || [];

        // Merge server sessions with local ones
        serverSessions.forEach(id => activeSessions.add(id));
        renderSessions();
    } catch (err) {
        console.error("Failed to fetch sessions", err);
    }
}

function renderSessions() {
    sessionContainer.innerHTML = '';
    const sorted = Array.from(activeSessions).sort();
    sorted.forEach(id => {
        const div = document.createElement('div');
        div.className = `session-item ${id === currentSessionId ? 'active' : ''}`;
        div.innerText = id;
        div.onclick = () => switchSession(id);
        sessionContainer.appendChild(div);
    });
}

async function switchSession(id) {
    if (id === currentSessionId) return;
    currentSessionId = id;
    chatMessages.innerHTML = '<div class="message assistant"><div class="bubble">Loading history...</div></div>';

    try {
        const response = await fetch(`/sessions/${id}/history`);
        const data = await response.json();
        chatMessages.innerHTML = '';
        if (data.history && data.history.length > 0) {
            data.history.forEach(msg => {
                appendMessage(msg.role, msg.content, msg.tool_calls || []);
            });
        } else {
            appendMessage('assistant', `Session ${id} has no history.`);
        }
    } catch (err) {
        chatMessages.innerHTML = '';
        appendMessage('assistant', 'Error loading session history.');
    }

    renderSessions();
}

newChatBtn.addEventListener('click', () => {
    currentSessionId = `session_${Math.random().toString(36).substring(7)}`;
    activeSessions.add(currentSessionId);
    chatMessages.innerHTML = '<div class="message assistant onboarding"><div class="bubble">New conversation started!</div></div>';
    renderSessions();
});

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

clearBtn.addEventListener('click', () => {
    chatMessages.innerHTML = '';
});

// Initial Load
(async () => {
    await refreshSessions();
    // If current session is already in the list, load its history
    if (activeSessions.has(currentSessionId)) {
        // Technically currentSessionId is new, so no history yet.
        // But if we refreshed the page, we might want to stay on a previous session?
        // For now, let's just start fresh but render the list.
    }
    renderSessions();
})();
