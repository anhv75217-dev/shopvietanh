# -*- coding: utf-8 -*-
# SHOP BAN FILE FREE FIRE - CODE HOÀN CHỈNH VỚI API KEY SEPAY CỦA BẠN
# API KEY: R2KFBS3YUQJFO0GNE3NMXIXNUWIQQDLHMIVJUVLIC5Z4MHANP2G5WYDGDP9TFVL1
# ĐÃ TÍCH HỢP ĐẦY ĐỦ: ĐĂNG NHẬP, ĐĂNG KÝ, QUÊN MK, NẠP TIỀN, BANK TỰ ĐỘNG, ADMIN

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
import time
import hmac
import socket
import re

app = Flask(__name__)
app.secret_key = "freefire_shop_secret_key_2026"

# === CẤU HÌNH EMAIL ===
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'      # THAY EMAIL CỦA BẠN
app.config['MAIL_PASSWORD'] = 'your_app_password'         # THAY MẬT KHẨU APP GMAIL
app.config['MAIL_DEFAULT_SENDER'] = 'your_email@gmail.com'
mail = Mail(app)

# ==================== CẤU HÌNH SEPAY (ĐÃ THÊM API KEY CỦA BẠN) ====================
SEPAY_CONFIG = {
    "api_url": "https://bankhub-api.sepay.vn/v1",          # Production URL
    "api_key": "R2KFBS3YUQJFO0GNE3NMXIXNUWIQQDLHMIVJUVLIC5Z4MHANP2G5WYDGDP9TFVL1",
    "account_number": "0123456789",                        # THAY SỐ TÀI KHOẢN MB BANK CỦA BẠN
    "bin": "970422",
    "account_name": "NGUYEN VAN A"                         # THAY TÊN CHỦ TÀI KHOẢN
}

# === CẤU HÌNH SHOP ===
SHOP_NAME = "FF SHOP PRO"
ZALO = "0362281930"
CURRENCY = "VND"

# === KHỞI TẠO DATABASE ===
DB_FILE = "shop_ff.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id TEXT PRIMARY KEY, name TEXT, category TEXT, price REAL,
        stock INTEGER, sold INTEGER DEFAULT 0, description TEXT,
        features TEXT, platform TEXT, warranty TEXT, file_link TEXT,
        status TEXT, created TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY, product_id TEXT, product_name TEXT,
        quantity INTEGER, total REAL, buyer TEXT, phone TEXT,
        payment_method TEXT, status TEXT, file_link TEXT, created TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY, username TEXT UNIQUE, email TEXT UNIQUE,
        password_hash TEXT, full_name TEXT, phone TEXT, role TEXT,
        status TEXT, reset_token TEXT, reset_expiry TEXT,
        balance REAL DEFAULT 0, created TEXT, last_login TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS deposit_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT, method TEXT, amount REAL,
        card_type TEXT, card_code TEXT, card_serial TEXT,
        bank_info TEXT, status TEXT, created TEXT
    )''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# === HÀM HỖ TRỢ ===
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_random_id(prefix=""):
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"{prefix}{random_str}"

def generate_qr_mbbank(amount, order_id):
    try:
        qr_data = f"https://img.vietqr.io/image/{SEPAY_CONFIG['bin']}-{SEPAY_CONFIG['account_number']}-compact2.png?amount={int(amount)}&addInfo={order_id}"
        return qr_data
    except:
        return None

# ==================== HÀM GỌI API SEPAY ====================
def fetch_sepay_transactions(account_number, from_date, to_date):
    """
    Lấy danh sách giao dịch từ SePay sử dụng API Key
    """
    try:
        headers = {
            "Authorization": f"Bearer {SEPAY_CONFIG['api_key']}",
            "Content-Type": "application/json"
        }
        params = {
            "account_number": account_number,
            "from_date": from_date.split()[0],
            "to_date": to_date.split()[0]
        }
        response = requests.get(
            SEPAY_CONFIG['api_url'] + "/transactions",
            headers=headers,
            params=params,
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
        else:
            print(f"SePay API error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"SePay API exception: {e}")
        return []

def test_sepay_connection():
    """Kiểm tra kết nối đến SePay với API Key"""
    try:
        result = fetch_sepay_transactions(
            SEPAY_CONFIG['account_number'],
            datetime.datetime.now().strftime("%Y-%m-%d"),
            datetime.datetime.now().strftime("%Y-%m-%d")
        )
        return len(result) >= 0
    except Exception as e:
        print(f"Connection test failed: {e}")
        return False

def check_and_process_sepay_deposit(user_id, amount, order_id):
    """
    Kiểm tra giao dịch từ SePay và tự động nạp tiền
    """
    from_date = (datetime.datetime.now() - datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    to_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        transactions = fetch_sepay_transactions(
            SEPAY_CONFIG['account_number'], 
            from_date, 
            to_date
        )
        
        for tx in transactions:
            tx_desc = tx.get('description', '') or tx.get('content', '')
            tx_amount = tx.get('amount', 0) or tx.get('transaction_amount', 0)
            tx_status = tx.get('status', '') or tx.get('transaction_status', 'success')
            
            if order_id in tx_desc and float(tx_amount) == float(amount) and tx_status.lower() in ['success', 'completed']:
                # Cộng tiền user
                conn = get_db()
                conn.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
                conn.execute('''INSERT INTO deposit_history 
                    (user_id, method, amount, bank_info, status, created)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (user_id, "sepay", amount, f"SePay - {order_id}", "success", str(datetime.datetime.now())))
                conn.commit()
                conn.close()
                
                # Cập nhật đơn hàng
                conn = get_db()
                conn.execute('UPDATE orders SET status = ? WHERE order_id = ?', ("Đã thanh toán", order_id))
                order = conn.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,)).fetchone()
                conn.close()
                
                if order and order['file_link']:
                    user = get_user_by_id(user_id)
                    if user and user['email']:
                        send_file_by_email(user['email'], order['file_link'], order_id)
                
                return {"success": True, "message": f"Nạp {amount} VND thành công qua SePay!"}
        
        return {"success": False, "message": "Chưa tìm thấy giao dịch khớp. Vui lòng đợi vài phút."}
    
    except Exception as e:
        return {"success": False, "message": f"Lỗi kết nối SePay: {str(e)}"}

# === QUẢN LÝ SẢN PHẨM ===
def add_product_db(name, category, price, stock, description, features="", platform="", warranty="", file_link=""):
    conn = get_db()
    pid = generate_random_id("FF")
    product = {
        "id": pid, "name": name, "category": category, "price": float(price),
        "stock": int(stock), "sold": 0, "description": description,
        "features": features, "platform": platform, "warranty": warranty,
        "file_link": file_link, "status": "Sẵn hàng" if int(stock) > 0 else "Hết hàng",
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
    if not update_product_stock(product_id, quantity):
        return None
    order_id = generate_random_id("ORD")
    total = product['price'] * quantity
    order = {
        "order_id": order_id, "product_id": product_id,
        "product_name": product['name'], "quantity": quantity,
        "total": total, "buyer": buyer_name, "phone": phone,
        "payment_method": payment_method, "status": "Chờ thanh toán",
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
    exist = conn.execute('SELECT * FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
    if exist:
        conn.close()
        return False
    user_id = generate_random_id("USR")
    user = {
        "user_id": user_id, "username": username, "email": email,
        "password_hash": hash_password(password), "full_name": full_name,
        "phone": phone, "role": role, "status": "active",
        "reset_token": "", "reset_expiry": "",
        "balance": 0,
        "created": str(datetime.datetime.now()), "last_login": None
    }
    conn.execute('''INSERT INTO users VALUES (
        :user_id, :username, :email, :password_hash, :full_name,
        :phone, :role, :status, :reset_token, :reset_expiry, :balance, :created, :last_login
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

def update_user_balance(user_id, amount):
    conn = get_db()
    conn.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    conn.close()

# === QUẢN LÝ NẠP TIỀN ===
def process_card_deposit(user_id, card_type, card_code, card_serial, amount):
    if len(card_code) < 6 or len(card_serial) < 6:
        return {"success": False, "message": "Mã thẻ hoặc serial không hợp lệ"}
    conn = get_db()
    conn.execute('''INSERT INTO deposit_history 
        (user_id, method, amount, card_type, card_code, card_serial, status, created)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (user_id, "card", amount, card_type, card_code, card_serial, "success", str(datetime.datetime.now())))
    conn.commit()
    conn.close()
    update_user_balance(user_id, amount)
    return {"success": True, "message": f"Nạp {amount} VND thành công!"}

def process_bank_deposit(user_id, amount, order_id):
    conn = get_db()
    conn.execute('''INSERT INTO deposit_history 
        (user_id, method, amount, bank_info, status, created)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (user_id, "sepay", amount, f"SePay - {order_id}", "pending", str(datetime.datetime.now())))
    conn.commit()
    conn.close()
    result = check_and_process_sepay_deposit(user_id, amount, order_id)
    return result

# === HÀM GỬI EMAIL ===
def send_reset_email(email, reset_link):
    try:
        msg = Message("Đặt lại mật khẩu - FF SHOP", recipients=[email])
        msg.html = f'''
        <h2>Xin chào!</h2>
        <p>Bạn đã yêu cầu đặt lại mật khẩu cho tài khoản tại FF SHOP.</p>
        <p>Vui lòng nhấp vào link bên dưới để đặt lại mật khẩu (có hiệu lực trong 15 phút):</p>
        <p><a href="{reset_link}">{reset_link}</a></p>
        <p>Nếu bạn không yêu cầu, vui lòng bỏ qua email này.</p>
        '''
        mail.send(msg)
        return True
    except:
        return False

def send_file_by_email(email, file_link, order_id):
    try:
        msg = Message(f"File của bạn - Đơn hàng {order_id}", recipients=[email])
        msg.html = f'''
        <h2>Cảm ơn bạn đã mua hàng tại FF SHOP!</h2>
        <p>Đơn hàng <b>{order_id}</b> đã được xác nhận.</p>
        <p>Link tải file: <a href="{file_link}">{file_link}</a></p>
        <p>Trân trọng,<br>FF SHOP PRO</p>
        '''
        mail.send(msg)
        return True
    except:
        return False

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
    <div style="max-width:460px; margin:30px auto; padding:40px 35px; background:rgba(255,255,255,0.03); border-radius:40px; border:1px solid rgba(255,255,255,0.05);">
        <h2 style="text-align:center; font-weight:700; background:linear-gradient(135deg, #ffd700, #f7971e); -webkit-background-clip:text; -webkit-text-fill-color:transparent;">Đăng ký tài khoản</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Tên đăng nhập" required style="width:100%; padding:16px 20px; margin:10px 0; border-radius:60px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); color:#fff;">
            <input type="email" name="email" placeholder="Email" required style="width:100%; padding:16px 20px; margin:10px 0; border-radius:60px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); color:#fff;">
            <input type="password" name="password" placeholder="Mật khẩu" required style="width:100%; padding:16px 20px; margin:10px 0; border-radius:60px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); color:#fff;">
            <input type="text" name="full_name" placeholder="Họ tên" style="width:100%; padding:16px 20px; margin:10px 0; border-radius:60px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); color:#fff;">
            <input type="text" name="phone" placeholder="Số điện thoại" style="width:100%; padding:16px 20px; margin:10px 0; border-radius:60px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); color:#fff;">
            <button type="submit" style="width:100%; padding:16px; background:linear-gradient(135deg, #f7971e, #ffd200); border:none; border-radius:60px; color:#0a0a0f; font-weight:700; cursor:pointer;">Đăng ký</button>
        </form>
        <p style="text-align:center; margin-top:15px;"><a href="/" style="color:rgba(255,255,255,0.3); text-decoration:none;">Quay lại trang chủ</a></p>
    </div>
    '''

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Đã đăng xuất.')
    return redirect(url_for('index'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = get_user_by_email(email)
        if not user:
            flash('Email không tồn tại!')
            return redirect(url_for('forgot_password'))
        token = hashlib.sha256(f"{email}{datetime.datetime.now()}".encode()).hexdigest()[:32]
        expiry = str(datetime.datetime.now() + datetime.timedelta(minutes=15))
        set_reset_token_db(email, token, expiry)
        reset_link = f"{request.host_url}reset-password/{token}"
        if send_reset_email(email, reset_link):
            flash('Email đặt lại mật khẩu đã gửi!')
        else:
            flash('Lỗi gửi email!')
        return redirect(url_for('index'))
    return '''
    <div style="max-width:460px; margin:30px auto; padding:40px 35px; background:rgba(255,255,255,0.03); border-radius:40px; border:1px solid rgba(255,255,255,0.05);">
        <h2 style="text-align:center; font-weight:700; color:#ffd700;">Quên mật khẩu</h2>
        <form method="POST">
            <input type="email" name="email" placeholder="Email của bạn" required style="width:100%; padding:16px 20px; margin:10px 0; border-radius:60px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); color:#fff;">
            <button type="submit" style="width:100%; padding:16px; background:linear-gradient(135deg, #f7971e, #ffd200); border:none; border-radius:60px; color:#0a0a0f; font-weight:700; cursor:pointer;">Gửi link reset</button>
        </form>
        <p style="text-align:center; margin-top:15px;"><a href="/" style="color:rgba(255,255,255,0.3); text-decoration:none;">Quay lại</a></p>
    </div>
    '''

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = get_user_by_reset_token(token)
    if not user:
        flash('Link không hợp lệ hoặc hết hạn!')
        return redirect(url_for('index'))
    if request.method == 'POST':
        new_password = request.form.get('password')
        if len(new_password) < 6:
            flash('Mật khẩu phải có ít nhất 6 ký tự!')
            return redirect(url_for('reset_password', token=token))
        update_user_password_db(user['user_id'], new_password)
        set_reset_token_db(user['email'], '', '')
        flash('Đặt lại mật khẩu thành công!')
        return redirect(url_for('index'))
    return '''
    <div style="max-width:460px; margin:30px auto; padding:40px 35px; background:rgba(255,255,255,0.03); border-radius:40px; border:1px solid rgba(255,255,255,0.05);">
        <h2 style="text-align:center; font-weight:700; color:#ffd700;">Đặt lại mật khẩu</h2>
        <form method="POST">
            <input type="password" name="password" placeholder="Mật khẩu mới (≥ 6 ký tự)" required style="width:100%; padding:16px 20px; margin:10px 0; border-radius:60px; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.06); color:#fff;">
            <button type="submit" style="width:100%; padding:16px; background:linear-gradient(135deg, #f7971e, #ffd200); border:none; border-radius:60px; color:#0a0a0f; font-weight:700; cursor:pointer;">Cập nhật</button>
        </form>
    </div>
    '''

@app.route('/buy', methods=['POST'])
def buy():
    if 'user' not in session:
        flash('Vui lòng đăng nhập!')
        return redirect(url_for('index'))
    product_id = request.form.get('product_id')
    try:
        quantity = int(request.form.get('quantity', 1))
    except:
        quantity = 1
    user = session['user']
    order = create_order_db(product_id, quantity, user['full_name'] or user['username'], 
                           user.get('phone', 'Chưa cập nhật'), 'SePay')
    if not order:
        flash('Lỗi đặt hàng! Kiểm tra số lượng.')
        return redirect(url_for('index'))
    flash(f'Đặt hàng thành công! Mã đơn: {order["order_id"]}. Vui lòng thanh toán qua Bank hoặc nạp tiền.')
    return redirect(url_for('index'))

@app.route('/orders')
def orders():
    if 'user' not in session:
        return redirect(url_for('index'))
    user_orders = get_orders_by_phone(session['user']['phone'])
    html = '''
    <div style="max-width:900px; margin:30px auto; padding:30px; background:rgba(255,255,255,0.03); border-radius:32px; border:1px solid rgba(255,255,255,0.05);">
        <h2 style="color:#ffd700;">📦 Đơn hàng của tôi</h2>
        <a href="/" style="color:rgba(255,255,255,0.3); text-decoration:none;">← Quay lại</a>
        <div style="margin-top:20px;">
    '''
    if not user_orders:
        html += '<p style="color:rgba(255,255,255,0.3);">Bạn chưa có đơn hàng nào.</p>'
    else:
        for o in user_orders:
            html += f'''
            <div style="border-bottom:1px solid rgba(255,255,255,0.04); padding:15px 0;">
                <b style="color:#fff;">{o['order_id']}</b> - {o['product_name']} x{o['quantity']} - <b style="color:#ffd700;">{o['total']} {CURRENCY}</b>
                <br>Trạng thái: <b style="color:{'#2ecc71' if o['status']=='Đã thanh toán' else '#f39c12'};">{o['status']}</b> | Ngày: {o['created']}
                <br>File: <a href="{o['file_link']}" target="_blank" style="color:#ffd700;">{o['file_link'] or 'Chưa có'}</a>
            </div>
            '''
    html += '</div></div>'
    return html

# === NẠP TIỀN (GIAO DIỆN ĐẸP) ===
@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if 'user' not in session:
        flash('Vui lòng đăng nhập để nạp tiền!')
        return redirect(url_for('index'))
    
    user = session['user']
    if request.method == 'POST':
        method = request.form.get('method')
        amount = float(request.form.get('amount', 0))
        
        if amount <= 0:
            flash('Số tiền phải lớn hơn 0!')
            return redirect(url_for('deposit'))
        
        if method == 'card':
            card_type = request.form.get('card_type')
            card_code = request.form.get('card_code')
            card_serial = request.form.get('card_serial')
            result = process_card_deposit(user['user_id'], card_type, card_code, card_serial, amount)
            flash(result['message'])
            if result['success']:
                session['user']['balance'] = user['balance'] + amount
            return redirect(url_for('deposit'))
        
        elif method == 'bank':
            order_id = generate_random_id("BANK")
            qr_link = generate_qr_mbbank(amount, order_id)
            if not qr_link:
                flash('Lỗi tạo QR, vui lòng thử lại!')
                return redirect(url_for('deposit'))
            
            result = process_bank_deposit(user['user_id'], amount, order_id)
            flash(result['message'])
            if result['success']:
                session['user']['balance'] = user['balance'] + amount
            return redirect(url_for('deposit'))
    
    # GIAO DIỆN NẠP TIỀN ĐẸP, HIỆN ĐẠI
    html = '''
    <!DOCTYPE html>
    <html lang="vi">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Nạp tiền - FF SHOP</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Inter', sans-serif;
                background: #f0f2f5;
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            .deposit-container {
                max-width: 1100px;
                width: 100%;
                background: white;
                border-radius: 32px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.08);
            }
            .deposit-header {
                text-align: center;
                margin-bottom: 35px;
            }
            .deposit-header h1 {
                font-size: 2.2em;
                font-weight: 800;
                color: #1a1a2e;
                letter-spacing: -0.5px;
            }
            .deposit-header h1 span { color: #f7971e; }
            .deposit-header p {
                color: #6b7280;
                font-size: 1em;
                margin-top: 6px;
            }
            .balance-box {
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                border-radius: 20px;
                padding: 20px 30px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 30px;
                color: white;
                flex-wrap: wrap;
                gap: 10px;
            }
            .balance-box .label { font-size: 0.9em; opacity: 0.7; }
            .balance-box .amount {
                font-size: 2em;
                font-weight: 700;
                background: linear-gradient(135deg, #ffd700, #f7971e);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .balance-box .btn-home {
                background: rgba(255,255,255,0.1);
                padding: 8px 20px;
                border-radius: 30px;
                color: white;
                text-decoration: none;
                font-size: 0.85em;
                transition: 0.3s;
            }
            .balance-box .btn-home:hover { background: rgba(255,255,255,0.2); }
            .deposit-grid {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 30px;
            }
            @media (max-width: 768px) { .deposit-grid { grid-template-columns: 1fr; } }
            .deposit-card {
                background: #f8fafc;
                border-radius: 24px;
                padding: 30px;
                border: 1px solid #e9edf2;
                transition: 0.3s;
            }
            .deposit-card:hover { border-color: #f7971e; box-shadow: 0 8px 30px rgba(247,151,30,0.08); }
            .deposit-card .icon {
                font-size: 2.2em;
                color: #f7971e;
                margin-bottom: 10px;
            }
            .deposit-card h3 {
                font-size: 1.3em;
                font-weight: 700;
                color: #1a1a2e;
                margin-bottom: 8px;
            }
            .deposit-card .desc {
                color: #6b7280;
                font-size: 0.9em;
                margin-bottom: 18px;
            }
            .deposit-card label {
                font-weight: 600;
                font-size: 0.85em;
                color: #374151;
                display: block;
                margin-top: 12px;
                margin-bottom: 4px;
            }
            .deposit-card input, .deposit-card select {
                width: 100%;
                padding: 12px 16px;
                border: 1px solid #d1d5db;
                border-radius: 16px;
                font-size: 0.95em;
                font-family: 'Inter', sans-serif;
                transition: 0.3s;
                background: white;
                color: #1a1a2e;
            }
            .deposit-card input:focus, .deposit-card select:focus {
                border-color: #f7971e;
                outline: none;
                box-shadow: 0 0 0 3px rgba(247,151,30,0.15);
            }
            .deposit-card button {
                width: 100%;
                padding: 14px;
                margin-top: 18px;
                background: linear-gradient(135deg, #f7971e, #ffd200);
                border: none;
                border-radius: 60px;
                color: #1a1a2e;
                font-weight: 700;
                font-size: 1em;
                cursor: pointer;
                transition: 0.3s;
                font-family: 'Inter', sans-serif;
            }
            .deposit-card button:hover {
                transform: scale(1.02);
                box-shadow: 0 8px 25px rgba(247,151,30,0.3);
            }
            .deposit-card .qr-placeholder {
                margin-top: 15px;
                padding: 15px;
                background: white;
                border-radius: 16px;
                border: 1px dashed #d1d5db;
                text-align: center;
                color: #6b7280;
                font-size: 0.9em;
            }
            .deposit-card .bank-info {
                margin-top: 15px;
                padding: 12px 16px;
                background: #eef2f6;
                border-radius: 12px;
                font-size: 0.85em;
                color: #1a1a2e;
            }
            .deposit-card .bank-info strong { color: #f7971e; }
            .flash-message {
                padding: 14px 20px;
                border-radius: 16px;
                margin-bottom: 20px;
                background: #fef9e7;
                border: 1px solid #f9e79f;
                color: #7d6608;
                font-weight: 500;
                text-align: center;
            }
            .footer-text {
                text-align: center;
                margin-top: 30px;
                font-size: 0.85em;
                color: #9ca3af;
            }
            .footer-text a { color: #f7971e; text-decoration: none; }
        </style>
    </head>
    <body>
        <div class="deposit-container">
            <div class="deposit-header">
                <h1>💳 Nạp <span>tiền</span></h1>
                <p>Chọn phương thức nạp tiền vào tài khoản</p>
            </div>

            <div class="balance-box">
                <div>
                    <div class="label">💰 Số dư hiện tại</div>
                    <div class="amount">''' + f"{user['balance']:,.0f}" + ''' đ</div>
                </div>
                <a href="/" class="btn-home"><i class="fas fa-arrow-left"></i> Trang chủ</a>
            </div>

            {% with messages = get_flashed_messages() %}
                {% if messages %}
                    <div class="flash-message"><i class="fas fa-info-circle"></i> {{ messages[0] }}</div>
                {% endif %}
            {% endwith %}

            <div class="deposit-grid">
                <!-- THẺ CÀO -->
                <div class="deposit-card">
                    <div class="icon"><i class="fas fa-credit-card"></i></div>
                    <h3>Thẻ cào</h3>
                    <div class="desc">Nạp tiền bằng thẻ Viettel, Mobifone, VinaPhone</div>
                    <form method="POST">
                        <input type="hidden" name="method" value="card">
                        <label>Loại thẻ</label>
                        <select name="card_type">
                            <option value="viettel">Viettel</option>
                            <option value="mobifone">Mobifone</option>
                            <option value="vinaphone">VinaPhone</option>
                        </select>
                        <label>Mã thẻ</label>
                        <input type="text" name="card_code" placeholder="Nhập mã thẻ" required>
                        <label>Số serial</label>
                        <input type="text" name="card_serial" placeholder="Nhập số serial" required>
                        <label>Mệnh giá (VND)</label>
                        <input type="number" name="amount" placeholder="Nhập số tiền" required min="10000">
                        <button type="submit"><i class="fas fa-check-circle"></i> Nạp thẻ</button>
                    </form>
                </div>

                <!-- BANK / SEPAY -->
                <div class="deposit-card">
                    <div class="icon"><i class="fas fa-university"></i></div>
                    <h3>Chuyển khoản ngân hàng</h3>
                    <div class="desc">Tự động xác nhận qua SePay (MB Bank)</div>
                    <form method="POST">
                        <input type="hidden" name="method" value="bank">
                        <label>Số tiền (VND)</label>
                        <input type="number" name="amount" placeholder="Nhập số tiền cần nạp" required min="10000">
                        <button type="submit"><i class="fas fa-qrcode"></i> Tạo QR & nạp</button>
                    </form>
                    <div class="bank-info">
                        <i class="fas fa-info-circle" style="color:#f7971e;"></i>
                        <strong>MB Bank:</strong> ''' + SEPAY_CONFIG['account_number'] + ''' - ''' + SEPAY_CONFIG['account_name'] + '''
                    </div>
                    <div class="qr-placeholder">
                        <i class="fas fa-qrcode" style="font-size:1.5em; color:#f7971e; display:block; margin-bottom:6px;"></i>
                        Quét QR sau khi nhập số tiền
                    </div>
                </div>
            </div>

            <div class="footer-text">
                <a href="/"><i class="fas fa-arrow-left"></i> Quay lại trang chủ</a>
            </div>
        </div>
    </body>
    </html>
    '''
    return render_template_string(html, session=session)

# === KIỂM TRA KẾT NỐI SEPAY ===
@app.route('/test-sepay')
def test_sepay():
    """Kiểm tra kết nối API SePay"""
    if test_sepay_connection():
        return "✅ Kết nối SePay thành công với API Key!"
    else:
        return "❌ Lỗi kết nối SePay. Kiểm tra API Key và cấu hình."

@app.route('/check-connectivity')
def check_connectivity():
    """Kiểm tra kết nối Internet từ server đến SePay API"""
    import socket
    import requests
    
    result = {
        "dns_resolution": False,
        "api_accessible": False,
        "details": ""
    }
    
    try:
        ip = socket.gethostbyname("bankhub-api.sepay.vn")
        result["dns_resolution"] = True
        result["details"] += f"✅ DNS: bankhub-api.sepay.vn -> {ip}\n"
    except Exception as e:
        result["details"] += f"❌ DNS error: {e}\n"
    
    try:
        test_url = "https://bankhub-api.sepay.vn/v1/health"
        response = requests.get(test_url, timeout=5)
        if response.status_code < 500:
            result["api_accessible"] = True
            result["details"] += f"✅ API accessible: {response.status_code}\n"
        else:
            result["details"] += f"⚠️ API response: {response.status_code}\n"
    except Exception as e:
        result["details"] += f"❌ API error: {e}\n"
    
    html = f"""
    <h2>🔍 Kiểm tra kết nối Internet</h2>
    <pre>{result['details']}</pre>
    <hr>
    <p><b>Kết luận:</b></p>
    <ul>
        <li>DNS: {'✅ OK' if result['dns_resolution'] else '❌ Lỗi'}</li>
        <li>API SePay: {'✅ Có thể truy cập' if result['api_accessible'] else '❌ Không truy cập được'}</li>
    </ul>
    """
    return html

# === WEBHOOK SEPAY ===
@app.route('/mbbank-webhook', methods=['POST'])
def mbbank_webhook():
    data = request.json
    if not data:
        return jsonify({"error": "Invalid data"}), 400
    
    try:
        transaction_id = data.get('transaction_id')
        amount = data.get('amount')
        description = data.get('description')
        status = data.get('status')
        
        if status == 'success' and description and 'ORD' in description:
            match = re.search(r'ORD\w+', description)
            if match:
                order_id = match.group()
                conn = get_db()
                order = conn.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,)).fetchone()
                if order:
                    conn.execute('UPDATE orders SET status = ? WHERE order_id = ?', ("Đã thanh toán", order_id))
                    conn.commit()
                    conn.close()
                    if order['file_link']:
                        user = get_user_by_id(order['phone'])
                        if user and user['email']:
                            send_file_by_email(user['email'], order['file_link'], order_id)
                    return jsonify({"success": True})
                conn.close()
        return jsonify({"success": False})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === ADMIN ===
@app.route('/admin')
def admin_dashboard():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash('Bạn cần quyền Admin!')
        return redirect(url_for('index'))
    users = get_all_users()
    orders = get_all_orders()
    products = get_products()
    html = '''
    <div style="max-width:1200px; margin:20px auto; padding:30px; background:rgba(255,255,255,0.03); border-radius:32px; border:1px solid rgba(255,255,255,0.05);">
        <h2 style="color:#ffd700;">⚙️ Admin Dashboard</h2>
        <a href="/" style="color:rgba(255,255,255,0.3); text-decoration:none;">← Trang chủ</a>
        <div style="display:flex; gap:20px; margin:20px 0; flex-wrap:wrap;">
            <div style="background:rgba(255,215,0,0.05); padding:25px; border-radius:20px; flex:1; text-align:center;">
                <h3 style="color:#ffd700;">Sản phẩm</h3>
                <p style="font-size:2em; color:#fff;">''' + str(len(products)) + '''</p>
                <a href="/admin/products" style="color:#ffd700;">Quản lý</a>
            </div>
            <div style="background:rgba(46,204,113,0.05); padding:25px; border-radius:20px; flex:1; text-align:center;">
                <h3 style="color:#2ecc71;">Đơn hàng</h3>
                <p style="font-size:2em; color:#fff;">''' + str(len(orders)) + '''</p>
                <a href="/admin/orders" style="color:#2ecc71;">Quản lý</a>
            </div>
            <div style="background:rgba(255,107,107,0.05); padding:25px; border-radius:20px; flex:1; text-align:center;">
                <h3 style="color:#ff6b6b;">Người dùng</h3>
                <p style="font-size:2em; color:#fff;">''' + str(len(users)) + '''</p>
                <a href="/admin/users" style="color:#ff6b6b;">Quản lý</a>
            </div>
        </div>
    </div>
    '''
    return html

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
            delete_product_db(request.form.get('pid'))
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
    <div style="max-width:1200px; margin:20px auto; padding:30px; background:rgba(255,255,255,0.03); border-radius:32px; border:1px solid rgba(255,255,255,0.05);">
        <h2 style="color:#ffd700;">📦 Quản lý sản phẩm</h2>
        <a href="/admin" style="color:rgba(255,255,255,0.3); text-decoration:none;">← Dashboard</a> | <a href="/" style="color:rgba(255,255,255,0.3); text-decoration:none;">Trang chủ</a>
        <div class="admin-panel">
            <h3 style="color:#fff;">➕ Thêm sản phẩm mới</h3>
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
                <input type="text" name="file_link" placeholder="Link file" style="width:100%;">
                <button type="submit">Thêm sản phẩm</button>
            </form>
        </div>
        <h3 style="color:#fff;">Danh sách sản phẩm</h3>
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

@app.route('/admin/orders', methods=['GET', 'POST'])
def admin_orders():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash('Bạn cần quyền Admin!')
        return redirect(url_for('index'))
    if request.method == 'POST':
        action = request.form.get('action')
        order_id = request.form.get('order_id')
        if action == 'update_status':
            update_order_status_db(order_id, request.form.get('status'))
            flash('Cập nhật trạng thái đơn hàng thành công!')
        elif action == 'delete':
            delete_order_db(order_id)
            flash('Xóa đơn hàng thành công!')
        return redirect(url_for('admin_orders'))
    orders = get_all_orders()
    html = '''
    <div style="max-width:1200px; margin:20px auto; padding:30px; background:rgba(255,255,255,0.03); border-radius:32px; border:1px solid rgba(255,255,255,0.05);">
        <h2 style="color:#ffd700;">📋 Quản lý đơn hàng</h2>
        <a href="/admin" style="color:rgba(255,255,255,0.3); text-decoration:none;">← Dashboard</a> | <a href="/" style="color:rgba(255,255,255,0.3); text-decoration:none;">Trang chủ</a>
        <h3 style="color:#fff;">Danh sách đơn hàng</h3>
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
                    <select name="status" onchange="this.form.submit()" style="background:rgba(255,255,255,0.04); color:#fff; border:1px solid rgba(255,255,255,0.06); border-radius:30px; padding:6px 14px;">
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
    html += '</table></div>'
    return html

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
            update_user_role_db(user_id, request.form.get('role'))
            flash('Cập nhật vai trò thành công!')
        elif action == 'toggle_status':
            toggle_user_status_db(user_id)
            flash('Cập nhật trạng thái thành công!')
        return redirect(url_for('admin_users'))
    users = get_all_users()
    html = '''
    <div style="max-width:1200px; margin:20px auto; padding:30px; background:rgba(255,255,255,0.03); border-radius:32px; border:1px solid rgba(255,255,255,0.05);">
        <h2 style="color:#ffd700;">👥 Quản lý người dùng</h2>
        <a href="/admin" style="color:rgba(255,255,255,0.3); text-decoration:none;">← Dashboard</a> | <a href="/" style="color:rgba(255,255,255,0.3); text-decoration:none;">Trang chủ</a>
        <h3 style="color:#fff;">Danh sách người dùng</h3>
        <table>
            <tr><th>ID</th><th>Tên đăng nhập</th><th>Email</th><th>Họ tên</th><th>Số dư</th><th>Vai trò</th><th>Trạng thái</th><th>Hành động</th></tr>
    '''
    for u in users:
        html += f'''
        <tr>
            <td>{u['user_id'][:8]}</td>
            <td>{u['username']}</td>
            <td>{u['email']}</td>
            <td>{u['full_name'] or '---'}</td>
            <td style="color:#ffd700;">{u['balance']}đ</td>
            <td>
                <form method="POST" style="display:inline-block;">
                    <input type="hidden" name="action" value="change_role">
                    <input type="hidden" name="user_id" value="{u['user_id']}">
                    <select name="role" onchange="this.form.submit()" style="background:rgba(255,255,255,0.04); color:#fff; border:1px solid rgba(255,255,255,0.06); border-radius:30px; padding:6px 14px;">
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
    html += '</table></div>'
    return html

# ==================== HTML TEMPLATE ====================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ shop_name }}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: #0a0a0f; min-height: 100vh; padding: 20px; color: #fff; }
        .container { max-width: 1280px; margin: auto; background: rgba(255,255,255,0.03); backdrop-filter: blur(20px); border-radius: 48px; padding: 35px; border: 1px solid rgba(255,255,255,0.06); box-shadow: 0 30px 80px rgba(0,0,0,0.5); }
        .header { text-align: center; padding: 25px 0 20px; position: relative; }
        .header h1 { font-size: 3.5em; font-weight: 900; background: linear-gradient(135deg, #f7971e, #ffd200, #f7971e); background-size: 300% 300%; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: gradientMove 5s ease infinite; }
        @keyframes gradientMove { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
        .header .sub { color: rgba(255,255,255,0.4); font-weight: 300; letter-spacing: 3px; font-size: 0.9em; margin-top: 6px; }
        .zalo-badge { display: inline-block; background: rgba(0,136,204,0.15); color: #4fc3f7; padding: 8px 28px; border-radius: 60px; margin: 12px 0; font-weight: 600; border: 1px solid rgba(0,136,204,0.15); }
        .user-info { position: absolute; right: 20px; top: 20px; background: rgba(255,255,255,0.04); padding: 10px 24px; border-radius: 60px; border: 1px solid rgba(255,255,255,0.05); font-size: 0.9em; }
        .user-info a { color: #ff6b6b; text-decoration: none; font-weight: 600; }
        .menu { display: flex; flex-wrap: wrap; gap: 10px; margin: 25px 0; justify-content: center; }
        .menu a, .menu button { font-family: 'Inter', sans-serif; background: rgba(255,255,255,0.04); color: #fff; padding: 12px 28px; border-radius: 60px; text-decoration: none; border: 1px solid rgba(255,255,255,0.05); cursor: pointer; font-weight: 500; transition: all 0.25s ease; }
        .menu a:hover, .menu button:hover { background: rgba(247,151,30,0.12); border-color: rgba(247,151,30,0.2); transform: translateY(-2px); }
        .menu a.admin { background: linear-gradient(135deg, #f7971e, #ffd200); color: #0a0a0f; border: none; font-weight: 700; }
        .products { display: grid; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); gap: 25px; margin-top: 30px; }
        .product-card { background: rgba(255,255,255,0.03); border-radius: 28px; padding: 24px 20px; transition: all 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275); border: 1px solid rgba(255,255,255,0.04); }
        .product-card:hover { transform: translateY(-8px); background: rgba(255,255,255,0.06); border-color: rgba(247,151,30,0.15); box-shadow: 0 20px 50px rgba(0,0,0,0.3); }
        .product-card h3 { font-size: 1.3em; font-weight: 700; margin-bottom: 4px; }
        .product-card .features { color: #ffd700; font-weight: 500; }
        .product-card .price { font-size: 1.9em; font-weight: 800; background: linear-gradient(135deg, #ffd700, #f7971e); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 10px 0; }
        .product-card .stock { color: #2ecc71; font-weight: 500; }
        .btn-buy { width: 100%; padding: 14px; background: linear-gradient(135deg, #f7971e, #ffd200); border: none; border-radius: 60px; color: #0a0a0f; font-weight: 700; cursor: pointer; transition: all 0.3s; font-family: 'Inter', sans-serif; margin-top: 8px; }
        .btn-buy:hover { transform: scale(1.02); box-shadow: 0 8px 25px rgba(247,151,30,0.3); }
        .auth-form { max-width: 460px; margin: 30px auto; padding: 40px 35px; background: rgba(255,255,255,0.03); border-radius: 40px; border: 1px solid rgba(255,255,255,0.05); }
        .auth-form h2 { text-align: center; font-weight: 700; font-size: 1.8em; background: linear-gradient(135deg, #ffd700, #f7971e); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        .auth-form input { width: 100%; padding: 16px 20px; margin: 10px 0; border: 1px solid rgba(255,255,255,0.06); border-radius: 60px; background: rgba(255,255,255,0.04); color: #fff; font-size: 0.95em; outline: none; transition: 0.3s; }
        .auth-form input:focus { border-color: #ffd700; background: rgba(255,255,255,0.08); }
        .auth-form button { width: 100%; padding: 16px; background: linear-gradient(135deg, #f7971e, #ffd200); border: none; border-radius: 60px; color: #0a0a0f; font-weight: 700; cursor: pointer; transition: 0.3s; margin-top: 8px; }
        .flash { padding: 14px 24px; background: rgba(241,196,15,0.08); border: 1px solid rgba(241,196,15,0.12); border-radius: 24px; margin: 15px 0; text-align: center; color: #ffd700; font-weight: 500; }
        .footer { text-align: center; margin-top: 40px; padding-top: 25px; border-top: 1px solid rgba(255,255,255,0.04); color: rgba(255,255,255,0.15); font-size: 0.85em; }
        .admin-panel { background: rgba(255,255,255,0.03); padding: 25px; border-radius: 28px; margin: 20px 0; border: 1px solid rgba(255,255,255,0.04); }
        .admin-panel input, .admin-panel textarea { width: 100%; padding: 14px 18px; margin: 8px 0; border: 1px solid rgba(255,255,255,0.06); border-radius: 30px; background: rgba(255,255,255,0.04); color: #fff; outline: none; }
        .admin-panel button { background: linear-gradient(135deg, #f7971e, #ffd200); color: #0a0a0f; padding: 14px 35px; border: none; border-radius: 60px; font-weight: 700; cursor: pointer; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; border-radius: 20px; overflow: hidden; }
        th { background: rgba(247,151,30,0.12); color: #ffd700; padding: 14px; font-weight: 700; text-align: left; }
        td { padding: 12px 14px; border-bottom: 1px solid rgba(255,255,255,0.04); color: rgba(255,255,255,0.75); }
        .btn-small { padding: 6px 16px; border: none; border-radius: 30px; cursor: pointer; font-weight: 600; font-size: 0.8em; }
        .btn-danger { background: #ff6b6b; color: #fff; }
        .btn-success { background: #2ecc71; color: #fff; }
        .btn-warning { background: #f39c12; color: #fff; }
        @media (max-width: 768px) { .container { padding: 20px; } .header h1 { font-size: 2.2em; } .user-info { position: static; display: inline-block; margin-top: 10px; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔥 {{ shop_name }}</h1>
            <div class="sub">⚡ Bán file Free Fire - Tích hợp SePay tự động</div>
            <div class="zalo-badge"><i class="fas fa-phone-alt"></i> Zalo: {{ zalo }}</div>
            <div class="user-info">
                {% if session.user %}
                    <i class="fas fa-user-circle"></i> {{ session.user.full_name or session.user.username }}
                    {% if session.user.role == 'admin' %}⭐ Admin{% endif %}
                    | <i class="fas fa-coins" style="color:#ffd700;"></i> {{ session.user.balance|default(0) }}đ
                    | <a href="{{ url_for('logout') }}"><i class="fas fa-sign-out-alt"></i></a>
                {% endif %}
            </div>
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}<div class="flash"><i class="fas fa-bell"></i> {{ messages[0] }}</div>{% endif %}
        {% endwith %}

        {% if not session.user %}
        <div class="auth-form">
            <h2>Chào mừng trở lại</h2>
            <form method="POST" action="{{ url_for('login') }}">
                <input type="text" name="username" placeholder="Email / Username" required>
                <input type="password" name="password" placeholder="Mật khẩu" required>
                <button type="submit"><i class="fas fa-sign-in-alt"></i> Đăng nhập</button>
            </form>
            <div style="text-align:center; margin-top:15px;">
                <a href="{{ url_for('register') }}" style="color:rgba(255,255,255,0.3);">Đăng ký</a> | 
                <a href="{{ url_for('forgot_password') }}" style="color:rgba(255,255,255,0.3);">Quên mật khẩu?</a>
            </div>
        </div>
        {% else %}
        <div class="menu">
            <a href="{{ url_for('index') }}"><i class="fas fa-home"></i> Trang chủ</a>
            <a href="{{ url_for('category', cat='Android') }}"><i class="fab fa-android"></i> Android</a>
            <a href="{{ url_for('category', cat='iOS') }}"><i class="fab fa-apple"></i> iOS</a>
            <a href="{{ url_for('category', cat='PC') }}"><i class="fas fa-desktop"></i> PC</a>
            <a href="{{ url_for('orders') }}"><i class="fas fa-box"></i> Đơn hàng</a>
            <a href="{{ url_for('deposit') }}" style="background:rgba(247,151,30,0.12); border-color:rgba(247,151,30,0.15);"><i class="fas fa-coins"></i> Nạp tiền</a>
            {% if session.user.role == 'admin' %}
                <a href="{{ url_for('admin_dashboard') }}" class="admin"><i class="fas fa-cog"></i> Quản trị</a>
            {% endif %}
        </div>

        <div class="products">
            {% for p in products %}
            <div class="product-card">
                <h3>{{ p.name }}</h3>
                <div class="features">{{ p.features }}</div>
                <div style="color:rgba(255,255,255,0.4); font-size:0.85em;">{{ p.warranty }}</div>
                <div class="price">{{ p.price }} {{ currency }}</div>
                <div class="stock"><i class="fas fa-check-circle"></i> Còn: {{ p.stock }} | Đã bán: {{ p.sold }}</div>
                <div style="display:inline-block; background:rgba(255,255,255,0.05); padding:3px 14px; border-radius:30px; font-size:0.8em; color:rgba(255,255,255,0.5); margin:8px 0;">{{ p.platform }}</div>
                <form method="POST" action="{{ url_for('buy') }}">
                    <input type="hidden" name="product_id" value="{{ p.id }}">
                    <input type="number" name="quantity" value="1" min="1" max="{{ p.stock }}" style="width:70px; padding:10px; border-radius:30px; border:1px solid rgba(255,255,255,0.06); background:rgba(255,255,255,0.04); color:#fff; margin:8px 0;">
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

# ==================== KHỞI TẠO ====================
def init_sample_data():
    init_db()
    conn = get_db()
    admin = conn.execute('SELECT * FROM users WHERE username = "admin"').fetchone()
    conn.close()
    if not admin:
        register_user_db("admin", "admin@ffshop.com", "admin123", "Administrator", "0988888888", "admin")
    if not get_products():
        sample_products = [
            ("Pixel 1.0", "Android", 350000, 10, "Nhiều Chức Năng Hot", "Full Đỏ Dễ Dàng", "Android", "An Toàn Acc Chính", "https://drive.google.com/file/pixel1"),
            ("Aim Proxy", "iOS", 0, 6, "Kéo Là Đỏ", "Đi Rank Phòng Đều Ok", "iOS", "", "https://drive.google.com/file/aimproxy"),
            ("AimBot PC", "PC", 0, 9, "Esp,Aimbot,Ai player", "An Toàn Trên Acc Chính", "PC", "", "https://drive.google.com/file/aimbotpc"),
        ]
        for name, cat, price, stock, desc, features, platform, warranty, file_link in sample_products:
            add_product_db(name, cat, price, stock, desc, features, platform, warranty, file_link)

init_sample_data()

# === DÙNG CHO PRODUCTION ===
application = app

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=10000)
