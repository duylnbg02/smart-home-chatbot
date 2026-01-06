import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

# Try to import face_recognition, but don't fail if models not available
try:
    from backend.face_recognition_handler import FaceRecognitionHandler
    FACE_RECOGNITION_AVAILABLE = True
except Exception as e:
    print(f"⚠️  Face recognition not available: {e}")
    FaceRecognitionHandler = None
    FACE_RECOGNITION_AVAILABLE = False

class AuthHandler:
    """
    Xử lý authentication (username/password + face recognition)
    """
    
    def __init__(self, db=None):
        """
        Args:
            db: MongoDB database instance
        """
        self.db = db
        if FACE_RECOGNITION_AVAILABLE:
            self.face_handler = FaceRecognitionHandler()
        else:
            self.face_handler = None
        self.active_sessions = {}  # {token: {user_id, username, expires}}
    
    def hash_password(self, password):
        """Hash password bằng SHA256 + salt"""
        salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            100000
        )
        return f"{salt}${pwd_hash.hex()}"
    
    def verify_password(self, stored_hash, password):
        """Verify password"""
        try:
            salt, pwd_hash = stored_hash.split('$')
            new_hash = hashlib.pbkdf2_hmac(
                'sha256',
                password.encode('utf-8'),
                salt.encode('utf-8'),
                100000
            )
            return new_hash.hex() == pwd_hash
        except:
            return False
    
    def generate_token(self, user_id, username, expires_in_hours=24):
        """Generate session token"""
        token = secrets.token_urlsafe(32)
        self.active_sessions[token] = {
            'user_id': user_id,
            'username': username,
            'expires': datetime.now() + timedelta(hours=expires_in_hours)
        }
        return token
    
    def verify_token(self, token):
        """Verify session token"""
        if token not in self.active_sessions:
            return None
        
        session = self.active_sessions[token]
        
        # Check expiry
        if datetime.now() > session['expires']:
            del self.active_sessions[token]
            return None
        
        return session
    
    def logout(self, token):
        """Logout - remove session"""
        if token in self.active_sessions:
            del self.active_sessions[token]
            return True
        return False
    
    # ============ Username/Password Login ============
    
    def login_with_credentials(self, username, password):
        """
        Đăng nhập bằng username/password
        
        Args:
            username: Username
            password: Password
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'token': str (nếu success),
                'user_id': str,
                'username': str
            }
        """
        if self.db is None:
            return {
                'success': False,
                'message': 'Database chưa được kết nối'
            }
        
        try:
            # Find user by username
            users_collection = self.db['users']
            user = users_collection.find_one({'username': username})
            
            if not user:
                return {
                    'success': False,
                    'message': 'Tài khoản không tồn tại'
                }
            
            # Verify password
            if not self.verify_password(user['password_hash'], password):
                return {
                    'success': False,
                    'message': 'Mật khẩu sai'
                }
            
            # Generate token
            user_id = str(user['_id'])
            token = self.generate_token(user_id, username)
            
            return {
                'success': True,
                'message': 'Đăng nhập thành công',
                'token': token,
                'user_id': user_id,
                'username': username
            }
        
        except Exception as e:
            print(f"❌ Login error: {e}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }
    
    # ============ Face Recognition Login ============
    
    def login_with_face(self, image_array):
        """
        Đăng nhập bằng nhận diện khuôn mặt
        
        Args:
            image_array: numpy array của ảnh (RGB format)
        
        Returns:
            dict: {
                'success': bool,
                'message': str,
                'token': str (nếu success),
                'user_id': str,
                'username': str,
                'confidence': float (độ chính xác 0-1)
            }
        """
        try:
            # Nhận diện khuôn mặt
            result = self.face_handler.recognize_faces(image_array)
            
            if not result['success'] or not result['matched_users']:
                return {
                    'success': False,
                    'message': 'Không nhận diện được khuôn mặt'
                }
            
            # Lấy best match (distance nhỏ nhất)
            best_match = min(result['matched_users'], key=lambda x: x['distance'])
            user_id = best_match['user_id']
            username = best_match['username']
            confidence = 1 - best_match['distance']  # Convert distance to confidence
            
            # Generate token
            token = self.generate_token(user_id, username)
            
            return {
                'success': True,
                'message': 'Đăng nhập bằng khuôn mặt thành công',
                'token': token,
                'user_id': user_id,
                'username': username,
                'confidence': round(confidence, 2)
            }
        
        except Exception as e:
            print(f"❌ Face login error: {e}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }
    
    # ============ User Management ============
    
    def create_user(self, username, password):
        """
        Tạo user mới
        
        Args:
            username: Username
            password: Password
        
        Returns:
            dict: {'success': bool, 'message': str, 'user_id': str}
        """
        if self.db is None:
            return {
                'success': False,
                'message': 'Database chưa được kết nối'
            }
        
        try:
            users_collection = self.db['users']
            
            # Check username exists
            if users_collection.find_one({'username': username}):
                return {
                    'success': False,
                    'message': 'Tài khoản đã tồn tại'
                }
            
            # Create user
            user_id = str(uuid.uuid4())
            user = {
                '_id': user_id,
                'username': username,
                'password_hash': self.hash_password(password),
                'created_at': datetime.now(),
                'has_face_encoding': False
            }
            
            users_collection.insert_one(user)
            
            return {
                'success': True,
                'message': 'Tạo tài khoản thành công',
                'user_id': user_id
            }
        
        except Exception as e:
            print(f"❌ Create user error: {e}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }
    
    def register_face_for_user(self, user_id, username, image_array):
        """
        Đăng ký khuôn mặt cho user
        
        Args:
            user_id: User ID
            username: Username
            image_array: numpy array của ảnh (RGB format)
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            result = self.face_handler.register_face_from_image(
                user_id, username, image_array
            )
            
            # Update user trong database
            if result['success'] and self.db:
                try:
                    users_collection = self.db['users']
                    users_collection.update_one(
                        {'_id': user_id},
                        {'$set': {'has_face_encoding': True}}
                    )
                except:
                    pass
            
            return result
        
        except Exception as e:
            print(f"❌ Register face error: {e}")
            return {
                'success': False,
                'message': f'Lỗi: {str(e)}'
            }
