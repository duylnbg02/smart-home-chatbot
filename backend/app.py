from flask import Flask, request, jsonify
from flask_cors import CORS
import uuid
from PIL import Image
import io
import numpy as np
from backend.chatbot import Chatbot
from backend.constants import APP_HOST, APP_PORT, DEBUG, CORS_ORIGINS
from nlp.pipeline import NLPPipeline

# Initialize Flask app
app = Flask(__name__)

# Enable CORS
CORS(app, resources={r"/.*": {"origins": CORS_ORIGINS}})

# Initialize components
chatbot = Chatbot()
nlp_pipeline = NLPPipeline()

# Initialize MongoDB connection and services
chat_service = None
db = None

try:
    from database.mongodb import get_db
    from backend.services import ChatHistoryService
    
    db = get_db("chatbot")
    chat_service = ChatHistoryService(db)
    print("✅ MongoDB connected successfully")
except Exception as e:
    print(f"⚠️  MongoDB connection warning: {e}")
    print("💡 Chat history will not be saved (make sure MongoDB is running)")
    chat_service = None

@app.route('/login', methods=['POST'])
def login():
    """
    Đăng nhập bằng username/password
    Request: {"username": "user", "password": "pass"}
    """
    try:
        print("📝 /login request received")
        from backend.auth import AuthHandler
        print("✅ AuthHandler imported")
        
        data = request.get_json()
        print(f"📝 Data: {data}")
        
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'error': 'Missing username or password'}), 400
        
        auth = AuthHandler(db)
        print(f"🔐 Authenticating: {data['username']}")
        
        result = auth.login_with_credentials(
            data['username'],
            data['password']
        )
        
        print(f"✅ Auth result: {result['success']}")
        
        if result['success']:
            return jsonify({
                'token': result['token'],
                'user_id': result['user_id'],
                'username': result['username'],
                'message': result['message']
            }), 200
        else:
            return jsonify({'error': result['message']}), 401
    
    except Exception as e:
        print(f"❌ Login error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/face-login', methods=['POST'])
def face_login():
    """
    Đăng nhập bằng nhận diện khuôn mặt
    Request: multipart/form-data với field 'image'
    """
    try:
        from backend.auth import AuthHandler
        
        if 'image' not in request.files:
            return jsonify({'error': 'Missing image field'}), 400
        
        image_file = request.files['image']
        
        if image_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Read and convert image to RGB
        image = Image.open(image_file.stream).convert('RGB')
        image_array = np.array(image)
        
        # Login with face
        auth = AuthHandler(db)
        result = auth.login_with_face(image_array)
        
        if result['success']:
            return jsonify({
                'token': result['token'],
                'user_id': result['user_id'],
                'username': result['username'],
                'confidence': result['confidence'],
                'message': result['message']
            }), 200
        else:
            return jsonify({'error': result['message']}), 401
    
    except Exception as e:
        print(f"❌ Face login error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/register-face', methods=['POST'])
def register_face():
    """
    Đăng ký khuôn mặt cho user
    Request: multipart/form-data với fields 'user_id', 'username', 'image'
    """
    try:
        from backend.auth import AuthHandler
        
        if 'image' not in request.files:
            return jsonify({'error': 'Missing image field'}), 400
        
        user_id = request.form.get('user_id')
        username = request.form.get('username')
        
        if not user_id or not username:
            return jsonify({'error': 'Missing user_id or username'}), 400
        
        image_file = request.files['image']
        
        if image_file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Read and convert image
        image = Image.open(image_file.stream).convert('RGB')
        image_array = np.array(image)
        
        # Register face
        auth = AuthHandler(db)
        result = auth.register_face_for_user(user_id, username, image_array)
        
        if result['success']:
            return jsonify({
                'message': result['message'],
                'encodings_count': result.get('encodings_count', 0)
            }), 200
        else:
            return jsonify({'error': result['message']}), 400
    
    except Exception as e:
        print(f"❌ Register face error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/logout', methods=['POST'])
def logout():
    """
    Đăng xuất
    Request: {"token": "session_token"}
    """
    try:
        from backend.auth import AuthHandler
        
        data = request.get_json()
        token = data.get('token') if data else None
        
        if not token:
            return jsonify({'error': 'Missing token'}), 400
        
        auth = AuthHandler(db)
        if auth.logout(token):
            return jsonify({'message': 'Logout successful'}), 200
        else:
            return jsonify({'error': 'Invalid token'}), 401
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/verify-token', methods=['POST'])
def verify_token():
    """
    Xác minh token
    Request: {"token": "session_token"}
    """
    try:
        from backend.auth import AuthHandler
        
        data = request.get_json()
        token = data.get('token') if data else None
        
        if not token:
            return jsonify({'error': 'Missing token'}), 400
        
        auth = AuthHandler(db)
        session = auth.verify_token(token)
        
        if session:
            return jsonify({
                'valid': True,
                'user_id': session['user_id'],
                'username': session['username']
            }), 200
        else:
            return jsonify({'valid': False, 'error': 'Invalid or expired token'}), 401
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/chat', methods=['POST'])
def chat():
    """
    Endpoint xử lý chat với NLP và database
    Request: {"message": "user message", "user_id": "optional", "session_id": "optional"}
    Response: {"reply": "bot reply", "intent": "intent", "entities": [...]}
    """
    try:
        data = request.get_json()
        
        if not data or 'message' not in data:
            return jsonify({'error': 'Missing message field'}), 400
        
        user_message = data['message'].strip()
        user_id = data.get('user_id', 'anonymous')
        session_id = data.get('session_id', str(uuid.uuid4()))
        
        if not user_message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Process with NLP pipeline
        nlp_result = nlp_pipeline.process(user_message)
        intent = nlp_result['intent']['type']
        entities = nlp_result['entities']
        
        # Get bot reply
        bot_reply = chatbot.get_response(user_message)
        
        # Save to database if available
        if chat_service:
            try:
                chat_service.save_message(
                    user_id=user_id,
                    session_id=session_id,
                    user_message=user_message,
                    bot_reply=bot_reply,
                    intent=intent,
                    entities=entities
                )
            except Exception as db_error:
                print(f"⚠️  Database error: {db_error}")
        
        return jsonify({
            'reply': bot_reply,
            'intent': intent,
            'entities': entities,
            'confidence': round(nlp_result['intent']['confidence'], 2),
            'session_id': session_id,
            'user_id': user_id
        }), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/history/<user_id>/<session_id>', methods=['GET'])
def get_history(user_id, session_id):
    """
    Get chat history for a session
    """
    try:
        if not chat_service:
            return jsonify({'error': 'Database not available'}), 503
        
        messages = chat_service.get_conversation(user_id, session_id)
        return jsonify({'messages': messages}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/sessions/<user_id>', methods=['GET'])
def get_sessions(user_id):
    """
    Get all sessions for a user
    """
    try:
        if not chat_service:
            return jsonify({'error': 'Database not available'}), 503
        
        sessions = chat_service.get_user_sessions(user_id)
        return jsonify({'sessions': sessions}), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stats/<user_id>', methods=['GET'])
def get_stats(user_id):
    """
    Get user statistics
    """
    try:
        if not chat_service:
            return jsonify({'error': 'Database not available'}), 503
        
        stats = chat_service.get_statistics(user_id)
        return jsonify(stats), 200
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint
    """
    return jsonify({
        'status': 'running',
        'database': 'connected' if chat_service else 'not available'
    }), 200

@app.route('/', methods=['GET'])
def home():
    """
    Home endpoint
    """
    return jsonify({'message': 'AI Chatbot API is running!'}), 200

if __name__ == '__main__':
    print(f"🚀 Starting Chatbot Server on http://{APP_HOST}:{APP_PORT}")
    print(f"📝 Frontend: Open http://localhost:8000")
    app.run(host=APP_HOST, port=APP_PORT, debug=DEBUG)
