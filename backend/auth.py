import hashlib, secrets, uuid, logging
from datetime import datetime, timedelta

try:
    from backend.face_recognition import FaceRecognitionHandler
    FACE_AVAIL = True
except:
    FACE_AVAIL = False

class AuthHandler:
    def __init__(self, db=None):
        self.db = db
        self.face_handler = FaceRecognitionHandler() if FACE_AVAIL else None
        self.sessions = {}  

    def hash_pw(self, password):
        salt = secrets.token_hex(16)
        phash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${phash.hex()}"

    def verify_pw(self, stored_hash, password):
        try:
            salt, phash = stored_hash.split('$')
            check = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return check.hex() == phash
        except: return False

    def make_token(self, uid, user):
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {'user_id': uid, 'username': user, 'exp': datetime.now() + timedelta(hours=24)}
        return token

    def verify_token(self, token):
        sess = self.sessions.get(token)
        if sess and datetime.now() < sess['exp']: return sess
        self.sessions.pop(token, None)
        return None

    def login_with_credentials(self, username, password):
        if self.db is None: return {'success': False, 'message': 'No DB'}
        user = self.db['users'].find_one({'username': username})
        
        if user and self.verify_pw(user['password_hash'], password):
            uid = str(user['_id'])
            return {'success': True, 'token': self.make_token(uid, username), 'user_id': uid, 'username': username}
        return {'success': False, 'message': 'Sai tài khoản hoặc mật khẩu'}

    def login_with_face(self, img_array):
        if not self.face_handler: return {'success': False, 'message': 'Face ID off'}
        res = self.face_handler.recognize_faces(img_array)
        
        if res.get('success') and res.get('matched_users'):
            best = max(res['matched_users'], key=lambda x: x['confidence'])
            uid, user = best['user_id'], best['username']
            return {'success': True, 'token': self.make_token(uid, user), 'user_id': uid, 'username': user, 'conf': best['confidence']}
        return {'success': False, 'message': res.get('message', 'Không nhận diện được')}

    def register_face_for_user(self, uid, user, img_array, idx=1):
        try:
            res = self.face_handler.register_face_from_image(uid, user, img_array, idx)
            if res['success'] and self.db is not None:
                self.db['users'].update_one({'_id': uid}, {'$set': {'has_face_encoding': True}})
            return res
        except Exception as e: return {'success': False, 'message': str(e)}

    def logout(self, token):
        return bool(self.sessions.pop(token, None))