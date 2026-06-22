# -*- coding: utf-8 -*-
# SHOP BAN FILE FREE FIRE - FULL TỰ ĐỘNG + ADMIN + ĐỔI MK QUA EMAIL
# Công nghệ: Flask + SQLite + PayOS (thanh toán) + Gửi email
# Tích hợp: Bank QR, Thẻ cào (mô phỏng), Tự động gửi file sau thanh toán

from flask import Flask, render_template_string, request, redirect, url_for, session, flash, jsonify
from flask_mail import Mail, Message
import hashlib
import json
import os
import datetime
import random
import string
import sqlite3
import requests
import hmac
import time

app = Flask(__name__)
app.secret_key = "freefire_shop_secret_key_2026"

# === CẤU HÌNH EMAIL (gửi link đổi mật khẩu) ===
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'  # Thay bằng email của bạn
app.config['MAIL_PASSWORD'] = 'your_app_password'     # Thay bằng mật khẩu ứng dụng Gmail
app.config['MAIL_DEFAULT_SENDER'] = 'your_email@gmail.com'
mail = Mail(app)

# === CẤU HÌNH PAYOS (thanh toán tự động) ===
PAYOS_CLIENT_ID = "your-client-id"       # Lấy từ dashboard PayOS
PAYOS_API_KEY = "your-api-key"
PAYOS_CHECKSUM_KEY = "your-checksum-key"
PAYOS_URL = "https://api.payos.vn/v2/payment-requests"

# === CẤU HÌNH SHOP ===
SHOP_NAME = "FF SHOP PRO - BÁN FILE FREE FIRE"
SHOP_OWNER = "Admin"
ZALO = "0362281930"
CURRENCY = "VND"

# === KHỞI TẠO DATABASE SQLITE ===
DB_FILE = "shop_ff.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Bảng sản phẩm
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT,
        price REAL,
        stock INTEGER,
        sold INTEGER DEFAULT 0,
        description TEXT,
        features TEXT,
        platform TEXT,
        warranty TEXT,
        file_link TEXT,
        status TEXT,
        created TEXT
    )''')
    # Bảng đơn hàng
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        product_id TEXT,
        product_name TEXT,
        quantity INTEGER,
        total REAL,
        buyer TEXT,
        phone TEXT,
        payment_method TEXT,
        status TEXT,
        file_link TEXT,
        created TEXT
    )''')
    # Bảng người dùng
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        password_hash TEXT,
        full_name TEXT,
        phone TEXT,
        role TEXT,
        status TEXT,
        reset_token TEXT,
        reset_expiry TEXT,
        created TEXT,
        last_login TEXT
    )''')
    # Bảng thẻ cào (lưu lịch sử nạp)
    c.execute('''CREATE TABLE IF NOT EXISTS card_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        card_type TEXT,
        card_code TEXT,
        card_serial TEXT,
        amount REAL,
        status TEXT,
        created TEXT
    )''')
    conn.commit()
    conn.close()

# === HÀM TẠO KẾT NỐI DB ===
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# === HÀM BĂM MẬT KHẨU ===
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_random_id(prefix=""):
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}{random_str}"

# === QUẢN LÝ SẢN PHẨM ===
def add_product_db(name, category, price, stock, description, features="", platform="", warranty="", file_link=""):
    conn = get_db()
    pid = generate_random_id("FF")
    product = {
        "id": pid,
        "name": name,
        "category": category,
        "price": float(price),
        "stock": int(stock),
        "sold": 0,
        "description": description,
        "features": features,
        "platform": platform,
        "warranty": warranty,
        "file_link": file_link,
        "status": "Sẵn hàng" if int(stock) > 0 else "Hết hàng",
        "created": str(datetime.datetime.now())
    }
    conn.execute('''INSERT INTO products VALUES (
        :id, :name, :category, :price, :stock, :sold, :description,
        :features, :platform, :warranty, :file_link, :status, :created
    )''', product)
    conn.commit()
    conn.close()
    return pid

def get_products():
    conn = get_db()
    products = conn.execute('SELECT * FROM products ORDER BY created DESC').fetchall()
    conn.close()
    return [dict(row) for row in products]

def get_product_by_id(pid):
    conn = get_db()
    row = conn.execute('SELECT * FROM products WHERE id = ?', (pid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def update_product_stock(pid, quantity):
    conn = get_db()
    product = get_product_by_id(pid)
    if not product:
        conn.close()
        return False
    new_stock = product['stock'] - quantity
    new_sold = product['sold'] + quantity
    status = "Sẵn hàng" if new_stock > 0 else "Hết hàng"
    conn.execute('UPDATE products SET stock = ?, sold = ?, status = ? WHERE id = ?',
                 (new_stock, new_sold, status, pid))
    conn.commit()
    conn.close()
    return True

def delete_product_db(pid):
    conn = get_db()
    conn.execute('DELETE FROM products WHERE id = ?', (pid,))
    conn.commit()
    conn.close()

def update_product_db(pid, name, category, price, stock, description, features, platform, warranty, file_link):
    conn = get_db()
    status = "Sẵn hàng" if int(stock) > 0 else "Hết hàng"
    conn.execute('''UPDATE products SET 
        name = ?, category = ?, price = ?, stock = ?, description = ?,
        features = ?, platform = ?, warranty = ?, file_link = ?, status = ?
        WHERE id = ?''', 
        (name, category, float(price), int(stock), description, features, platform, warranty, file_link, status, pid))
    conn.commit()
    conn.close()
    return True

# === QUẢN LÝ ĐƠN HÀNG ===
def create_order_db(product_id, quantity, buyer_name, phone, payment_method, file_link=""):
    product = get_product_by_id(product_id)
    if not product or product['stock'] < quantity:
        return None
    
    # Trừ stock
    if not update_product_stock(product_id, quantity):
        return None
    
    order_id = generate_random_id("ORD")
    total = product['price'] * quantity
    order = {
        "order_id": order_id,
        "product_id": product_id,
        "product_name": product['name'],
        "quantity": quantity,
        "total": total,
        "buyer": buyer_name,
        "phone": phone,
        "payment_method": payment_method,
        "status": "Chờ thanh toán",
        "file_link": file_link or product['file_link'],
        "created": str(datetime.datetime.now())
    }
    conn = get_db()
    conn.execute('''INSERT INTO orders VALUES (
        :order_id, :product_id, :product_name, :quantity, :total,
        :buyer, :phone, :payment_method, :status, :file_link, :created
    )''', order)
    conn.commit()
    conn.close()
    return order

def get_orders_by_phone(phone):
    conn = get_db()
    rows = conn.execute('SELECT * FROM orders WHERE phone = ? ORDER BY created DESC', (phone,)).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_all_orders():
    conn = get_db()
    rows = conn.execute('SELECT * FROM orders ORDER BY created DESC').fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_order_status_db(order_id, status):
    conn = get_db()
    conn.execute('UPDATE orders SET status = ? WHERE order_id = ?', (status, order_id))
    conn.commit()
    conn.close()
    return True

def delete_order_db(order_id):
    conn = get_db()
    conn.execute('DELETE FROM orders WHERE order_id = ?', (order_id,))
    conn.commit()
    conn.close()

# === QUẢN LÝ NGƯỜI DÙNG ===
def register_user_db(username, email, password, full_name="", phone="", role="user"):
    conn = get_db()
    # Kiểm tra tồn tại
    exist = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
    if exist:
        conn.close()
        return False
    user_id = generate_random_id("USR")
    user = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "password_hash": hash_password(password),
        "full_name": full_name,
        "phone": phone,
        "role": role,
        "status": "active",
        "reset_token": "",
        "reset_expiry": "",
        "created": str(datetime.datetime.now()),
        "last_login": None
    }
    conn.execute('''INSERT INTO users VALUES (
        :user_id, :username, :email, :password_hash, :full_name,
        :phone, :role, :status, :reset_token, :reset_expiry, :created, :last_login
    )''', user)
    conn.commit()
    conn.close()
    return True

def login_user_db(username_or_email, password):
    conn = get_db()
    user = conn.execute('''SELECT * FROM users WHERE (username = ? OR email = ?) AND status = 'active' ''', 
                        (username_or_email, username_or_email)).fetchone()
    conn.close()
    if user and user['password_hash'] == hash_password(password):
        # Cập nhật last_login
        conn = get_db()
        conn.execute('UPDATE users SET last_login = ? WHERE user_id = ?', 
                     (str(datetime.datetime.now()), user['user_id']))
        conn.commit()
        conn.close()
        return dict(user)
    return None

def get_user_by_email(email):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def update_user_password_db(user_id, new_password):
    conn = get_db()
    conn.execute('UPDATE users SET password_hash = ? WHERE user_id = ?', 
                 (hash_password(new_password), user_id))
    conn.commit()
    conn.close()
    return True

def set_reset_token_db(email, token, expiry):
    conn = get_db()
    conn.execute('UPDATE users SET reset_token = ?, reset_expiry = ? WHERE email = ?', 
                 (token, expiry, email))
    conn.commit()
    conn.close()

def get_user_by_reset_token(token):
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE reset_token = ? AND reset_expiry > ?', 
                        (token, str(datetime.datetime.now()))).fetchone()
    conn.close()
    return dict(user) if user else None

def get_all_users():
    conn = get_db()
    rows = conn.execute('SELECT * FROM users ORDER BY created DESC').fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_user_role_db(user_id, role):
    conn = get_db()
    conn.execute('UPDATE users SET role = ? WHERE user_id = ?', (role, user_id))
    conn.commit()
    conn.close()

def toggle_user_status_db(user_id):
    conn = get_db()
    user = get_user_by_id(user_id)
    if not user:
        conn.close()
        return False
    new_status = "banned" if user['status'] == "active" else "active"
    conn.execute('UPDATE users SET status = ? WHERE user_id = ?', (new_status, user_id))
    conn.commit()
    conn.close()
    return True

def delete_user_db(user_id):
    conn = get_db()
    conn.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

# === QUẢN LÝ THẺ CÀO (mô phỏng tự động nạp) ===
def process_card_payment(user_id, card_type, card_code, card_serial, amount):
    # Mô phỏng: kiểm tra mã thẻ hợp lệ (demo)
    # Trong thực tế, gọi API nhà mạng để xác thực
    if len(card_code) < 6 or len(card_serial) < 6:
        return {"success": False, "message": "Mã thẻ hoặc serial không hợp lệ"}
    
    # Giả lập tự động nạp thành công
    conn = get_db()
    conn.execute('''INSERT INTO card_history (user_id, card_type, card_code, card_serial, amount, status, created)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                 (user_id, card_type, card_code, card_serial, amount, "success", str(datetime.datetime.now())))
    conn.commit()
    conn.close()
    return {"success": True, "message": f"Nạp {amount} VND thành công!"}

# === HÀM GỬI EMAIL ===
def send_reset_email(email, reset_link):
    try:
        msg = Message("Đặt lại mật khẩu - FF SHOP",
                      recipients=[email])
        msg.html = f'''
        <h2>Xin chào!</h2>
        <p>Bạn đã yêu cầu đặt lại mật khẩu cho tài khoản tại FF SHOP.</p>
        <p>Vui lòng nhấp vào link bên dưới để đặt lại mật khẩu (có hiệu lực trong 15 phút):</p>
        <p><a href="{reset_link}">{reset_link}</a></p>
        <p>Nếu bạn không yêu cầu, vui lòng bỏ qua email này.</p>
        <p>Trân trọng,<br>FF SHOP PRO</p>
        '''
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Lỗi gửi email: {e}")
        return False

def send_file_by_email(email, file_link, order_id):
    try:
        msg = Message(f"File của bạn - Đơn hàng {order_id}",
                      recipients=[email])
        msg.html = f'''
        <h2>Cảm ơn bạn đã mua hàng tại FF SHOP!</h2>
        <p>Đơn hàng <b>{order_id}</b> đã được xác nhận.</p>
        <p>Link tải file của bạn: <a href="{file_link}">{file_link}</a></p>
        <p>Lưu ý: Link có hiệu lực trong 24 giờ.</p>
        <p>Trân trọng,<br>FF SHOP PRO</p>
        '''
        mail.send(msg)
        return True
    except:
        return False

# === TÍCH HỢP PAYOS (thanh toán QR) ===
def create_payos_payment(order_id, amount, buyer_name, description="Thanh toan don hang"):
    # Tạo link thanh toán PayOS
    # Tham khảo tài liệu PayOS để biết chi tiết
    # Demo: tạo payload
    payload = {
        "orderCode": int(time.time() * 1000),
        "amount": int(amount),
        "description": description[:25],
        "buyerName": buyer_name,
        "buyerPhone": "0987654321",
        "buyerEmail": "customer@email.com",
        "items": [{"name": f"Don hang {order_id}", "quantity": 1, "price": int(amount)}],
        "returnUrl": "https://your-domain.com/payment-success",
        "cancelUrl": "https://your-domain.com/payment-cancel",
        "webhookUrl": "https://your-domain.com/webhook"
    }
    # Trong thực tế, gửi POST đến PAYOS_URL với headers và checksum
    # Demo: trả về link giả
    return {"success": True, "payment_url": f"https://payos.vn/pay/{order_id}"}

# === TEMPLATE HTML (GIAO DIỆN HIỆN ĐẠI) ===
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ shop_name }}</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
        .container { max-width: 1200px; margin: auto; background: rgba(255,255,255,0.95); border-radius: 30px; padding: 30px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); backdrop-filter: blur(10px); }
        .header { text-align: center; padding: 20px 0; border-bottom: 3px solid #764ba2; position: relative; }
        .header h1 { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-size: 2.8em; }
        .header .user-info { position: absolute; right: 20px; top: 20px; background: #f0f0f0; padding: 8px 20px; border-radius: 30px; }
        .zalo-badge { display: inline-block; background: #0088cc; color: white; padding: 8px 25px; border-radius: 30px; margin: 10px 0; font-weight: bold; }
        .menu { display: flex; flex-wrap: wrap; gap: 12px; margin: 25px 0; justify-content: center; }
        .menu a, .menu button { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px 30px; border-radius: 50px; text-decoration: none; border: none; cursor: pointer; font-weight: 600; transition: all 0.3s; box-shadow: 0 4px 15px rgba(102,126,234,0.4); }
        .menu a:hover, .menu button:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(102,126,234,0.6); }
        .menu a.admin { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
        .products { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 25px; margin-top: 30px; }
        .product-card { background: white; border-radius: 20px; padding: 20px; box-shadow: 0 8px 30px rgba(0,0,0,0.1); transition: 0.3s; border: 1px solid #eee; }
        .product-card:hover { transform: translateY(-8px); box-shadow: 0 15px 40px rgba(0,0,0,0.15); }
        .product-card h3 { color: #2c3e50; font-size: 1.3em; }
        .product-card .price { color: #e74c3c; font-size: 1.8em; font-weight: bold; }
        .product-card .stock { color: #27ae60; }
        .btn-buy { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 12px; border: none; border-radius: 50px; cursor: pointer; width: 100%; font-weight: bold; transition: 0.3s; }
        .btn-buy:hover { transform: scale(1.02); box-shadow: 0 4px 15px rgba(102,126,234,0.4); }
        .flash { padding: 15px; background: #f1c40f; border-radius: 15px; margin: 15px 0; text-align: center; font-weight: bold; color: #2c3e50; }
        .login-form { max-width: 450px; margin: 40px auto; padding: 40px; background: white; border-radius: 30px; box-shadow: 0 10px 40px rgba(0,0,0,0.1); }
        .login-form input { width: 100%; padding: 15px; margin: 10px 0; border: 2px solid #eee; border-radius: 50px; transition: 0.3s; font-size: 1em; }
        .login-form input:focus { border-color: #764ba2; outline: none; box-shadow: 0 0 0 3px rgba(118,75,162,0.2); }
        .login-form button { width: 100%; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; border-radius: 50px; cursor: pointer; font-weight: bold; font-size: 1.1em; }
        .admin-panel { background: #f8f9fa; padding: 25px; border-radius: 20px; margin: 20px 0; }
        .admin-panel input, .admin-panel textarea, .admin-panel select { width: 100%; padding: 12px; margin: 8px 0; border: 2px solid #eee; border-radius: 15px; }
        .admin-panel button { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; padding: 12px 30px; border: none; border-radius: 50px; cursor: pointer; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; background: white; border-radius: 15px; overflow: hidden; }
        th { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px; }
        td { padding: 12px; border-bottom: 1px solid #eee; }
        .btn-small { padding: 6px 15px; border: none; border-radius: 30px; cursor: pointer; font-weight: bold; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn-warning { background: #f39c12; color: white; }
        .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 2px solid #eee; color: #7f8c8d; }
        .card-payment { background: #f8f9fa; padding: 25px; border-radius: 20px; margin: 20px 0; }
        .card-payment input { width: 100%; padding: 12px; margin: 8px 0; border: 2px solid #eee; border-radius: 15px; }
        @media (max-width: 600px) { .products { grid-template-columns: 1fr; } .header h1 { font-size: 1.8em; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔥 {{ shop_name }}</h1>
            <div class="zalo-badge">📱 Zalo: {{ zalo }}</div>
            <div class="user-info">
                {% if session.user %}
                    👤 {{ session.user.full_name or session.user.username }}
                    {% if session.user.role == 'admin' %}⭐ Admin{% endif %}
                    | <a href="{{ url_for('logout') }}" style="color:#e74c3c;">Đăng xuất</a>
                {% endif %}
            </div>
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}<div class="flash">{{ messages[0] }}</div>{% endif %}
        {% endwith %}

        {% if not session.user %}
        <!-- LOGIN / REGISTER -->
        <div class="login-form">
            <h2 style="text-align:center; color:#2c3e50;">Chào mừng quay trở lại</h2>
            <form method="POST" action="{{ url_for('login') }}">
                <input type="text" name="username" placeholder="Email / Username" required>
                <input type="password" name="password" placeholder="Mật khẩu" required>
                <button type="submit">Đăng nhập</button>
            </form>
            <div style="text-align:center; margin-top:15px;">
                <a href="{{ url_for('register') }}" style="color:#764ba2;">Đăng ký tài khoản mới</a> | 
                <a href="{{ url_for('forgot_password') }}" style="color:#e74c3c;">Quên mật khẩu?</a>
            </div>
        </div>
        {% else %}
        <!-- MENU CHÍNH -->
        <div class="menu">
            <a href="{{ url_for('index') }}"><i class="fas fa-home"></i> Trang chủ</a>
            <a href="{{ url_for('category', cat='Android') }}"><i class="fab fa-android"></i> Android</a>
            <a href="{{ url_for('category', cat='iOS') }}"><i class="fab fa-apple"></i> iOS</a>
            <a href="{{ url_for('category', cat='PC') }}"><i class="fas fa-desktop"></i> PC</a>
            <a href="{{ url_for('orders') }}"><i class="fas fa-box"></i> Đơn hàng</a>
            <a href="{{ url_for('card_payment') }}"><i class="fas fa-credit-card"></i> Nạp thẻ</a>
            {% if session.user.role == 'admin' %}
                <a href="{{ url_for('admin_dashboard') }}" class="admin"><i class="fas fa-cog"></i> Quản trị</a>
            {% endif %}
        </div>

        <!-- HIỂN THỊ SẢN PHẨM -->
        <div class="products">
            {% for p in products %}
            <div class="product-card">
                <h3>{{ p.name }}</h3>
                <p>{{ p.features }}</p>
                <p style="color:#2980b9;">{{ p.warranty }}</p>
                <div class="price">{{ p.price }} {{ currency }}</div>
                <div class="stock">📦 Còn: {{ p.stock }} | Đã bán: {{ p.sold }}</div>
                <p><span style="background:#ecf0f1; padding:3px 12px; border-radius:15px;">{{ p.platform }}</span></p>
                <form method="POST" action="{{ url_for('buy') }}">
                    <input type="hidden" name="product_id" value="{{ p.id }}">
                    <input type="number" name="quantity" value="1" min="1" max="{{ p.stock }}" style="width:70px; padding:8px; border-radius:15px; border:1px solid #ddd; margin:5px 0;">
                    <button class="btn-buy" type="submit"><i class="fas fa-shopping-cart"></i> Mua ngay</button>
                </form>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="footer">
            <p>© 2025 {{ shop_name }} - Liên hệ Zalo {{ zalo }}</p>
        </div>
    </div>
</body>
</html>
"""

# ==================== ROUTES ====================
@app.route('/')
def index():
    products = get_products()
    return render_template_string(HTML_TEMPLATE, 
                                shop_name=SHOP_NAME,
                                zalo=ZALO,
                                currency=CURRENCY,
                                products=products,
                                session=session)

@app.route('/category/<cat>')
def category(cat):
    products = [p for p in get_products() if p['category'].lower() == cat.lower()]
    return render_template_string(HTML_TEMPLATE,
                                shop_name=SHOP_NAME,
                                zalo=ZALO,
                                currency=CURRENCY,
                                products=products,
                                session=session)

# === ĐĂNG NHẬP / ĐĂNG KÝ ===
@app.route('/login', methods=['POST'])
def login():
    username = request.form.get('username')
    password = request.form.get('password')
    user = login_user_db(username, password)
    if user:
        session['user'] = user
        flash('Đăng nhập thành công!')
    else:
        flash('Sai tên đăng nhập hoặc mật khẩu!')
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name', '')
        phone = request.form.get('phone', '')
        if register_user_db(username, email, password, full_name, phone):
            flash('Đăng ký thành công! Vui lòng đăng nhập.')
        else:
            flash('Tên đăng nhập hoặc email đã tồn tại!')
        return redirect(url_for('index'))
    return '''
    <div style="max-width:450px; margin:40px auto; padding:40px; background:white; border-radius:30px; box-shadow:0 10px 40px rgba(0,0,0,0.1);">
        <h2 style="text-align:center; color:#2c3e50;">Đăng ký tài khoản</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Tên đăng nhập" required style="width:100%; padding:15px; margin:10px 0; border:2px solid #eee; border-radius:50px;">
            <input type="email" name="email" placeholder="Email" required style="width:100%; padding:15px; margin:10px 0; border:2px solid #eee; border-radius:50px;">
            <input type="password" name="password" placeholder="Mật khẩu" required style="width:100%; padding:15px; margin:10px 0; border:2px solid #eee; border-radius:50px;">
            <input type="text" name="full_name" placeholder="Họ tên" style="width:100%; padding:15px; margin:10px 0; border:2px solid #eee; border-radius:50px;">
            <input type="text" name="phone" placeholder="Số điện thoại" style="width:100%; padding:15px; margin:10px 0; border:2px solid #eee; border-radius:50px;">
            <button type="submit" style="width:100%; padding:15px; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:white; border:none; border-radius:50px; cursor:pointer; font-weight:bold;">Đăng ký</button>
        </form>
        <p style="text-align:center; margin-top:15px;"><a href="/">Quay lại trang chủ</a></p>
    </div>
    '''

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Đã đăng xuất.')
    return redirect(url_for('index'))

# === QUÊN MẬT KHẨU - GỬI EMAIL ===
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = get_user_by_email(email)
        if not user:
            flash('Email không tồn tại trong hệ thống!')
            return redirect(url_for('forgot_password'))
        
        # Tạo token reset
        token = hashlib.sha256(f"{email}{datetime.datetime.now()}".encode()).hexdigest()[:32]
        expiry = str(datetime.datetime.now() + datetime.timedelta(minutes=15))
        set_reset_token_db(email, token, expiry)
        
        # Gửi email
        reset_link = f"{request.host_url}reset-password/{token}"
        if send_reset_email(email, reset_link):
            flash('Email đặt lại mật khẩu đã được gửi! Vui lòng kiểm tra hộp thư.')
        else:
            flash('Lỗi gửi email! Vui lòng thử lại sau.')
        return redirect(url_for('index'))
    
    return '''
    <div style="max-width:450px; margin:40px auto; padding:40px; background:white; border-radius:30px; box-shadow:0 10px 40px rgba(0,0,0,0.1);">
        <h2 style="text-align:center; color:#2c3e50;">Quên mật khẩu</h2>
        <p>Nhập email của bạn để nhận link đặt lại mật khẩu.</p>
        <form method="POST">
            <input type="email" name="email" placeholder="Email của bạn" required style="width:100%; padding:15px; margin:10px 0; border:2px solid #eee; border-radius:50px;">
            <button type="submit" style="width:100%; padding:15px; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:white; border:none; border-radius:50px; cursor:pointer; font-weight:bold;">Gửi link reset</button>
        </form>
        <p style="text-align:center; margin-top:15px;"><a href="/">Quay lại trang chủ</a></p>
    </div>
    '''

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = get_user_by_reset_token(token)
    if not user:
        flash('Link không hợp lệ hoặc đã hết hạn!')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        new_password = request.form.get('password')
        if len(new_password) < 6:
            flash('Mật khẩu phải có ít nhất 6 ký tự!')
            return redirect(url_for('reset_password', token=token))
        update_user_password_db(user['user_id'], new_password)
        # Xóa token
        set_reset_token_db(user['email'], '', '')
        flash('Đặt lại mật khẩu thành công! Vui lòng đăng nhập.')
        return redirect(url_for('index'))
    
    return '''
    <div style="max-width:450px; margin:40px auto; padding:40px; background:white; border-radius:30px; box-shadow:0 10px 40px rgba(0,0,0,0.1);">
        <h2 style="text-align:center; color:#2c3e50;">Đặt lại mật khẩu</h2>
        <form method="POST">
            <input type="password" name="password" placeholder="Mật khẩu mới (tối thiểu 6 ký tự)" required style="width:100%; padding:15px; margin:10px 0; border:2px solid #eee; border-radius:50px;">
            <button type="submit" style="width:100%; padding:15px; background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:white; border:none; border-radius:50px; cursor:pointer; font-weight:bold;">Cập nhật mật khẩu</button>
        </form>
    </div>
    '''

# === MUA HÀNG ===
@app.route('/buy', methods=['POST'])
def buy():
    if 'user' not in session:
        flash('Vui lòng đăng nhập để mua hàng!')
        return redirect(url_for('index'))
    
    product_id = request.form.get('product_id')
    try:
        quantity = int(request.form.get('quantity', 1))
    except:
        quantity = 1
    
    user = session['user']
    order = create_order_db(product_id, quantity, user['full_name'] or user['username'], 
                           user.get('phone', 'Chưa cập nhật'), 'PayOS')
    
    if not order:
        flash('Lỗi đặt hàng! Kiểm tra số lượng hoặc sản phẩm.')
        return redirect(url_for('index'))
    
    # Tạo link thanh toán PayOS
    payment = create_payos_payment(order['order_id'], order['total'], user['full_name'])
    if payment['success']:
        flash(f'Đặt hàng thành công! Mã đơn: {order["order_id"]}. Vui lòng thanh toán qua link bên dưới.')
        return redirect(payment['payment_url'])
    else:
        flash(f'Đặt hàng thành công! Mã đơn: {order["order_id"]}. Vui lòng thanh toán qua Zalo {ZALO}.')
        return redirect(url_for('index'))

# === ĐƠN HÀNG CỦA TÔI ===
@app.route('/orders')
def orders():
    if 'user' not in session:
        return redirect(url_for('index'))
    
    user_orders = get_orders_by_phone(session['user']['phone'])
    html = '''
    <div style="max-width:900px; margin:20px auto; padding:30px; background:white; border-radius:30px; box-shadow:0 10px 40px rgba(0,0,0,0.1);">
        <h2>📦 Đơn hàng của tôi</h2>
        <a href="/">← Quay lại trang chủ</a>
        <div style="margin-top:20px;">
    '''
    if not user_orders:
        html += '<p>Bạn chưa có đơn hàng nào.</p>'
    else:
        for o in user_orders:
            html += f'''
            <div style="border-bottom:1px solid #eee; padding:15px 0;">
                <b>{o['order_id']}</b> - {o['product_name']} x{o['quantity']} - <b>{o['total']} {CURRENCY}</b>
                <br>Trạng thái: <b>{o['status']}</b> | Ngày: {o['created']}
                <br>File: <a href="{o['file_link']}" target="_blank">{o['file_link'] or 'Chưa có'}</a>
            </div>
            '''
    html += '</div></div>'
    return html

# === NẠP THẺ CÀO TỰ ĐỘNG ===
@app.route('/card-payment', methods=['GET', 'POST'])
def card_payment():
    if 'user' not in session:
        flash('Vui lòng đăng nhập để nạp thẻ!')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        card_type = request.form.get('card_type')
        card_code = request.form.get('card_code')
        card_serial = request.form.get('card_serial')
        amount = float(request.form.get('amount', 0))
        
        result = process_card_payment(session['user']['user_id'], card_type, card_code, card_serial, amount)
        flash(result['message'])
        return redirect(url_for('card_payment'))
    
    return '''
    <div style="max-width:550px; margin:30px auto; padding:30px; background:white; border-radius:30px; box-shadow:0 10px 40px rgba(0,0,0,0.1);">
        <h2>💳 Nạp thẻ cào tự động</h2>
        <p>Nạp thẻ Viettel, Mobifone, VinaPhone để cộng tiền vào tài khoản.</p>
        <form method="POST">
            <select name="card_type" style="width:100%; padding:15px; margin:10px 0; border:2px solid #eee; border-radius:50px;">
                <option value="viettel">Viettel</option>
                <option value="mobifone">Mobifone</option>
                <option value="vinaphone">VinaPhone</option>
            </select>
            <input type="text" name="card_code" placeholder="Mã thẻ" required style="width:100%; padding:15px; margin:10px 0; border:2px solid #eee; border-radius:50px;">
            <input type="text" name="card_serial" placeholder="Số serial" required style="width:100%; padding:15px; margin:10px 0; border:2px solid #eee; border-radius:50px;">
            <input type="number" name="amount" placeholder="Mệnh giá (VND)" required style="width:100%; padding:15px; margin:10px 0; border:2px solid #eee; border-radius:50px;">
            <button type="submit" style="width:100%; padding:15px; background:linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color:white; border:none; border-radius:50px; cursor:pointer; font-weight:bold;">Nạp thẻ</button>
        </form>
        <p style="text-align:center; margin-top:15px;"><a href="/">Quay lại trang chủ</a></p>
    </div>
    '''

# ==================== ADMIN DASHBOARD ====================
@app.route('/admin')
def admin_dashboard():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash('Bạn cần quyền Admin!')
        return redirect(url_for('index'))
    
    users = get_all_users()
    orders = get_all_orders()
    products = get_products()
    
    html = '''
    <div style="max-width:1200px; margin:20px auto; padding:30px; background:white; border-radius:30px; box-shadow:0 10px 40px rgba(0,0,0,0.1);">
        <h2>⚙️ Admin Dashboard</h2>
        <a href="/">← Trang chủ</a>
        <div style="display:flex; gap:20px; margin:20px 0; flex-wrap:wrap;">
            <div style="background:linear-gradient(135deg, #667eea 0%, #764ba2 100%); color:white; padding:25px; border-radius:20px; flex:1; text-align:center;">
                <h3>Sản phẩm</h3>
                <p style="font-size:2em;">''' + str(len(products)) + '''</p>
                <a href="/admin/products" style="color:white; text-decoration:underline;">Quản lý</a>
            </div>
            <div style="background:linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); color:white; padding:25px; border-radius:20px; flex:1; text-align:center;">
                <h3>Đơn hàng</h3>
                <p style="font-size:2em;">''' + str(len(orders)) + '''</p>
                <a href="/admin/orders" style="color:white; text-decoration:underline;">Quản lý</a>
            </div>
            <div style="background:linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color:white; padding:25px; border-radius:20px; flex:1; text-align:center;">
                <h3>Người dùng</h3>
                <p style="font-size:2em;">''' + str(len(users)) + '''</p>
                <a href="/admin/users" style="color:white; text-decoration:underline;">Quản lý</a>
            </div>
        </div>
    </div>
    '''
    return html

# === ADMIN: QUẢN LÝ SẢN PHẨM ===
@app.route('/admin/products', methods=['GET', 'POST'])
def admin_products():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash('Bạn cần quyền Admin!')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            name = request.form.get('name')
            category = request.form.get('category')
            try:
                price = float(request.form.get('price'))
                stock = int(request.form.get('stock'))
            except:
                flash('Giá hoặc số lượng không hợp lệ!')
                return redirect(url_for('admin_products'))
            description = request.form.get('description', '')
            features = request.form.get('features', '')
            platform = request.form.get('platform', '')
            warranty = request.form.get('warranty', '')
            file_link = request.form.get('file_link', '')
            add_product_db(name, category, price, stock, description, features, platform, warranty, file_link)
            flash('Thêm sản phẩm thành công!')
        elif action == 'delete':
            pid = request.form.get('pid')
            delete_product_db(pid)
            flash('Xóa sản phẩm thành công!')
        elif action == 'edit':
            pid = request.form.get('pid')
            name = request.form.get('name')
            category = request.form.get('category')
            try:
                price = float(request.form.get('price'))
                stock = int(request.form.get('stock'))
            except:
                flash('Giá hoặc số lượng không hợp lệ!')
                return redirect(url_for('admin_products'))
            description = request.form.get('description', '')
            features = request.form.get('features', '')
            platform = request.form.get('platform', '')
            warranty = request.form.get('warranty', '')
            file_link = request.form.get('file_link', '')
            update_product_db(pid, name, category, price, stock, description, features, platform, warranty, file_link)
            flash('Cập nhật sản phẩm thành công!')
        return redirect(url_for('admin_products'))
    
    products = get_products()
    html = '''
    <div style="max-width:1200px; margin:20px auto; padding:30px; background:white; border-radius:30px; box-shadow:0 10px 40px rgba(0,0,0,0.1);">
        <h2>📦 Quản lý sản phẩm</h2>
        <a href="/admin">← Dashboard</a> | <a href="/">Trang chủ</a>
        
        <div class="admin-panel">
            <h3>➕ Thêm sản phẩm mới</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add">
                <input type="text" name="name" placeholder="Tên sản phẩm" required>
                <input type="text" name="category" placeholder="Danh mục (Android/iOS/PC)" required>
                <input type="number" name="price" placeholder="Giá (VND)" required>
                <input type="number" name="stock" placeholder="Số lượng" required>
                <textarea name="description" placeholder="Mô tả"></textarea>
                <input type="text" name="features" placeholder="Tính năng nổi bật">
                <input type="text" name="platform" placeholder="Nền tảng">
                <input type="text" name="warranty" placeholder="Bảo hành">
                <input type="text" name="file_link" placeholder="Link file (Google Drive...)" style="width:100%;">
                <button type="submit">Thêm sản phẩm</button>
            </form>
        </div>
        
        <h3>Danh sách sản phẩm</h3>
        <table>
            <tr><th>ID</th><th>Tên</th><th>Danh mục</th><th>Giá</th><th>Tồn</th><th>Đã bán</th><th>Hành động</th></tr>
    '''
    for p in products:
        html += f'''
        <tr>
            <td>{p['id'][:8]}</td>
            <td>{p['name']}</td>
            <td>{p['category']}</td>
            <td>{p['price']} {CURRENCY}</td>
            <td>{p['stock']}</td>
            <td>{p['sold']}</td>
            <td>
                <form method="POST" style="display:inline-block;">
                    <input type="hidden" name="action" value="delete">
                    <input type="hidden" name="pid" value="{p['id']}">
                    <button type="submit" class="btn-small btn-danger" onclick="return confirm('Xóa sản phẩm này?')">Xóa</button>
                </form>
                <button class="btn-small btn-warning" onclick="editProduct('{p['id']}','{p['name']}','{p['category']}','{p['price']}','{p['stock']}','{p['description']}','{p['features']}','{p['platform']}','{p['warranty']}','{p['file_link']}')">Sửa</button>
            </td>
        </tr>
        '''
    
    html += '''
        </table>
    </div>
    <script>
    function editProduct(id, name, category, price, stock, description, features, platform, warranty, file_link) {
        var form = document.createElement('form');
        form.method = 'POST';
        form.innerHTML = `
            <input type="hidden" name="action" value="edit">
            <input type="hidden" name="pid" value="${id}">
            <input type="text" name="name" value="${name}" placeholder="Tên sản phẩm" required>
            <input type="text" name="category" value="${category}" placeholder="Danh mục" required>
            <input type="number" name="price" value="${price}" placeholder="Giá" required>
            <input type="number" name="stock" value="${stock}" placeholder="Số lượng" required>
            <textarea name="description" placeholder="Mô tả">${description}</textarea>
            <input type="text" name="features" value="${features}" placeholder="Tính năng">
            <input type="text" name="platform" value="${platform}" placeholder="Nền tảng">
            <input type="text" name="warranty" value="${warranty}" placeholder="Bảo hành">
            <input type="text" name="file_link" value="${file_link}" placeholder="Link file">
            <button type="submit" class="btn-small btn-success">Cập nhật</button>
            <button type="button" class="btn-small btn-danger" onclick="this.parentElement.remove()">Hủy</button>
        `;
        var row = event.target.closest('tr');
        row.parentNode.insertBefore(form, row.nextSibling);
    }
    </script>
    '''
    return html

# === ADMIN: QUẢN LÝ ĐƠN HÀNG ===
@app.route('/admin/orders', methods=['GET', 'POST'])
def admin_orders():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash('Bạn cần quyền Admin!')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        order_id = request.form.get('order_id')
        if action == 'update_status':
            new_status = request.form.get('status')
            update_order_status_db(order_id, new_status)
            flash('Cập nhật trạng thái đơn hàng thành công!')
        elif action == 'delete':
            delete_order_db(order_id)
            flash('Xóa đơn hàng thành công!')
        return redirect(url_for('admin_orders'))
    
    orders = get_all_orders()
    html = '''
    <div style="max-width:1200px; margin:20px auto; padding:30px; background:white; border-radius:30px; box-shadow:0 10px 40px rgba(0,0,0,0.1);">
        <h2>📋 Quản lý đơn hàng</h2>
        <a href="/admin">← Dashboard</a> | <a href="/">Trang chủ</a>
        
        <h3>Danh sách đơn hàng</h3>
        <table>
            <tr><th>Mã đơn</th><th>Sản phẩm</th><th>Số lượng</th><th>Tổng</th><th>Trạng thái</th><th>Người mua</th><th>Hành động</th></tr>
    '''
    for o in orders:
        html += f'''
        <tr>
            <td>{o['order_id']}</td>
            <td>{o['product_name']}</td>
            <td>{o['quantity']}</td>
            <td>{o['total']} {CURRENCY}</td>
            <td>
                <form method="POST" style="display:inline-block;">
                    <input type="hidden" name="action" value="update_status">
                    <input type="hidden" name="order_id" value="{o['order_id']}">
                    <select name="status" onchange="this.form.submit()">
                        <option value="Chờ thanh toán" {"selected" if o['status']=='Chờ thanh toán' else ""}>Chờ thanh toán</option>
                        <option value="Đã thanh toán" {"selected" if o['status']=='Đã thanh toán' else ""}>Đã thanh toán</option>
                        <option value="Đã giao" {"selected" if o['status']=='Đã giao' else ""}>Đã giao</option>
                        <option value="Hủy" {"selected" if o['status']=='Hủy' else ""}>Hủy</option>
                    </select>
                </form>
            </td>
            <td>{o['buyer']} - {o['phone']}</td>
            <td>
                <form method="POST" style="display:inline-block;">
                    <input type="hidden" name="action" value="delete">
                    <input type="hidden" name="order_id" value="{o['order_id']}">
                    <button type="submit" class="btn-small btn-danger" onclick="return confirm('Xóa đơn hàng này?')">Xóa</button>
                </form>
            </td>
        </tr>
        '''
    
    html += '''
        </table>
    </div>
    '''
    return html

# === ADMIN: QUẢN LÝ NGƯỜI DÙNG ===
@app.route('/admin/users', methods=['GET', 'POST'])
def admin_users():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash('Bạn cần quyền Admin!')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id')
        if action == 'delete':
            delete_user_db(user_id)
            flash('Xóa người dùng thành công!')
        elif action == 'change_role':
            new_role = request.form.get('role')
            update_user_role_db(user_id, new_role)
            flash('Cập nhật vai trò thành công!')
        elif action == 'toggle_status':
            toggle_user_status_db(user_id)
            flash('Cập nhật trạng thái thành công!')
        return redirect(url_for('admin_users'))
    
    users = get_all_users()
    html = '''
    <div style="max-width:1200px; margin:20px auto; padding:30px; background:white; border-radius:30px; box-shadow:0 10px 40px rgba(0,0,0,0.1);">
        <h2>👥 Quản lý người dùng</h2>
        <a href="/admin">← Dashboard</a> | <a href="/">Trang chủ</a>
        
        <h3>Danh sách người dùng</h3>
        <table>
            <tr><th>ID</th><th>Tên đăng nhập</th><th>Email</th><th>Họ tên</th><th>Vai trò</th><th>Trạng thái</th><th>Hành động</th></tr>
    '''
    for u in users:
        html += f'''
        <tr>
            <td>{u['user_id'][:8]}</td>
            <td>{u['username']}</td>
            <td>{u['email']}</td>
            <td>{u['full_name'] or '---'}</td>
            <td>
                <form method="POST" style="display:inline-block;">
                    <input type="hidden" name="action" value="change_role">
                    <input type="hidden" name="user_id" value="{u['user_id']}">
                    <select name="role" onchange="this.form.submit()">
                        <option value="user" {"selected" if u['role']=='user' else ""}>User</option>
                        <option value="admin" {"selected" if u['role']=='admin' else ""}>Admin</option>
                    </select>
                </form>
            </td>
            <td>
                <form method="POST" style="display:inline-block;">
                    <input type="hidden" name="action" value="toggle_status">
                    <input type="hidden" name="user_id" value="{u['user_id']}">
                    <button type="submit" class="btn-small {"btn-danger" if u['status']=='banned' else "btn-success"}">
                        {"Ban" if u['status']=='active' else "Mở khóa"}
                    </button>
                </form>
            </td>
            <td>
                <form method="POST" style="display:inline-block;">
                    <input type="hidden" name="action" value="delete">
                    <input type="hidden" name="user_id" value="{u['user_id']}">
                    <button type="submit" class="btn-small btn-danger" onclick="return confirm('Xóa người dùng này?')">Xóa</button>
                </form>
            </td>
        </tr>
        '''
    
    html += '''
        </table>
    </div>
    '''
    return html

# === WEBHOOK PAYOS (nhận thông báo thanh toán) ===
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    # Xác minh chữ ký PayOS (nếu có)
    # Cập nhật trạng thái đơn hàng khi thanh toán thành công
    if data and data.get('status') == 'PAID':
        order_id = data.get('orderCode')
        # Tìm đơn hàng theo mã (cần map orderCode với order_id)
        # Cập nhật status = "Đã thanh toán" và gửi file tự động
        # send_file_by_email(user_email, file_link, order_id)
        pass
    return jsonify({"success": True})

# ==================== KHỞI TẠO ====================
def init_sample_data():
    init_db()
    # Tạo admin mặc định nếu chưa có
    conn = get_db()
    admin = conn.execute('SELECT * FROM users WHERE username = "admin"').fetchone()
    conn.close()
    if not admin:
        register_user_db("admin", "admin@ffshop.com", "admin123", "Administrator", "0988888888", "admin")
    
    # Tạo sản phẩm mẫu nếu chưa có
    if not get_products():
        sample_products = [
            ("Pixel 1.0", "Android", 350000, 10, "Nhiều Chức Năng Hot", "Full Đỏ Dễ Dàng Với AimLegit", "Android", "An Toàn Acc Chính", "https://drive.google.com/file/pixel1"),
            ("Aim Proxy", "iOS", 0, 6, "Kéo Là Đỏ", "Đi Rank Phòng Đều Ok", "iOS", "", "https://drive.google.com/file/aimproxy"),
            ("AimBot PC", "PC", 0, 9, "Esp,Aimbot,Ai player", "An Toàn Trên Acc Chính", "PC", "", "https://drive.google.com/file/aimbotpc"),
            ("Migul Pro", "iOS", 0, 9, "Nhiều Chức Năng", "Antiban, Chơi Acc Chính", "iOS", "", "https://drive.google.com/file/migul"),
        ]
        for name, cat, price, stock, desc, features, platform, warranty, file_link in sample_products:
            add_product_db(name, cat, price, stock, desc, features, platform, warranty, file_link)

init_sample_data()

# === DÙNG CHO PRODUCTION ===
application = app

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=10000)
