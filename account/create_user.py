import hashlib
import secrets
import uuid
from datetime import datetime
from pymongo import MongoClient

def generate_password_hash(password):
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}${pwd_hash.hex()}"

if __name__ == '__main__':
    print("=" * 60)
    print("👤 TẠO TÀI KHOẢN MỚI")
    print("=" * 60)
    
    username = input("\nUsername: ").strip()
    password = input("Password: ").strip()
    
    if not username or not password:
        print("❌ Username/Password không được để trống!")
        exit()

    try:
        client = MongoClient('mongodb://localhost:27017')
        db = client['chatbot']
        users_col = db['users']
        
        # Check exists
        if users_col.find_one({'username': username}):
            print(f"❌ Tài khoản '{username}' đã tồn tại!")
            exit()
        
        # Create user
        user_id = str(uuid.uuid4())
        hash_value = generate_password_hash(password)
        
        user = {
            '_id': user_id,
            'username': username,
            'password_hash': hash_value,
            'has_face_encoding': False,
            'created_at': datetime.now(),
            'role': 'user'
        }
        
        users_col.insert_one(user)
        
        print("\n" + "=" * 60)
        print("✅ Tài khoản tạo thành công!")
        print("=" * 60)
        print(f"Username: {username}")
        print(f"Password: {password}")
        print(f"User ID: {user_id}")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
