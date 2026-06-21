# -*- coding: utf-8 -*-
# TOAN BO CODE WEB SHOP THANH SON - CHAY TREN RENDER.COM
# (Copy toan bo file nay vao app.py va deploy len Render)

from flask import Flask, render_template_string, request, redirect, url_for, session, flash, jsonify
import hashlib
import json
import os
import datetime
import random

app = Flask(__name__)
app.secret_key = "thanhson_super_secret_key_2026"

# === CAU HINH ===
SHOP_NAME = "SHOP UY TÍN HÀNG ĐẦU"
ZALO = "0362281930"
CURRENCY = "VND"

# File luu tru (Render se luu tam thoi, can dung PostgreSQL de luu vinh vien)
PRODUCT_FILE = "web_products.json"
ORDER_FILE = "web_orders.json"
USER_FILE = "web_users.json"

# Khoi tao file
def init_files():
    for f in [PRODUCT_FILE, ORDER_FILE, USER_FILE]:
        if not os.path.exists(f):
            with open(f, "w", encoding="utf-8") as file:
                json.dump([], file, indent=4)

# === QUAN LY SAN PHAM ===
def load_products():
    with open(PRODUCT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_products(products):
    with open(PRODUCT_FILE, "w", encoding="utf-8") as f:
        json.dump(products, f, indent=4)

def add_product(name, category, price, stock, description, features="", platform="", warranty=""):
    products = load_products()
    pid = hashlib.md5(f"{name}{datetime.datetime.now()}".encode()).hexdigest()[:8]
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
        "status": "Sẵn hàng" if int(stock) > 0 else "Hết hàng",
        "created": str(datetime.datetime.now())
    }
    products.append(product)
    save_products(products)
    return pid

def get_product_by_id(pid):
    products = load_products()
    for p in products:
        if p["id"] == pid:
            return p
    return None

# === QUAN LY DON HANG ===
def load_orders():
    with open(ORDER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_orders(orders):
    with open(ORDER_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, indent=4)

def create_order(product_id, quantity, buyer_name, phone, payment_method="ZaloPay"):
    product = get_product_by_id(product_id)
    if not product or product["stock"] < quantity:
        return None
    
    # Tru stock
    product["stock"] -= quantity
    product["sold"] += quantity
    products = load_products()
    for i, p in enumerate(products):
        if p["id"] == product_id:
            products[i] = product
            break
    save_products(products)
    
    order_id = hashlib.md5(f"{buyer_name}{phone}{datetime.datetime.now()}".encode()).hexdigest()[:10].upper()
    total = product["price"] * quantity
    order = {
        "order_id": order_id,
        "product_id": product_id,
        "product_name": product["name"],
        "quantity": quantity,
        "total": total,
        "buyer": buyer_name,
        "phone": phone,
        "payment": payment_method,
        "status": "Chờ xác nhận",
        "created": str(datetime.datetime.now())
    }
    orders = load_orders()
    orders.append(order)
    save_orders(orders)
    return order

# === QUAN LY USER ===
def load_users():
    with open(USER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)

def register_user(username, email, password, full_name="", phone=""):
    users = load_users()
    if any(u["username"] == username or u["email"] == email for u in users):
        return False
    user = {
        "user_id": hashlib.md5(f"{username}{datetime.datetime.now()}".encode()).hexdigest()[:8],
        "username": username,
        "email": email,
        "password_hash": hashlib.sha256(password.encode()).hexdigest(),
        "full_name": full_name,
        "phone": phone,
        "role": "user",
        "created": str(datetime.datetime.now())
    }
    users.append(user)
    save_users(users)
    return True

def login_user(username_or_email, password):
    users = load_users()
    for u in users:
        if u["username"] == username_or_email or u["email"] == username_or_email:
            if u["password_hash"] == hashlib.sha256(password.encode()).hexdigest():
                return u
    return None

# === TEMPLATE HTML (GIAO DIEN WEB) ===
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ shop_name }}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: Arial, sans-serif; background: #f0f2f5; padding: 20px; }
        .container { max-width: 1200px; margin: auto; background: white; border-radius: 10px; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        .header { text-align: center; padding: 20px 0; border-bottom: 2px solid #e74c3c; }
        .header h1 { color: #e74c3c; }
        .zalo-badge { background: #0088cc; color: white; padding: 5px 15px; border-radius: 20px; display: inline-block; margin: 10px 0; }
        .menu { display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0; justify-content: center; }
        .menu a, .menu button { background: #3498db; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; border: none; cursor: pointer; }
        .menu a:hover, .menu button:hover { background: #2980b9; }
        .products { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; margin-top: 20px; }
        .product-card { border: 1px solid #ddd; border-radius: 8px; padding: 15px; background: #fafafa; }
        .product-card h3 { color: #2c3e50; }
        .product-card .price { color: #e74c3c; font-size: 1.2em; font-weight: bold; }
        .product-card .stock { color: #27ae60; }
        .btn-buy { background: #27ae60; color: white; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer; margin-top: 10px; }
        .btn-buy:hover { background: #2ecc71; }
        .login-form { max-width: 400px; margin: 40px auto; padding: 30px; background: #f9f9f9; border-radius: 8px; }
        .login-form input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; }
        .login-form button { width: 100%; padding: 10px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; }
        .flash { padding: 10px; background: #f1c40f; margin: 10px 0; border-radius: 4px; }
        .order-list { margin-top: 20px; }
        .order-item { border-bottom: 1px solid #eee; padding: 10px 0; }
        .admin-panel { background: #ecf0f1; padding: 20px; border-radius: 8px; margin-top: 20px; }
        .admin-panel input, .admin-panel textarea, .admin-panel select { width: 100%; padding: 8px; margin: 5px 0; }
        .admin-panel button { background: #e67e22; color: white; padding: 10px; border: none; border-radius: 4px; cursor: pointer; }
        .footer { text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #7f8c8d; }
        .register-link { text-align: center; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{{ shop_name }}</h1>
            <p>Xin Chào Quý Khách, Chúc Quý Khách Tham Khảo Vui Vẻ</p>
            <div class="zalo-badge">📱 Zalo: {{ zalo }}</div>
            {% if session.user %}
                <p>👤 {{ session.user.full_name or session.user.username }} | <a href="{{ url_for('logout') }}">Đăng xuất</a></p>
            {% endif %}
        </div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash">{{ messages[0] }}</div>
            {% endif %}
        {% endwith %}

        {% if not session.user %}
        <!-- FORM DANG NHAP -->
        <div class="login-form">
            <h2>Đăng nhập</h2>
            <form method="POST" action="{{ url_for('login') }}">
                <input type="text" name="username" placeholder="Email / Username" required>
                <input type="password" name="password" placeholder="Mật khẩu" required>
                <button type="submit">Đăng nhập</button>
            </form>
            <div class="register-link">
                <a href="{{ url_for('register') }}">Đăng ký tài khoản mới</a>
            </div>
        </div>
        {% else %}
        <!-- MENU CHINH -->
        <div class="menu">
            <a href="{{ url_for('index') }}">Trang chủ</a>
            <a href="{{ url_for('category', cat='Android') }}">Android</a>
            <a href="{{ url_for('category', cat='iOS') }}">iOS</a>
            <a href="{{ url_for('category', cat='PC') }}">PC</a>
            <a href="{{ url_for('orders') }}">Đơn hàng của tôi</a>
            {% if session.user.role == 'admin' %}
                <a href="{{ url_for('admin') }}">Quản trị</a>
            {% endif %}
        </div>

        <!-- HIEN THI SAN PHAM -->
        <div class="products">
            {% for p in products %}
            <div class="product-card">
                <h3>{{ p.name }}</h3>
                <p>{{ p.features }}</p>
                <p>{{ p.warranty }}</p>
                <div class="price">{{ p.price }} {{ currency }}</div>
                <div class="stock">Còn: {{ p.stock }} | Đã bán: {{ p.sold }}</div>
                <p>Nền tảng: {{ p.platform }}</p>
                <form method="POST" action="{{ url_for('buy') }}">
                    <input type="hidden" name="product_id" value="{{ p.id }}">
                    <input type="number" name="quantity" value="1" min="1" max="{{ p.stock }}" style="width:60px;">
                    <button class="btn-buy" type="submit">Mua ngay</button>
                </form>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="footer">
            <p>Shop Uy Tín Hàng Đầu - Liên hệ Zalo {{ zalo }}</p>
        </div>
    </div>
</body>
</html>
"""

# === ROUTES (CAC TRANG WEB) ===
@app.route('/')
def index():
    products = load_products()
    return render_template_string(HTML_TEMPLATE, 
                                shop_name=SHOP_NAME, 
                                zalo=ZALO, 
                                currency=CURRENCY,
                                products=products,
                                session=session)

@app.route('/category/<cat>')
def category(cat):
    products = [p for p in load_products() if p["category"].lower() == cat.lower()]
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
    user = login_user(username, password)
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
        if register_user(username, email, password, full_name, phone):
            flash('Đăng ký thành công! Vui lòng đăng nhập.')
        else:
            flash('Tên đăng nhập hoặc email đã tồn tại!')
        return redirect(url_for('index'))
    
    # Form dang ky
    return '''
    <div style="max-width:400px; margin:40px auto; padding:30px; background:#f9f9f9; border-radius:8px;">
        <h2>Đăng ký tài khoản</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Tên đăng nhập" required style="width:100%; padding:10px; margin:5px 0;"><br>
            <input type="email" name="email" placeholder="Email" required style="width:100%; padding:10px; margin:5px 0;"><br>
            <input type="password" name="password" placeholder="Mật khẩu" required style="width:100%; padding:10px; margin:5px 0;"><br>
            <input type="text" name="full_name" placeholder="Họ tên" style="width:100%; padding:10px; margin:5px 0;"><br>
            <input type="text" name="phone" placeholder="Số điện thoại" style="width:100%; padding:10px; margin:5px 0;"><br>
            <button type="submit" style="width:100%; padding:10px; background:#3498db; color:white; border:none; border-radius:4px; cursor:pointer;">Đăng ký</button>
        </form>
        <p style="text-align:center; margin-top:10px;"><a href="/">Quay lại trang chủ</a></p>
    </div>
    '''

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Đã đăng xuất.')
    return redirect(url_for('index'))

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
    order = create_order(product_id, quantity, user['full_name'] or user['username'], user.get('phone', 'Chưa cập nhật'))
    
    if order:
        flash(f'Đặt hàng thành công! Mã đơn: {order["order_id"]}. Tổng: {order["total"]} {CURRENCY}. Vui lòng thanh toán qua Zalo {ZALO}.')
    else:
        flash('Lỗi đặt hàng! Kiểm tra số lượng hoặc sản phẩm.')
    return redirect(url_for('index'))

@app.route('/orders')
def orders():
    if 'user' not in session:
        return redirect(url_for('index'))
    
    user_orders = [o for o in load_orders() if o['phone'] == session['user'].get('phone')]
    
    html = '''
    <div style="max-width:800px; margin:20px auto; padding:20px; background:white; border-radius:8px;">
        <h2>Đơn hàng của tôi</h2>
        <a href="/">← Quay lại trang chủ</a>
        <div style="margin-top:20px;">
    '''
    if not user_orders:
        html += '<p>Bạn chưa có đơn hàng nào.</p>'
    else:
        for o in user_orders:
            html += f'''
            <div style="border-bottom:1px solid #eee; padding:10px 0;">
                <b>{o['order_id']}</b> - {o['product_name']} x{o['quantity']} - {o['total']} {CURRENCY} - <b>{o['status']}</b>
                <br><small>Ngày đặt: {o['created']}</small>
            </div>
            '''
    html += '</div></div>'
    return html

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if 'user' not in session or session['user']['role'] != 'admin':
        return "Bạn không có quyền truy cập!", 403
    
    if request.method == 'POST':
        # Them san pham
        name = request.form.get('name')
        category = request.form.get('category')
        try:
            price = float(request.form.get('price'))
            stock = int(request.form.get('stock'))
        except:
            flash('Giá hoặc số lượng không hợp lệ!')
            return redirect(url_for('admin'))
        
        description = request.form.get('description', '')
        features = request.form.get('features', '')
        platform = request.form.get('platform', '')
        warranty = request.form.get('warranty', '')
        
        add_product(name, category, price, stock, description, features, platform, warranty)
        flash('Thêm sản phẩm thành công!')
        return redirect(url_for('admin'))
    
    # Hien thi form admin + danh sach don hang + danh sach san pham
    orders = load_orders()
    products = load_products()
    
    html = '''
    <div style="max-width:1000px; margin:20px auto; padding:20px; background:white; border-radius:8px;">
        <h2>Quản trị Shop</h2>
        <a href="/">← Trang chủ</a>
        
        <div style="background:#ecf0f1; padding:20px; border-radius:8px; margin:20px 0;">
            <h3>Thêm sản phẩm mới</h3>
            <form method="POST">
                <input type="text" name="name" placeholder="Tên sản phẩm" required style="width:100%; padding:8px; margin:5px 0;">
                <input type="text" name="category" placeholder="Danh mục (Android/iOS/PC)" required style="width:100%; padding:8px; margin:5px 0;">
                <input type="number" name="price" placeholder="Giá (VND)" required style="width:100%; padding:8px; margin:5px 0;">
                <input type="number" name="stock" placeholder="Số lượng" required style="width:100%; padding:8px; margin:5px 0;">
                <textarea name="description" placeholder="Mô tả" style="width:100%; padding:8px; margin:5px 0;"></textarea>
                <input type="text" name="features" placeholder="Tính năng nổi bật" style="width:100%; padding:8px; margin:5px 0;">
                <input type="text" name="platform" placeholder="Nền tảng" style="width:100%; padding:8px; margin:5px 0;">
                <input type="text" name="warranty" placeholder="Bảo hành" style="width:100%; padding:8px; margin:5px 0;">
                <button type="submit" style="background:#e67e22; color:white; padding:10px 20px; border:none; border-radius:4px; cursor:pointer;">Thêm sản phẩm</button>
            </form>
        </div>
        
        <h3>Danh sách sản phẩm</h3>
        <table style="width:100%; border-collapse:collapse; margin:10px 0;">
            <tr style="background:#3498db; color:white;">
                <th style="padding:8px;">ID</th><th>Tên</th><th>Giá</th><th>Tồn</th><th>Đã bán</th>
            </tr>
    '''
    for p in products:
        html += f'''
        <tr style="border-bottom:1px solid #ddd;">
            <td style="padding:8px;">{p['id'][:6]}</td>
            <td>{p['name']}</td>
            <td>{p['price']} {CURRENCY}</td>
            <td>{p['stock']}</td>
            <td>{p['sold']}</td>
        </tr>
        '''
    
    html += '''
        </table>
        <h3>Danh sách đơn hàng</h3>
        <table style="width:100%; border-collapse:collapse; margin:10px 0;">
            <tr style="background:#e67e22; color:white;">
                <th style="padding:8px;">Mã đơn</th><th>Sản phẩm</th><th>Tổng</th><th>Trạng thái</th><th>Người mua</th>
            </tr>
    '''
    for o in orders:
        html += f'''
        <tr style="border-bottom:1px solid #ddd;">
            <td style="padding:8px;">{o['order_id']}</td>
            <td>{o['product_name']}</td>
            <td>{o['total']} {CURRENCY}</td>
            <td>{o['status']}</td>
            <td>{o['buyer']}</td>
        </tr>
        '''
    
    html += '''
        </table>
    </div>
    '''
    return html

# === KHOI TAO DU LIEU MAU ===
def init_sample_data():
    init_files()
    if not load_products():
        sample = [
            ("Pixel 1.0", "Android", 350000, 10, "Nhiều Chức Năng Hot", "Full Đỏ Dễ Dàng Với AimLegit", "Android", "An Toàn Acc Chính Band Hoàn X2"),
            ("Aim Proxy", "iOS", 0, 6, "Kéo Là Đỏ", "Đi Rank Phòng Đều Ok", "iOS", ""),
            ("AimBot PC", "PC", 0, 9, "Esp,Aimbot,Ai player", "An Toàn Trên Acc Chính", "PC", ""),
            ("Migul Pro 1 Tháng", "iOS", 0, 9, "Nhiều Chức Năng Hơn Lite", "Antiban", "iOS", ""),
            ("Fluorite 1 Tháng", "iOS", 0, 9, "Nhiều Chức Năng", "Chơi Được Acc Chính", "iOS", ""),
            ("Aim Cổ", "PC", 0, 10, "Kéo Là Đỏ", "An toàn Acc Chính", "PC", ""),
            ("HeadLock", "Android", 0, 10, "Khóa Tâm Vùng Đầu", "An Toàn Acc Chính, Cân Mọi Chế Độ", "Android", ""),
            ("Aimlock V2", "Android", 0, 10, "Khả Năng Bám Đầu Cao Hơn V1", "Cân Mọi Map, An Toàn Cho Acc Chính", "Android", ""),
        ]
        for name, cat, price, stock, desc, features, platform, warranty in sample:
            add_product(name, cat, price, stock, desc, features, platform, warranty)
    
    # Tao admin mac dinh
    users = load_users()
    if not any(u["username"] == "admin" for u in users):
        register_user("admin", "admin@thanhson.shop", "admin123", "Administrator", ZALO)
        users = load_users()
        for u in users:
            if u["username"] == "admin":
                u["role"] = "admin"
                save_users(users)
                break

# === CHAY APP ===
if __name__ == "__main__":
    init_sample_data()
    print("="*50)
    print("SHOP THANH SON DA KHOI TAO THANH CONG!")
    print("Dang chay tren Render.com hoac localhost")
    print("="*50)
    app.run(host='0.0.0.0', port=10000)
