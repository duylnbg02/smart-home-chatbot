from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid, numpy as np, logging
from PIL import Image
from backend.constants import APP_HOST, APP_PORT, DEBUG, CORS_ORIGINS
from backend.mqtt_handler import get_mqtt_handler, init_mqtt
from backend.chatbot import get_chatbot
from database.mongodb import get_db
from backend.services import ChatHistoryService
from backend.auth import AuthHandler

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": CORS_ORIGINS}})

db = get_db("chatbot")
chat_service = ChatHistoryService(db)
mqtt_handler = get_mqtt_handler()
init_mqtt()
chatbot = get_chatbot(mqtt_handler)
auth = AuthHandler(db)

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
        nlp = chatbot.nlp.process(msg)
        reply = chatbot.get_response(msg)
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
        return jsonify({'sensors': mqtt_handler.get_sensor_data(), 'connected': mqtt_handler.is_connected}), 200
    except Exception as e:
        return jsonify({'sensors': {}, 'connected': False}), 200

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