"""
Script tạo tài khoản admin
"""
from pymongo import MongoClient
import hashlib
import secrets

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

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017')
db = client['chatbot']
users_col = db['users']

# Check if admin exists
admin = users_col.find_one({'username': 'admin'})

if admin:
    print("✅ Admin account already exists!")
    print(f"   Username: admin")
    print(f"   User ID: {admin['_id']}")
else:
    # Create admin
    admin_user = {
        '_id': 'admin_001',
        'username': 'admin',
        'password_hash': hash_password('123'),
        'has_face_encoding': False,
        'created_at': __import__('datetime').datetime.now(),
        'role': 'admin'
    }
    
    users_col.insert_one(admin_user)
    print("✅ Admin account created successfully!")
    print(f"   Username: admin")
    print(f"   Password: 123")
    print(f"   User ID: admin_001")

# List all users
print("\n👥 All users in database:")
for user in users_col.find():
    print(f"   - {user['username']} ({user['_id']})")
