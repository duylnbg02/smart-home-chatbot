from pymongo import MongoClient
import hashlib
import secrets
from datetime import datetime
import getpass


# =========================
# PASSWORD HASH
# =========================
def generate_password_hash(password: str) -> str:
    salt = secrets.token_hex(16)

    pwd_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    )

    return f"{salt}${pwd_hash.hex()}"


# =========================
# DATABASE CONNECT
# =========================
client = MongoClient("mongodb://localhost:27017")
db = client["chatbot"]
users_col = db["users"]


# =========================
# CREATE ACCOUNT
# =========================
def create_user():
    username = input("Username: ").strip()

    if users_col.find_one({"username": username}):
        print("❌ User already exists!")
        return

    password = getpass.getpass("Password: ")
    role = input("Role (admin/user) [user]: ").strip() or "user"

    user = {
        "_id": f"user_{secrets.token_hex(4)}",
        "username": username,
        "password_hash": generate_password_hash(password),
        "has_face_encoding": False,
        "created_at": datetime.now(),
        "role": role
    }

    users_col.insert_one(user)
    print("✅ Account created!")


# =========================
# CHECK ACCOUNT
# =========================
def check_user():
    username = input("Username cần kiểm tra: ").strip()

    user = users_col.find_one({"username": username})

    if not user:
        print("❌ Không tìm thấy user")
        return

    print("\n✅ Thông tin tài khoản:")
    print(f"ID: {user['_id']}")
    print(f"Username: {user['username']}")
    print(f"Role: {user.get('role','user')}")
    print(f"Face Encoding: {user.get('has_face_encoding', False)}")
    print(f"Created: {user.get('created_at')}")


# =========================
# UPDATE PASSWORD (NEW)
# =========================
def update_password():
    print("\n🔑 CẬP NHẬT MẬT KHẨU")

    username = input("Username: ").strip()
    new_password = getpass.getpass("Mật khẩu mới: ")

    if not username or not new_password:
        print("❌ Không được để trống!")
        return

    user = users_col.find_one({"username": username})

    if not user:
        print("❌ Tài khoản không tồn tại!")
        return

    hash_value = generate_password_hash(new_password)

    users_col.update_one(
        {"username": username},
        {"$set": {"password_hash": hash_value}}
    )

    print("✅ Cập nhật mật khẩu thành công!")


# =========================
# LIST USERS
# =========================
def list_users():
    print("\n👥 Danh sách tài khoản:")

    for user in users_col.find().sort("created_at", 1):
        role = user.get("role", "user")
        has_face = "✅" if user.get("has_face_encoding") else "❌"

        print(
            f" - {user['username']:<12}"
            f"({user['_id']}) "
            f"[{role}] Face: {has_face}"
        )


# =========================
# MENU
# =========================
def main():
    while True:
        print("\n" + "=" * 60)
        print(" USER MANAGEMENT SYSTEM")
        print("=" * 60)
        print("1. Tạo tài khoản")
        print("2. Kiểm tra tài khoản")
        print("3. Danh sách tài khoản")
        print("4. Cập nhật mật khẩu")
        print("5. Thoát")

        choice = input("Chọn: ")

        if choice == "1":
            create_user()
        elif choice == "2":
            check_user()
        elif choice == "3":
            list_users()
        elif choice == "4":
            update_password()
        elif choice == "5":
            break
        else:
            print("❌ Lựa chọn không hợp lệ!")


if __name__ == "__main__":
    main()