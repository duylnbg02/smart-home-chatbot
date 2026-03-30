import sys
from pymongo import MongoClient, ASCENDING
from datetime import datetime
import hashlib
import secrets

def hash_password(password):
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}${pwd_hash.hex()}"

def init_database():
    try:
        client = MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
    except Exception as e:
        print(f"❌ Lỗi kết nối MongoDB: {e}")
        return False
    
    db = client['chatbot']
    if 'users' not in db.list_collection_names():
        db.create_collection('users')
    
    users_col = db['users']
    users_col.create_index('username', unique=True)
    users_col.create_index('created_at')

    if 'chat_messages' not in db.list_collection_names():
        db.create_collection('chat_messages')
    
    chat_col = db['chat_messages']
    chat_col.create_index([('user_id', ASCENDING), ('session_id', ASCENDING)])
    chat_col.create_index('created_at')

    if users_col.count_documents({}) == 0:
        sample_users = [
            {'_id': 'user001', 'username': 'admin', 'password_hash': hash_password('admin123'), 
             'has_face_encoding': False, 'created_at': datetime.now(), 'role': 'admin'},
            {'_id': 'user002', 'username': 'john', 'password_hash': hash_password('john123'), 
             'has_face_encoding': False, 'created_at': datetime.now(), 'role': 'user'},
            {'_id': 'user003', 'username': 'alice', 'password_hash': hash_password('alice123'), 
             'has_face_encoding': False, 'created_at': datetime.now(), 'role': 'user'}
        ]
        users_col.insert_many(sample_users)
        print("Đã khởi tạo dữ liệu mẫu thành công.")
    else:
        print("Dữ liệu đã tồn tại, không cần khởi tạo lại.")
    return True

if __name__ == '__main__':
    init_database()