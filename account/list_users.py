"""
Script hiển thị tất cả tài khoản trong database
"""
from pymongo import MongoClient
from datetime import datetime

if __name__ == '__main__':
    try:
        client = MongoClient('mongodb://localhost:27017')
        db = client['chatbot']
        users_col = db['users']
        
        users = list(users_col.find().sort('created_at', 1))
        
        if not users:
            print("❌ Không có tài khoản nào!")
            exit()
        
        print("\n" + "=" * 80)
        print("👥 DANH SÁCH TÀI KHOẢN")
        print("=" * 80)
        print(f"{'STT':<5} {'Username':<15} {'User ID':<40} {'Role':<10} {'Face':<8}")
        print("-" * 80)
        
        for idx, user in enumerate(users, 1):
            username = user.get('username', 'N/A')
            user_id = user.get('_id', 'N/A')[:20] + "..."  # Cắt ngắn ID
            role = user.get('role', 'user')
            has_face = "✅ Yes" if user.get('has_face_encoding') else "❌ No"
            
            print(f"{idx:<5} {username:<15} {user_id:<40} {role:<10} {has_face:<8}")
        
        print("=" * 80)
        print(f"Tổng: {len(users)} tài khoản\n")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
