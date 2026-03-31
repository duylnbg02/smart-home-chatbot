import uuid
import numpy as np
import os
from pathlib import Path
import pickle
from datetime import datetime

face_recognition = None

class FaceRecognitionHandler:
    TOLERANCE = 0.6
    MAX_PHOTOS = 5
    FACES_DIR = Path(__file__).parent.parent / "faces" / "encodings"

    def __init__(self, db=None, encodings_dir=None):
        self.encodings_dir = encodings_dir or str(self.FACES_DIR)
        Path(self.encodings_dir).mkdir(parents=True, exist_ok=True)

        if db is None:
            try:
                from database.mongodb import get_db
                db = get_db("assistant")
            except Exception:
                db = None

        self.db = db
        self._collection = db["face_credentials"] if db is not None else None
        self._cache: list = []
        self._cache_loaded = False

    def _import_fr(self):
        global face_recognition
        if face_recognition is None:
            import face_recognition as fr
            face_recognition = fr
        return face_recognition

    def _load_cache(self):
        self._cache = []
        if self._collection is not None:
            for doc in self._collection.find({}):
                raw = doc.get("embedded")
                if raw is None:
                    continue
                try:
                    enc = pickle.loads(raw) if isinstance(raw, (bytes, bytearray)) else np.array(raw, dtype=np.float64)
                    self._cache.append({
                        "user_id": doc["userid"],
                        "username": doc.get("username", doc["userid"]),
                        "encoding": enc
                    })
                except Exception:
                    pass
        self._cache_loaded = True

    def _invalidate_cache(self):
        self._cache_loaded = False
        self._cache = []

    def _get_cache(self) -> list:
        if not self._cache_loaded:
            self._load_cache()
        return self._cache

    def _save_face_image(self, user_id: str, username: str, image_index: int,
        image_array: np.ndarray, suffix: str = "") -> str | None:
        try:
            from PIL import Image as PILImage
            save_dir = Path(self.encodings_dir)
            save_dir.mkdir(parents=True, exist_ok=True)
            name = f"{user_id}_{username}_{image_index}{suffix}.jpg"
            filepath = save_dir / name
            img = PILImage.fromarray(image_array.astype(np.uint8))
            img.save(str(filepath), "JPEG", quality=85)
            return str(filepath)
        except Exception:
            return None

    def register_face_from_image(self, user_id: str, username: str,
        image_array: np.ndarray, image_index: int = 1) -> dict:
        try:
            self._save_face_image(user_id, username, image_index, image_array, suffix="_raw")
            fr = self._import_fr()

            face_locations = fr.face_locations(image_array, model='hog')
            if not face_locations:
                return {'success': False, 'message': 'Không phát hiện khuôn mặt. Vui lòng chụp lại rõ hơn.'}
            
            if len(face_locations) > 1:
                return {'success': False, 'message': f'Phát hiện {len(face_locations)} khuôn mặt. Chỉ để 1 khuôn mặt.'}

            encodings = fr.face_encodings(image_array, face_locations)
            if not encodings:
                return {'success': False, 'message': 'Không thể trích xuất đặc trưng. Vui lòng thử lại.'}
            
            encoding = encodings[0]
            self._save_face_image(user_id, username, image_index, image_array)

            if self._collection is not None:
                self._collection.delete_one({'userid': user_id, 'image_index': image_index})
                self._collection.insert_one({
                    '_id': str(uuid.uuid4()),
                    'userid': user_id,
                    'username': username,
                    'embedded': pickle.dumps(encoding),
                    'image_index': image_index,
                    'created_at': datetime.now()
                })
                total = self._collection.count_documents({'userid': user_id})
                self._invalidate_cache()
                return {
                    'success': True,
                    'message': f'Lưu ảnh {image_index} thành công!',
                    'image_index': image_index,
                    'encodings_count': total
                }
            else:
                return {'success': False, 'message': 'Không có kết nối cơ sở dữ liệu.'}

        except Exception as e:
            return {'success': False, 'message': f'Lỗi: {str(e)}'}

    def recognize_faces(self, image_array: np.ndarray, tolerance: float = None) -> dict:
        tol = tolerance if tolerance is not None else self.TOLERANCE
        try:
            fr = self._import_fr()
            known_entries = self._get_cache()

            if not known_entries:
                return {'success': False, 'matched_users': [], 'face_count': 0,
                        'message': 'Chưa có khuôn mặt nào được đăng ký.'}

            face_locations = fr.face_locations(image_array, model='hog')
            if not face_locations:
                return {'success': False, 'matched_users': [], 'face_count': 0,
                        'message': 'Không phát hiện khuôn mặt trong ảnh.'}

            unknown_encodings = fr.face_encodings(image_array, face_locations)
            known_encs_arr = [e['encoding'] for e in known_entries]
            matched_users = []

            for unknown_enc in unknown_encodings:
                distances = fr.face_distance(known_encs_arr, unknown_enc)
                best_idx = int(np.argmin(distances))
                best_dist = float(distances[best_idx])

                if best_dist <= tol:
                    entry = known_entries[best_idx]
                    existing = next((m for m in matched_users if m['user_id'] == entry['user_id']), None)
                    if existing is None or best_dist < existing['distance']:
                        if existing:
                            matched_users.remove(existing)
                        matched_users.append({
                            'user_id': entry['user_id'],
                            'username': entry['username'],
                            'distance': round(best_dist, 4),
                            'confidence': round(1 - best_dist, 4)
                        })

            if matched_users:
                return {'success': True, 'matched_users': matched_users,
                        'face_count': len(face_locations),
                        'message': f'Nhận diện thành công'}
            
            return {'success': False, 'matched_users': [], 'face_count': len(face_locations),
                    'message': 'Khuôn mặt không khớp với bất kỳ user nào.'}

        except Exception as e:
            return {'success': False, 'matched_users': [], 'face_count': 0, 'message': f'Lỗi: {str(e)}'}

    def has_user_face_encoding(self, user_id: str) -> bool:
        if self._collection is not None:
            return self._collection.count_documents({'userid': user_id}) > 0
        return False

    def list_registered_faces(self) -> list:
        if self._collection is None:
            return []
        pipeline = [
            {'$group': {
                '_id': '$userid',
                'username': {'$first': '$username'},
                'encodings_count': {'$sum': 1},
                'updated_at': {'$max': '$created_at'}
            }},
            {'$project': {
                'user_id': '$_id',
                'username': 1,
                'encodings_count': 1,
                'updated_at': {'$toString': '$updated_at'},
                '_id': 0
            }}
        ]
        return list(self._collection.aggregate(pipeline))