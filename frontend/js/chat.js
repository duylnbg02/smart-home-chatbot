const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const micBtn = document.getElementById('micBtn');
const ttsBtn = document.getElementById('ttsBtn');
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
        localStorage.removeItem('user');
        window.location.href = 'login.html?_=' + Date.now();
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
        speakText(data.reply);
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

// ─── VOICE OUTPUT (TTS) ────────────────────────────
let ttsEnabled = false;

ttsBtn.addEventListener('click', () => {
    ttsEnabled = !ttsEnabled;
    ttsBtn.classList.toggle('active', ttsEnabled);
    ttsBtn.title = ttsEnabled ? 'Tắt đọc câu trả lời' : 'Bật đọc câu trả lời';
    if (!ttsEnabled) speechSynthesis.cancel();
});

function speakText(text) {
    if (!ttsEnabled) return;
    speechSynthesis.cancel();
    const utt = new SpeechSynthesisUtterance(text);
    utt.lang = 'vi-VN';
    utt.rate = 1.0;
    utt.pitch = 1.0;
    // Ưu tiên giọng tiếng Việt nếu có
    const voices = speechSynthesis.getVoices();
    const viVoice = voices.find(v => v.lang.startsWith('vi'));
    if (viVoice) utt.voice = viVoice;
    speechSynthesis.speak(utt);
}

// ─── VOICE INPUT (STT) ────────────────────────────
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRecognition) {
    const recognition = new SpeechRecognition();
    recognition.lang = 'vi-VN';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    let isRecording = false;

    micBtn.addEventListener('click', () => {
        if (isRecording) {
            recognition.stop();
        } else {
            recognition.start();
        }
    });

    recognition.addEventListener('start', () => {
        isRecording = true;
        micBtn.classList.add('recording');
        micBtn.title = 'Đang ghi âm... (nhấn để dừng)';
    });

    recognition.addEventListener('end', () => {
        isRecording = false;
        micBtn.classList.remove('recording');
        micBtn.title = 'Nhấn để nói';
    });

    recognition.addEventListener('result', (e) => {
        const transcript = e.results[0][0].transcript.trim();
        if (transcript) {
            messageInput.value = transcript;
            sendMessage();
        }
    });

    recognition.addEventListener('error', (e) => {
        console.error('SpeechRecognition error:', e.error);
        if (e.error === 'not-allowed') {
            alert('Vui lòng cho phép truy cập microphone trong trình duyệt.');
        }
    });
} else {
    micBtn.disabled = true;
    micBtn.title = 'Trình duyệt không hỗ trợ nhận dạng giọng nói';
    micBtn.style.opacity = '0.4';
}
