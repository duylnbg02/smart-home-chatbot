"""
Script cập nhật password cho tài khoản
"""
import hashlib
import secrets
from pymongo import MongoClient

def generate_password_hash(password):
    """Tạo hash từ password"""
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
    print("🔑 CẬP NHẬT MẬT KHẨU")
    print("=" * 60)
    
    username = input("\nUsername cần cập nhật: ").strip()
    new_password = input("Mật khẩu mới: ").strip()
    
    if not username or not new_password:
        print("❌ Username/Password không được để trống!")
        exit()
    
    try:
        client = MongoClient('mongodb://localhost:27017')
        db = client['chatbot']
        users_col = db['users']
        
        # Find user
        user = users_col.find_one({'username': username})
        if not user:
            print(f"❌ Tài khoản '{username}' không tồn tại!")
            exit()
        
        # Update password
        hash_value = generate_password_hash(new_password)
        result = users_col.update_one(
            {'username': username},
            {'$set': {'password_hash': hash_value}}
        )
        
        print("\n" + "=" * 60)
        print("✅ Mật khẩu cập nhật thành công!")
        print("=" * 60)
        print(f"Username: {username}")
        print(f"Mật khẩu mới: {new_password}")
        print("=" * 60 + "\n")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
