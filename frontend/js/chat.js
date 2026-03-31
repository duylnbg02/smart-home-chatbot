const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const chatMessages = document.getElementById('chatMessages');
const usernameSpan = document.getElementById('username');
const logoutBtn = document.getElementById('logoutBtn');

const API_BASE_URL = 'http://localhost:5000';

window.addEventListener('load', () => {
    checkAuth();
});

function checkAuth() {
    const token = localStorage.getItem('authToken');
    const username = localStorage.getItem('username');
    
    if (!token) {
        window.location.href = 'login.html';
        return;
    }
    if (username && usernameSpan) {
        usernameSpan.textContent = `👤 ${username}`;
    }
}

if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
        const token = localStorage.getItem('authToken');
        if (token) {
            fetch(`${API_BASE_URL}/logout`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token })
            }).catch(() => {});
        }

        localStorage.removeItem('authToken');
        localStorage.removeItem('userId');
        localStorage.removeItem('username');
        window.location.href = 'login.html';
    });
}

sendBtn.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

async function sendMessage() {
    const message = messageInput.value.trim();  
    if (!message) return;

    displayMessage(message, 'user');
    messageInput.value = '';

    const userId = localStorage.getItem('userId');
    const token = localStorage.getItem('authToken');

    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                message: message,
                user_id: userId,
                token: token
            })
        });

        if (!response.ok) {
            throw new Error('Lỗi kết nối với server');
        }

        const data = await response.json();
        displayMessage(data.reply, 'bot');
    } catch (error) {
        displayMessage('❌ Lỗi: ' + error.message, 'bot');
    }
}

function displayMessage(text, sender) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    const p = document.createElement('p');
    p.textContent = text;
    p.style.whiteSpace = 'pre-wrap';
    messageDiv.appendChild(p);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}
