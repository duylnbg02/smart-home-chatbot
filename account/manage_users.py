import hashlib, secrets, getpass
from pymongo import MongoClient
from datetime import datetime

db = MongoClient("mongodb://localhost:27017")["assistant"]
users_col = db["users"]

def hash_pw(password):
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return f"{salt}${pwd_hash.hex()}"

def create_user():
    user = input("Username: ").strip()
    if users_col.find_one({"username": user}): return print("Người dùng đã tồn tại!")
    
    pw = getpass.getpass("Password: ")
    role = input("Role (admin/user): ") or "user"
    
    users_col.insert_one({
        "_id": f"user_{secrets.token_hex(4)}",
        "username": user,
        "password_hash": hash_pw(pw),
        "role": role,
        "created_at": datetime.now()
    })
    print("Người dùng đã được tạo.")

def list_users():
    print("\n--- DANH SÁCH ---")
    for u in users_col.find():
        print(f"• {u['username']} [{u.get('role','user')}] - ID: {u['_id']}")

def update_pw():
    user = input("Username: ").strip()
    if not users_col.find_one({"username": user}): return print("Không tìm thấy người dùng!")
    
    new_pw = getpass.getpass("Mật khẩu mới: ")
    users_col.update_one({"username": user}, {"$set": {"password_hash": hash_pw(new_pw)}})
    print("Mật khẩu đã được cập nhật!")

def main():
    menu = {"1": create_user, "2": list_users, "3": update_pw}
    while True:
        print("\n1.Tạo | 2.List | 3.Đổi PW | 4.Thoát")
        c = input("Chọn: ")
        if c == "4": break
        if c in menu: menu[c]()

if __name__ == "__main__":
    main()