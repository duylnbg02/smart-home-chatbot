const API_BASE_URL = 'http://localhost:5000';

window.addEventListener('load', () => {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('logout') === 'true') {
        localStorage.clear();
        window.history.replaceState({}, document.title, window.location.pathname);
        return;
    }

    const user = localStorage.getItem('user');
    if (user) {
        try {
            JSON.parse(user); 
            window.location.href = 'dashboard.html';
        } catch (e) {
            localStorage.removeItem('user');
        }
    }
});

const tabBtns = document.querySelectorAll('.tab-btn');
const tabContents = document.querySelectorAll('.tab-content');
const loginForm = document.getElementById('loginForm');
const credentialsMessage = document.getElementById('credentialsMessage');
const webcam = document.getElementById('webcam');
const canvas = document.getElementById('canvas');
const startCameraBtn = document.getElementById('startCameraBtn');
const stopCameraBtn = document.getElementById('stopCameraBtn');
const captureFaceBtn = document.getElementById('captureFaceBtn');
const faceStatus = document.getElementById('faceStatus');
const loadingSpinner = document.getElementById('loadingSpinner');

let cameraStream = null;
let isCameraActive = false;

tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.dataset.tab;

        tabBtns.forEach(b => b.classList.remove('active'));
        tabContents.forEach(content => content.classList.remove('active'));

        btn.classList.add('active');
        document.getElementById(`${tabName}-tab`).classList.add('active');

        if (tabName !== 'face' && cameraStream) {
            stopCamera();
        }
    });
});

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
            showMessage(credentialsMessage, 'Đăng nhập thành công!', 'success');
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

startCameraBtn.addEventListener('click', () => { startCamera();});

stopCameraBtn.addEventListener('click', () => { stopCamera(); });

captureFaceBtn.addEventListener('click', () => { captureFace(); });

async function startCamera() {
    try {
        cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: 'user' }
        });

        webcam.srcObject = cameraStream;
        isCameraActive = true;

        startCameraBtn.style.display = 'none';
        stopCameraBtn.style.display = 'block';
        captureFaceBtn.style.display = 'block';

        const fs = document.getElementById('faceStatus');
        if (fs) { fs.textContent = 'Camera đang hoạt động'; fs.className = 'face-status info'; }
    } catch (error) {
        const fs = document.getElementById('faceStatus');
        if (fs) { fs.textContent = 'Không thể truy cập camera: ' + error.message; fs.className = 'face-status error'; }
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
    const fs = document.getElementById('faceStatus');
    if (fs) { fs.textContent = ''; fs.className = 'face-status'; }
}

async function captureFace() {
    const faceStatusEl = document.getElementById('faceStatus');

    function setStatus(text, type) {
        if (faceStatusEl) {
            faceStatusEl.textContent = text;
            faceStatusEl.className = 'face-status' + (type ? ' ' + type : '');
        }
    }

    if (!isCameraActive) {
        setStatus('❌ Camera chưa bật', 'error');
        return;
    }

    const ctx = canvas.getContext('2d');
    canvas.width = webcam.videoWidth;
    canvas.height = webcam.videoHeight;
    ctx.drawImage(webcam, 0, 0);
    canvas.toBlob(async (blob) => {
        try {
            showLoading(true);
            setStatus('⏳ Đang nhận diện khuôn mặt...', 'info');

            const formData = new FormData();
            formData.append('image', blob, 'face.png');

            const response = await fetch(`${API_BASE_URL}/face-login`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (response.ok) {
                setStatus('✅ Nhận diện thành công!', 'success');
                saveAuthData(data);
                setTimeout(() => {
                    window.location.href = 'dashboard.html';
                }, 1000);
            } else {
                setStatus('❌ ' + (data.error || 'Không nhận diện được khuôn mặt'), 'error');
            }
        } catch (error) {
            console.error('captureFace error:', error);
            setStatus('❌ Lỗi: ' + error.message, 'error');
        } finally {
            showLoading(false);
        }
    }, 'image/png');
}

function showMessage(element, text, type) {
    element.textContent = text;
    element.className = `message ${type}`;
}

function showLoading(show) {
    const spinner = document.getElementById('loadingSpinner');
    if (spinner) spinner.style.display = show ? 'flex' : 'none';
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

document.getElementById('username').addEventListener('focus', () => {
    credentialsMessage.textContent = '';
    credentialsMessage.className = 'message';
});

document.getElementById('password').addEventListener('focus', () => {
    credentialsMessage.textContent = '';
    credentialsMessage.className = 'message';
});
