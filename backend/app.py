from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid, numpy as np, logging
from PIL import Image
from backend.constants import APP_HOST, APP_PORT, DEBUG, CORS_ORIGINS
from backend.mqtt_handler import get_mqtt_handler, init_mqtt
from backend.assistant import get_assistant
from database.mongodb import get_db
from backend.services import ChatHistoryService
from backend.auth import AuthHandler
from backend.weather_service import get_weather_service

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": CORS_ORIGINS}})

db = get_db("assistant")
chat_service = ChatHistoryService(db)
mqtt_handler = get_mqtt_handler()
init_mqtt()
assistant = get_assistant(mqtt_handler)
auth = AuthHandler(db)
weather_service = get_weather_service()

@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'success': False, 'message': 'Thiếu username hoặc password'}), 400
        res = auth.login_with_credentials(data.get('username'), data.get('password'))
        return jsonify(res), (200 if res['success'] else 401)
    except Exception as e:
        print(f"❌ /login error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/face-login', methods=['POST'])
def face_login():
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'Missing image'}), 400
        img = Image.open(request.files['image'].stream).convert('RGB')
        res = auth.login_with_face(np.array(img))
        return jsonify(res), (200 if res['success'] else 401)
    except Exception as e:
        print(f"❌ /face-login error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/register-face', methods=['POST'])
def register_face():
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'Missing image'}), 400
        if not request.form.get('user_id') or not request.form.get('username'):
            return jsonify({'success': False, 'message': 'Missing user_id or username'}), 400
        img = Image.open(request.files['image'].stream).convert('RGB')
        res = auth.register_face_for_user(
            request.form.get('user_id'),
            request.form.get('username'),
            np.array(img),
            int(request.form.get('image_index', 1))
        )
        return jsonify(res), (200 if res['success'] else 400)
    except Exception as e:
        print(f"❌ /register-face error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/verify-token', methods=['POST'])
def verify_token():
    try:
        data = request.get_json() or {}
        session = auth.verify_token(data.get('token'))
        return jsonify({'valid': bool(session), **(session or {})}), (200 if session else 401)
    except Exception as e:
        return jsonify({'valid': False, 'message': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Missing message'}), 400
        msg, uid, sid = data['message'].strip(), data.get('user_id', 'anonymous'), data.get('session_id', str(uuid.uuid4()))
        nlp = assistant.nlp.process(msg)
        reply = assistant.get_response(msg)
        if chat_service:
            chat_service.save_message(uid, sid, msg, reply, nlp['intent']['type'], nlp['entities'])
        return jsonify({'reply': reply, 'intent': nlp['intent']['type'], 'session_id': sid}), 200
    except Exception as e:
        print(f"❌ /chat error: {e}")
        return jsonify({'reply': 'Lỗi xử lý', 'error': str(e)}), 500

@app.route('/history/<user_id>/<session_id>', methods=['GET'])
def get_history(user_id, session_id):
    try:
        return jsonify({'messages': chat_service.get_conversation(user_id, session_id)}), 200
    except Exception as e:
        return jsonify({'messages': [], 'error': str(e)}), 500

@app.route('/devices/status', methods=['GET'])
def get_devices_status():
    try:
        return jsonify({'success': True, 'devices': mqtt_handler.get_device_states()}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/device/command', methods=['POST'])
def send_command():
    try:
        d = request.get_json() or {}
        success = mqtt_handler.send_command(d['type'], d['location'], d['value'])
        return jsonify({'success': success}), (200 if success else 500)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/sensors/data', methods=['GET'])
def get_sensors():
    try:
        sensor_data = mqtt_handler.get_sensor_data()
        connected = mqtt_handler.is_connected
        source = 'mqtt'
        # Fall back to WeatherAPI when MQTT not connected or no data
        if not connected or (sensor_data['temperature'] == 0 and sensor_data['humidity'] == 0):
            weather = weather_service.get_current()
            if weather:
                sensor_data = {
                    'temperature': weather['temperature'],
                    'humidity':    weather['humidity'],
                    'light':       weather['light'],
                }
                source = 'weather'
        return jsonify({'sensors': sensor_data, 'connected': connected, 'source': source}), 200
    except Exception as e:
        return jsonify({'sensors': {}, 'connected': False, 'source': 'error'}), 200

@app.route('/weather', methods=['GET'])
def get_weather():
    try:
        data = weather_service.get_current()
        if data:
            return jsonify({'success': True, 'weather': data}), 200
        return jsonify({'success': False, 'message': 'Không lấy được dữ liệu thời tiết'}), 503
    except Exception as e:
        print(f'❌ /weather error: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/health')
def health():
    return jsonify({'status': 'running', 'db': bool(chat_service), 'mqtt': mqtt_handler.is_connected}), 200

@app.route('/faces', methods=['GET'])
def list_faces():
    try:
        from backend.face_recognition import FaceRecognitionHandler
        faces = FaceRecognitionHandler(db=db).list_registered_faces()
        return jsonify({'faces': faces}), 200
    except Exception as e:
        print(f"❌ /faces error: {e}")
        return jsonify({'faces': [], 'error': str(e)}), 500

if __name__ == '__main__':
    logging.getLogger('werkzeug').addFilter(lambda r: '/sensors/data' not in r.getMessage())
    app.run(host=APP_HOST, port=APP_PORT, debug=DEBUG)