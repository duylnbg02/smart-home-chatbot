const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const chatMessages = document.getElementById('chatMessages');
const usernameSpan = document.getElementById('username');
const logoutBtn = document.getElementById('logoutBtn');

const API_BASE_URL = 'http://localhost:5000';

// Check login when page loads
window.addEventListener('load', () => {
    checkAuth();
});

function checkAuth() {
    const token = localStorage.getItem('authToken');
    const username = localStorage.getItem('username');
    
    if (!token) {
        // Not logged in, redirect to login
        window.location.href = 'login.html';
        return;
    }
    
    // Show username
    if (username && usernameSpan) {
        usernameSpan.textContent = `👤 ${username}`;
    }
}

// Logout
if (logoutBtn) {
    logoutBtn.addEventListener('click', () => {
        const token = localStorage.getItem('authToken');
        
        // Optional: notify backend
        if (token) {
            fetch(`${API_BASE_URL}/logout`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token })
            }).catch(() => {});
        }
        
        // Clear storage and redirect
        localStorage.removeItem('authToken');
        localStorage.removeItem('userId');
        localStorage.removeItem('username');
        window.location.href = 'login.html';
    });
}

// Gửi tin nhắn khi nhấn nút Gửi
sendBtn.addEventListener('click', sendMessage);

// Gửi tin nhắn khi nhấn Enter
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});

async function sendMessage() {
    const message = messageInput.value.trim();
    
    if (!message) return;

    // Hiển thị tin nhắn của người dùng
    displayMessage(message, 'user');
    messageInput.value = '';

    // Get auth data
    const userId = localStorage.getItem('userId');
    const token = localStorage.getItem('authToken');

    // Gửi tin nhắn đến backend
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
    
    // Cuộn xuống cuối cùng
    chatMessages.scrollTop = chatMessages.scrollHeight;
}
