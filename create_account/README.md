# 📝 Quản Lý Tài Khoản

## 🚀 Hướng dẫn sử dụng

### 1️⃣ **Xem danh sách tài khoản**
```bash
python list_users.py
```

Output:
```
👥 DANH SÁCH TÀI KHOẢN
==============================================================================
STT   Username        User ID                                  Role      Face
--------------------------------------------------------------
1     admin           550e8400-e29b-41d4-a716-44...           admin     ❌ No
2     john            550e8400-e29b-41d4-a716-45...           user      ❌ No
3     alice           550e8400-e29b-41d4-a716-46...           user      ❌ No
==============================================================================
Tổng: 3 tài khoản
```

### 2️⃣ **Tạo tài khoản mới**
```bash
python create_user.py
```

Nhập:
```
Username: john
Password: john123
```

### 3️⃣ **Cập nhật mật khẩu**
```bash
python update_password.py
```

Nhập:
```
Username cần cập nhật: admin
Mật khẩu mới: 123456
```

## 📋 Cấu trúc Database

**Collection: users**
```javascript
{
  _id: "user_id",
  username: "john",
  password_hash: "salt$hash_value",
  has_face_encoding: false,
  created_at: timestamp,
  role: "user"  // "admin" hoặc "user"
}
```

## 🔍 Kiểm tra trong MongoDB Compass

1. Mở **MongoDB Compass**
2. Kết nối: `mongodb://localhost:27017`
3. Chọn database: **chatbot**
4. Chọn collection: **users**
5. Xem danh sách tài khoản

## ⚠️ Lưu ý

- **Password hash**: Không phải plaintext, là kết quả của PBKDF2-SHA256
- **User ID**: Tự động tạo UUID khi tạo tài khoản mới
- **Thứ tự**: Theo `created_at` (thời gian tạo)
- **Face encoding**: `true` nếu user đã đăng ký khuôn mặt
