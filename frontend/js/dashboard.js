// API Base URL
const API_BASE = 'http://localhost:5000';

// Device States
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

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    loadUserInfo();
    initDeviceStates();
    startSensorUpdates();
});

// Load user info from localStorage
function loadUserInfo() {
    const userData = JSON.parse(localStorage.getItem('user'));
    if (userData) {
        document.getElementById('username').textContent = userData.username;
    } else {
        // Redirect to login if not authenticated
        window.location.href = 'login.html';
    }
}

// Initialize device states from backend
function initDeviceStates() {
    // Request initial states from backend
    fetch(`${API_BASE}/devices/status`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Update device states
                if (data.devices) {
                    deviceStates.lights = { ...deviceStates.lights, ...data.devices.lights };
                    deviceStates.ac = { ...deviceStates.ac, ...data.devices.ac };
                }
                updateDeviceUI();
            }
        })
        .catch(error => console.log('Device status not yet available:', error));
}

// Update UI based on device states
function updateDeviceUI() {
    // Update lights
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

    // Update AC
    const acBtn = document.getElementById('ac-bedroom');
    if (acBtn) {
        if (deviceStates.ac.bedroom) {
            acBtn.classList.add('on');
            acBtn.textContent = 'Bật';
        } else {
            acBtn.classList.remove('on');
            acBtn.textContent = 'Tắt';
        }
    }

    // Update temperature display
    document.getElementById('temp-bedroom').value = deviceStates.ac.temperature;
}

// Toggle Light
function toggleLight(room) {
    deviceStates.lights[room] = !deviceStates.lights[room];
    
    // Send to backend/MQTT
    sendCommand('light', room, deviceStates.lights[room]);
    
    // Update UI
    updateDeviceUI();
}

// Toggle AC
function toggleAC(room) {
    deviceStates.ac[room] = !deviceStates.ac[room];
    
    // Send to backend/MQTT
    sendCommand('ac', room, deviceStates.ac[room]);
    
    // Update UI
    updateDeviceUI();
}

// Increase Temperature
function increaseTemp(room) {
    if (deviceStates.ac.temperature < 30) {
        deviceStates.ac.temperature++;
        sendCommand('ac_temp', room, deviceStates.ac.temperature);
        document.getElementById('temp-bedroom').value = deviceStates.ac.temperature;
    }
}

// Decrease Temperature
function decreaseTemp(room) {
    if (deviceStates.ac.temperature > 16) {
        deviceStates.ac.temperature--;
        sendCommand('ac_temp', room, deviceStates.ac.temperature);
        document.getElementById('temp-bedroom').value = deviceStates.ac.temperature;
    }
}

// Send command to backend
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

// Start sensor updates (every 5 seconds)
function startSensorUpdates() {
    updateSensors();
    setInterval(updateSensors, 5000);
}

// Update sensor readings
function updateSensors() {
    fetch(`${API_BASE}/sensors/data`)
        .then(response => response.json())
        .then(data => {
            if (data.success && data.sensors) {
                document.getElementById('temp-value').textContent = 
                    data.sensors.temperature.toFixed(1) + '°C';
                document.getElementById('humidity-value').textContent = 
                    data.sensors.humidity.toFixed(1) + '%';
                document.getElementById('light-value').textContent = 
                    data.sensors.light + ' lux';
            }
        })
        .catch(error => console.log('Sensors not yet available:', error));
}

// Chatbot Functions
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

    // Display user message
    displayMessage(message, 'user');
    input.value = '';

    // Send to backend
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
    
    // Scroll to bottom
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Logout
function logout() {
    if (confirm('Bạn có chắc chắn muốn đăng xuất?')) {
        localStorage.removeItem('user');
        window.location.href = 'login.html';
    }
}
