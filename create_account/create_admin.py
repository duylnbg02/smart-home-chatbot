"""
Script tạo tài khoản admin mặc định
"""
from pymongo import MongoClient
import hashlib
import secrets
from datetime import datetime

def hash_password(password):
    """Hash password"""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )
    return f"{salt}${pwd_hash.hex()}"

if __name__ == '__main__':
    try:
        # Connect to MongoDB
        client = MongoClient('mongodb://localhost:27017')
        db = client['chatbot']
        users_col = db['users']

        # Check if admin exists
        admin = users_col.find_one({'username': 'admin'})

        if admin:
            print("=" * 60)
            print("⚠️  Admin account already exists!")
            print("=" * 60)
            print(f"Username: admin")
            print(f"User ID: {admin['_id']}")
            print("=" * 60)
        else:
            # Create admin
            admin_user = {
                '_id': 'admin_001',
                'username': 'admin',
                'password_hash': hash_password('123'),
                'has_face_encoding': False,
                'created_at': datetime.now(),
                'role': 'admin'
            }
            
            users_col.insert_one(admin_user)
            print("=" * 60)
            print("✅ Admin account created successfully!")
            print("=" * 60)
            print(f"Username: admin")
            print(f"Password: 123")
            print(f"User ID: admin_001")
            print("=" * 60)

        # List all users
        print("\n👥 All users in database:")
        for user in users_col.find().sort('created_at', 1):
            role = user.get('role', 'user')
            has_face = "✅" if user.get('has_face_encoding') else "❌"
            print(f"   - {user['username']:<10} ({user['_id']}) [{role}] Face: {has_face}")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
