import numpy as np
import os
from pathlib import Path
import pickle

# Lazy import face_recognition to avoid model loading issues
face_recognition = None

class FaceRecognitionHandler:
    """
    Xử lý nhận diện khuôn mặt
    """
    
    def __init__(self, encodings_dir="faces/encodings"):
        self.encodings_dir = encodings_dir
        self.known_faces = {}  # {user_id: [encodings]}
        self.known_names = {}  # {user_id: username}
        
        # Tạo folder nếu chưa tồn tại
        Path(encodings_dir).mkdir(parents=True, exist_ok=True)
        
        # Load encodings từ disk
        self.load_all_encodings()
    
    def load_all_encodings(self):
        """Load tất cả face encodings từ folder"""
        try:
            for filename in os.listdir(self.encodings_dir):
                if filename.endswith('.pkl'):
                    user_id = filename.replace('.pkl', '')
                    filepath = os.path.join(self.encodings_dir, filename)
                    
                    with open(filepath, 'rb') as f:
                        data = pickle.load(f)
                        self.known_faces[user_id] = data['encodings']
                        self.known_names[user_id] = data['username']
            
            print(f"✅ Loaded encodings for {len(self.known_faces)} users")
        except Exception as e:
            print(f"⚠️  Error loading encodings: {e}")
    
    def save_encodings(self, user_id, username, encodings):
        """Lưu face encodings cho user"""
        try:
            filepath = os.path.join(self.encodings_dir, f"{user_id}.pkl")
            
            data = {
                'user_id': user_id,
                'username': username,
                'encodings': encodings
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(data, f)
            
            # Update memory
            self.known_faces[user_id] = encodings
            self.known_names[user_id] = username
            
            return True
        except Exception as e:
            print(f"❌ Error saving encodings: {e}")
            return False
    
    def get_face_encodings_from_image(self, image_array):
        """
        Lấy face encodings từ ảnh
        
        Args:
            image_array: numpy array của ảnh (RGB format)
        
        Returns:
            list: Face encodings hoặc []
        """
        try:
            global face_recognition
            if face_recognition is None:
                import face_recognition as fr
                face_recognition = fr
            
            # Detect face locations
            face_locations = face_recognition.face_locations(
                image_array,
                model='cnn'  # Dùng 'cnn' nếu có GPU
            )
            
            if not face_locations:
                return []
            
            # Get encodings
            encodings = face_recognition.face_encodings(
                image_array,
                face_locations
            )
            
            return encodings
        except Exception as e:
            print(f"❌ Error getting face encodings: {e}")
            return []
    
    def recognize_faces(self, image_array, tolerance=0.6):
        """
        Nhận diện khuôn mặt từ ảnh
        
        Args:
            image_array: numpy array của ảnh (RGB format)
            tolerance: Ngưỡng khác biệt (càng thấp càng strict)
        
        Returns:
            dict: {
                'success': bool,
                'matched_users': [{'user_id': str, 'username': str, 'distance': float}],
                'unknown_faces': int,
                'total_faces': int
            }
        """
        try:
            # Get encodings từ uploaded image
            unknown_encodings = self.get_face_encodings_from_image(image_array)
            
            if not unknown_encodings:
                return {
                    'success': False,
                    'message': 'Không phát hiện khuôn mặt nào trong ảnh',
                    'matched_users': [],
                    'unknown_faces': 0,
                    'total_faces': 0
                }
            
            matched_users = []
            unknown_count = 0
            
            # So sánh với từng khuôn mặt trong ảnh
            for unknown_encoding in unknown_encodings:
                best_match = None
                best_distance = tolerance
                
                # So sánh với tất cả known faces
                for user_id, known_encodings in self.known_faces.items():
                    global face_recognition
                    if face_recognition is None:
                        import face_recognition as fr
                        face_recognition = fr
                    
                    # Compare với tất cả encodings của user
                    distances = face_recognition.face_distance(
                        known_encodings,
                        unknown_encoding
                    )
                    
                    min_distance = np.min(distances)
                    
                    # Nếu match tốt hơn best match hiện tại
                    if min_distance < best_distance:
                        best_distance = min_distance
                        best_match = {
                            'user_id': user_id,
                            'username': self.known_names[user_id],
                            'distance': float(min_distance)
                        }
                
                if best_match:
                    matched_users.append(best_match)
                else:
                    unknown_count += 1
            
            success = len(matched_users) > 0
            
            return {
                'success': success,
                'message': f"Nhận diện được {len(matched_users)} khuôn mặt" if success else "Không nhận diện được",
                'matched_users': matched_users,
                'unknown_faces': unknown_count,
                'total_faces': len(unknown_encodings)
            }
        
        except Exception as e:
            print(f"❌ Error recognizing faces: {e}")
            return {
                'success': False,
                'message': f"Lỗi: {str(e)}",
                'matched_users': [],
                'unknown_faces': 0,
                'total_faces': 0
            }
    
    def register_face_from_image(self, user_id, username, image_array):
        """
        Đăng ký khuôn mặt từ ảnh
        
        Args:
            user_id: ID của user
            username: Username của user
            image_array: numpy array của ảnh (RGB format)
        
        Returns:
            dict: {'success': bool, 'message': str}
        """
        try:
            encodings = self.get_face_encodings_from_image(image_array)
            
            if not encodings:
                return {
                    'success': False,
                    'message': 'Không phát hiện khuôn mặt trong ảnh'
                }
            
            # Save encodings
            if self.save_encodings(user_id, username, encodings):
                return {
                    'success': True,
                    'message': f"Đăng ký {len(encodings)} khuôn mặt thành công",
                    'encodings_count': len(encodings)
                }
            else:
                return {
                    'success': False,
                    'message': 'Lỗi lưu face encodings'
                }
        
        except Exception as e:
            print(f"❌ Error registering face: {e}")
            return {
                'success': False,
                'message': f"Lỗi: {str(e)}"
            }
    
    def has_user_face_encoding(self, user_id):
        """Kiểm tra user đã có face encoding chưa"""
        return user_id in self.known_faces
    
    def get_user_face_encodings(self, user_id):
        """Lấy face encodings của user"""
        return self.known_faces.get(user_id, [])
