import sys
from pymongo import MongoClient, ASCENDING
from datetime import datetime
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

def init_database():
    try:
        client = MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        print("✅ Connected to MongoDB")
    except Exception as e:
        print(f"❌ Cannot connect to MongoDB: {e}")
        print("\n📌 Make sure MongoDB is running:")
        print("   - Windows: mongod --dbpath 'C:\\data\\db'")
        print("   - Or use MongoDB Atlas (cloud)")
        return False
    
    # Get database
    db = client['chatbot']
    print(f"📦 Using database: {db.name}")
    
    # Create users collection
    if 'users' not in db.list_collection_names():
        db.create_collection('users')
        print("✅ Created 'users' collection")
    else:
        print("⚠️  'users' collection already exists")
    
    users_col = db['users']
    
    # Create indexes
    users_col.create_index('username', unique=True)
    users_col.create_index('created_at')
    print("✅ Created indexes for 'users'")
    
    # Create chat_messages collection
    if 'chat_messages' not in db.list_collection_names():
        db.create_collection('chat_messages')
        print("✅ Created 'chat_messages' collection")
    else:
        print("⚠️  'chat_messages' collection already exists")
    
    chat_col = db['chat_messages']
    chat_col.create_index([('user_id', ASCENDING), ('session_id', ASCENDING)])
    chat_col.create_index('created_at')
    print("✅ Created indexes for 'chat_messages'")
    
    # Insert sample users (nếu chưa có)
    existing_users = users_col.count_documents({})
    
    if existing_users == 0:
        print("\n📝 Creating sample users...")
        
        sample_users = [
            {
                '_id': 'user001',
                'username': 'admin',
                'password_hash': hash_password('admin123'),
                'has_face_encoding': False,
                'created_at': datetime.now(),
                'role': 'admin'
            },
            {
                '_id': 'user002',
                'username': 'john',
                'password_hash': hash_password('john123'),
                'has_face_encoding': False,
                'created_at': datetime.now(),
                'role': 'user'
            },
            {
                '_id': 'user003',
                'username': 'alice',
                'password_hash': hash_password('alice123'),
                'has_face_encoding': False,
                'created_at': datetime.now(),
                'role': 'user'
            }
        ]
        
        users_col.insert_many(sample_users)
        
        print("\n👥 Sample users created:")
        for user in sample_users:
            print(f"   - {user['username']} (password: {user['username']}123)")
    else:
        print(f"\n⚠️  Database already has {existing_users} users")
    
    print("\n✅ Database initialization completed!")
    print("\n📚 Collections:")
    for col_name in db.list_collection_names():
        col = db[col_name]
        count = col.count_documents({})
        print(f"   - {col_name}: {count} documents")
    
    print("\n💡 Next steps:")
    print("   1. Run the Flask server: python -m backend.app")
    print("   2. Open http://localhost:8000/login.html")
    print("   3. Login with: username='admin', password='admin123'")
    
    return True

if __name__ == '__main__':
    init_database()
