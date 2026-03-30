const API_BASE = 'http://localhost:5000';

const deviceStates = {
    lights: {
        living_room: false,
        bedroom: false,
        bathroom: false
    },
    ac: {
        bedroom: false,
        temperature: 20
    }
};

document.addEventListener('DOMContentLoaded', function() {
    loadUserInfo();
    initDeviceStates();
    startSensorUpdates();
    startDeviceUpdates();
});

function loadUserInfo() {
    const userData = JSON.parse(localStorage.getItem('user'));
    if (userData) {
        document.getElementById('username').textContent = userData.username;
    } else {
        window.location.href = 'login.html';
    }
}

function fetchDeviceStates() {
    return fetch(`${API_BASE}/devices/status`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.devices) {
                deviceStates.lights = { ...deviceStates.lights, ...data.devices.lights };
                deviceStates.ac    = { ...deviceStates.ac,    ...data.devices.ac };
                updateDeviceUI();
            }
        })
        .catch(error => console.log('Device status not available:', error));
}

function initDeviceStates() {
    fetchDeviceStates();
}

function startDeviceUpdates() {
    setInterval(fetchDeviceStates, 3000);
}

function updateDeviceUI() {
    Object.keys(deviceStates.lights).forEach(light => {
        const btn = document.getElementById(`light-${light}`);
        if (btn) {
            if (deviceStates.lights[light]) {
                btn.classList.add('on');
                btn.querySelector('.light-status').textContent = 'Bật';
            } else {
                btn.classList.remove('on');
                btn.querySelector('.light-status').textContent = 'Tắt';
            }
        }
    });

    const acBtn = document.getElementById('ac-bedroom');
    if (acBtn) {
        if (deviceStates.ac.bedroom) {
            acBtn.classList.add('on');
            acBtn.querySelector('.ac-status').textContent = 'Bật';
        } else {
            acBtn.classList.remove('on');
            acBtn.querySelector('.ac-status').textContent = 'Tắt';
        }
    }
    document.getElementById('temp-bedroom').value = deviceStates.ac.temperature;
}

function toggleLight(room) {
    deviceStates.lights[room] = !deviceStates.lights[room];
    sendCommand('light', room, deviceStates.lights[room]);
    updateDeviceUI();
}

function toggleAC(room) {
    deviceStates.ac[room] = !deviceStates.ac[room];
    sendCommand('ac', room, deviceStates.ac[room]);
    updateDeviceUI();
}

function increaseTemp(room) {
    if (deviceStates.ac.temperature < 30) {
        deviceStates.ac.temperature++;
        sendCommand('ac_temp', room, deviceStates.ac.temperature);
        document.getElementById('temp-bedroom').value = deviceStates.ac.temperature;
    }
}

function decreaseTemp(room) {
    if (deviceStates.ac.temperature > 16) {
        deviceStates.ac.temperature--;
        sendCommand('ac_temp', room, deviceStates.ac.temperature);
        document.getElementById('temp-bedroom').value = deviceStates.ac.temperature;
    }
}

function sendCommand(type, location, value) {
    const payload = {
        type: type,
        location: location,
        value: value
    };

    console.log('Sending command:', payload);

    fetch(`${API_BASE}/device/command`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        console.log('Command response:', data);
        if (!data.success) {
            console.error('Command failed:', data.message);
        }
    })
    .catch(error => console.error('Command error:', error));
}

function startSensorUpdates() {
    updateSensors();
    setInterval(updateSensors, 5000);
}

function updateSensors() {
    fetch(`${API_BASE}/sensors/data`)
        .then(response => response.json())
        .then(data => {
            if (data.sensors) {
                const s = data.sensors;
                const temp = (typeof s.temperature === 'number') ? s.temperature : 0;
                const humi = (typeof s.humidity === 'number') ? s.humidity : 0;
                const light = (typeof s.light === 'number') ? s.light : 0;

                document.getElementById('temp-value').textContent = temp.toFixed(1) + '°C';
                document.getElementById('humidity-value').textContent = humi.toFixed(1) + '%';
                document.getElementById('light-value').textContent = light.toLocaleString() + ' lux';

                // Show source badge
                const badge = document.getElementById('sensor-source-badge');
                if (badge) {
                    if (data.source === 'weather') {
                        badge.textContent = '🌤️ WeatherAPI';
                        badge.title = 'Dữ liệu từ WeatherAPI (MQTT chưa kết nối)';
                        badge.style.color = '#f5a623';
                    } else {
                        badge.textContent = '📡 ESP32';
                        badge.title = 'Dữ liệu từ cảm biến ESP32';
                        badge.style.color = '#4caf50';
                    }
                }
            }
        })
        .catch(error => console.log('Sensors not yet available:', error));
}

function toggleChatbot() {
    const chatWindow = document.getElementById('chatbot-window');
    if (chatWindow.style.display === 'none') {
        chatWindow.style.display = 'flex';
        document.getElementById('chat-input').focus();
    } else {
        chatWindow.style.display = 'none';
    }
}

function sendChatMessage(event) {
    event.preventDefault();
    
    const input = document.getElementById('chat-input');
    const message = input.value.trim();

    if (!message) return;

    displayMessage(message, 'user');
    input.value = '';

    fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            message: message,
            user_id: JSON.parse(localStorage.getItem('user')).user_id
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.reply) {
            displayMessage(data.reply, 'bot');
        }
    })
    .catch(error => {
        console.error('Chat error:', error);
        displayMessage('Xin lỗi, có lỗi khi gửi tin nhắn.', 'bot');
    });
}

function displayMessage(text, sender) {
    const messagesDiv = document.getElementById('chatbot-messages');
    const messageEl = document.createElement('div');
    messageEl.className = `message ${sender}`;
    messageEl.textContent = text;
    messagesDiv.appendChild(messageEl);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Logout
function logout() {
    if (confirm('Bạn có chắc chắn muốn đăng xuất?')) {
        localStorage.clear();
        localStorage.removeItem('user');
        localStorage.removeItem('token');
        localStorage.removeItem('user_id');
        localStorage.removeItem('username');
        localStorage.removeItem('session_id');
        window.location.href = 'login.html?logout=true';
    }
}

async function checkFaceRegistration() {
    const userData = JSON.parse(localStorage.getItem('user') || '{}');
    const userId   = userData.user_id || localStorage.getItem('user_id');

    try {
        const noticeEl = document.getElementById('face-header-notice');
        if (noticeEl) {
            noticeEl.style.display = 'inline-block';
            noticeEl.className = 'face-header-notice loading';
        }

        const res  = await fetch(`${API_BASE}/faces`);
        const data = await res.json();

        const alreadyRegistered = data.faces &&
            data.faces.some(f => String(f.user_id) === String(userId));

        if (alreadyRegistered && noticeEl) {
            noticeEl.className = 'face-header-notice success';
            noticeEl.textContent = '✅ Bạn đã đăng ký khuôn mặt';
        }

        setTimeout(() => { window.location.href = 'face-register.html'; }, 800);
    } catch (e) {
        window.location.href = 'face-register.html';
    }
}

