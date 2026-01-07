// API endpoints
const API_BASE_URL = 'http://localhost:5000';

// DOM elements
const tabBtns = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');
const loginForm = document.getElementById('loginForm');
const credentialsMessage = document.getElementById('credentialsMessage');
const webcam = document.getElementById('webcam');
const canvas = document.getElementById('canvas');
const startCameraBtn = document.getElementById('startCameraBtn');
const stopCameraBtn = document.getElementById('stopCameraBtn');
const captureFaceBtn = document.getElementById('captureFaceBtn');
const faceMessage = document.getElementById('faceMessage');
const faceStatus = document.getElementById('faceStatus');
const loadingSpinner = document.getElementById('loadingSpinner');

let cameraStream = null;
let isCameraActive = false;

// Tab switching
tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.dataset.tab;

        // Remove active class from all tabs
        tabBtns.forEach(b => b.classList.remove('active'));
        tabContents.forEach(content => content.classList.remove('active'));

        // Add active class to clicked tab
        btn.classList.add('active');
        document.getElementById(`${tabName}-tab`).classList.add('active');

        // Stop camera when switching away from face tab
        if (tabName !== 'face' && cameraStream) {
            stopCamera();
        }
    });
});

// ============ Credentials Login ============

loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    if (!username || !password) {
        showMessage(credentialsMessage, 'Vui lòng nhập tài khoản và mật khẩu', 'error');
        return;
    }

    showLoading(true);

    try {
        const response = await fetch(`${API_BASE_URL}/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok) {
            showMessage(credentialsMessage, '✅ Đăng nhập thành công!', 'success');
            saveAuthData(data);
            setTimeout(() => {
                window.location.href = 'dashboard.html';
            }, 1000);
        } else {
            showMessage(credentialsMessage, data.error || 'Đăng nhập thất bại', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        showMessage(credentialsMessage, 'Lỗi kết nối: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
});

// ============ Face Recognition ============

startCameraBtn.addEventListener('click', () => {
    startCamera();
});

stopCameraBtn.addEventListener('click', () => {
    stopCamera();
});

captureFaceBtn.addEventListener('click', () => {
    captureFace();
});

async function startCamera() {
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 320, height: 240, facingMode: 'user' }
        });

        webcam.srcObject = cameraStream;
        isCameraActive = true;

        startCameraBtn.style.display = 'none';
        stopCameraBtn.style.display = 'block';
        captureFaceBtn.style.display = 'block';

        faceStatus.textContent = '📹 Camera đang hoạt động';
        faceStatus.className = 'face-status info';
    } catch (error) {
        faceStatus.textContent = '❌ Không thể truy cập camera: ' + error.message;
        faceStatus.className = 'face-status error';
    }
}

function stopCamera() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
        isCameraActive = false;
    }

    webcam.srcObject = null;
    startCameraBtn.style.display = 'block';
    stopCameraBtn.style.display = 'none';
    captureFaceBtn.style.display = 'none';
    faceStatus.textContent = '';
    faceStatus.className = 'face-status';
}

async function captureFace() {
    if (!isCameraActive) {
        showMessage(faceMessage, 'Camera chưa bật', 'error');
        return;
    }

    // Draw webcam frame to canvas
    const ctx = canvas.getContext('2d');
    canvas.width = webcam.videoWidth;
    canvas.height = webcam.videoHeight;
    ctx.drawImage(webcam, 0, 0);

    // Convert canvas to blob
    canvas.toBlob(async (blob) => {
        showLoading(true);
        faceStatus.textContent = '⏳ Đang nhận diện khuôn mặt...';
        faceStatus.className = 'face-status info';

        try {
            const formData = new FormData();
            formData.append('image', blob, 'face.png');

            const response = await fetch(`${API_BASE_URL}/face-login`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                faceStatus.textContent = '✅ Nhận diện thành công!';
                faceStatus.className = 'face-status success';
                showMessage(faceMessage, '✅ Đăng nhập bằng khuôn mặt thành công!', 'success');
                
                saveAuthData(data);
                setTimeout(() => {
                    window.location.href = 'dashboard.html';
                }, 1000);
            } else {
                faceStatus.textContent = '❌ ' + (data.error || 'Nhận diện thất bại');
                faceStatus.className = 'face-status error';
                showMessage(faceMessage, data.error || 'Không nhận diện được khuôn mặt', 'error');
            }
        } catch (error) {
            console.error('Error:', error);
            faceStatus.textContent = '❌ Lỗi: ' + error.message;
            faceStatus.className = 'face-status error';
            showMessage(faceMessage, 'Lỗi kết nối: ' + error.message, 'error');
        } finally {
            showLoading(false);
        }
    }, 'image/png');
}

// ============ Utilities ============

function showMessage(element, text, type) {
    element.textContent = text;
    element.className = `message ${type}`;
}

function showLoading(show) {
    loadingSpinner.style.display = show ? 'flex' : 'none';
}

function saveAuthData(data) {
    localStorage.setItem('authToken', data.token || data.session_id);
    localStorage.setItem('userId', data.user_id);
    localStorage.setItem('user', JSON.stringify({
        user_id: data.user_id,
        username: data.username
    }));
}

function getAuthToken() {
    return localStorage.getItem('authToken');
}

// Clear messages on input
document.getElementById('username').addEventListener('focus', () => {
    credentialsMessage.textContent = '';
    credentialsMessage.className = 'message';
});

document.getElementById('password').addEventListener('focus', () => {
    credentialsMessage.textContent = '';
    credentialsMessage.className = 'message';
});

// Check if already logged in
window.addEventListener('load', () => {
    if (getAuthToken()) {
        window.location.href = 'dashboard.html';
    }
});
