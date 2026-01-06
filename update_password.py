"""
Script cập nhật password admin thành 123
"""
import hashlib
import secrets
from pymongo import MongoClient

# Hash password "123"
password = '123'
salt = secrets.token_hex(16)
pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
hash_str = f"{salt}${pwd_hash.hex()}"

print(f"Hash mới: {hash_str}")

# Connect to MongoDB
client = MongoClient('mongodb://localhost:27017')
db = client['chatbot']

# Update admin password
result = db.users.update_one(
    {'username': 'admin'},
    {'$set': {'password_hash': hash_str}}
)

if result.modified_count > 0:
    print("✅ Admin password updated to: 123")
    user = db.users.find_one({'username': 'admin'})
    print(f"   Username: {user['username']}")
    print(f"   New hash: {user['password_hash'][:50]}...")
else:
    print("❌ No changes made")
