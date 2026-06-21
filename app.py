from flask import Flask, render_template_string, request, redirect, url_for, session, flash
import hashlib
import json
import os
import datetime

app = Flask(__name__)
app.secret_key = "vietanh_super_secret_key_2026"

# === CAU HINH ===
SHOP_NAME = "SHOP UY TÍN HÀNG ĐẦU"
SHOP_OWNER = "Quản Trị Viên"
WELCOME = "Xin Chào Quý Khách, Chúc Quý Khách Tham Khảo Vui Vẻ"
ZALO = "0933121845"
CURRENCY = "VND"
HOT_DEAL = "350.000đ"
THONG_BAO = "Khi Mua Hàng Bị Vấn Đề Gì Hãy Liên Hệ Qua Zalo"

# File luu tru
PRODUCT_FILE = "vietanh_products.json"
ORDER_FILE = "vietanh_orders.json"
USER_FILE = "vietanh_users.json"

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

def delete_product(pid):
    products = load_products()
    products = [p for p in products if p["id"] != pid]
    save_products(products)
    return True

def update_product(pid, name, category, price, stock, description, features, platform, warranty):
    products = load_products()
    for p in products:
        if p["id"] == pid:
            p["name"] = name
            p["category"] = category
            p["price"] = float(price)
            p["stock"] = int(stock)
            p["description"] = description
            p["features"] = features
            p["platform"] = platform
            p["warranty"] = warranty
            p["status"] = "Sẵn hàng" if int(stock) > 0 else "Hết hàng"
            save_products(products)
            return True
    return False

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

def update_order_status(order_id, new_status):
    orders = load_orders()
    for o in orders:
        if o["order_id"] == order_id:
            o["status"] = new_status
            save_orders(orders)
            return True
    return False

def delete_order(order_id):
    orders = load_orders()
    orders = [o for o in orders if o["order_id"] != order_id]
    save_orders(orders)
    return True

# === QUAN LY USER (NANG CAO) ===
def load_users():
    with open(USER_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)

def register_user(username, email, password, full_name="", phone="", role="user"):
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
        "role": role,  # "admin" hoac "user"
        "created": str(datetime.datetime.now()),
        "last_login": None,
        "status": "active"  # active, banned
    }
    users.append(user)
    save_users(users)
    return True

def login_user(username_or_email, password):
    users = load_users()
    for u in users:
        if u["status"] == "banned":
            continue
        if u["username"] == username_or_email or u["email"] == username_or_email:
            if u["password_hash"] == hashlib.sha256(password.encode()).hexdigest():
                u["last_login"] = str(datetime.datetime.now())
                save_users(users)
                return u
    return None

def delete_user(user_id):
    users = load_users()
    users = [u for u in users if u["user_id"] != user_id]
    save_users(users)
    return True

def update_user_role(user_id, new_role):
    users = load_users()
    for u in users:
        if u["user_id"] == user_id:
            u["role"] = new_role
            save_users(users)
            return True
    return False

def toggle_user_status(user_id):
    users = load_users()
    for u in users:
        if u["user_id"] == user_id:
            u["status"] = "banned" if u["status"] == "active" else "active"
            save_users(users)
            return True
    return False

# === TEMPLATE HTML (GIAO DIEN ADMIN MO RONG) ===
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ shop_vietanh }}</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: Arial, sans-serif; background: #f5f5f5; }
        .container { max-width: 1200px; margin: auto; background: white; padding: 20px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }
        .header { text-align: center; padding: 20px 0; border-bottom: 3px solid #e74c3c; }
        .header h1 { color: #e74c3c; font-size: 2.5em; }
        .admin-badge { background: #2c3e50; color: white; padding: 5px 15px; border-radius: 20px; display: inline-block; margin: 10px 0; }
        .zalo-badge { background: #0088cc; color: white; padding: 8px 20px; border-radius: 30px; display: inline-block; margin: 15px 0; font-weight: bold; }
        .hot-deal { background: #e74c3c; color: white; padding: 12px; text-align: center; font-size: 1.5em; margin: 15px 0; border-radius: 5px; }
        .thong-bao { background: #f39c12; color: white; padding: 10px; text-align: center; border-radius: 5px; margin: 10px 0; }
        .menu { display: flex; flex-wrap: wrap; gap: 10px; margin: 20px 0; justify-content: center; border-bottom: 2px solid #ddd; padding-bottom: 15px; }
        .menu a, .menu button { background: #3498db; color: white; padding: 10px 25px; border-radius: 25px; text-decoration: none; border: none; cursor: pointer; font-weight: bold; }
        .menu a:hover, .menu button:hover { background: #2980b9; transform: scale(1.05); }
        .menu a.admin { background: #e67e22; }
        .menu a.admin:hover { background: #d35400; }
        .products { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 25px; margin-top: 20px; }
        .product-card { border: 1px solid #ddd; border-radius: 12px; padding: 18px; background: #fafafa; transition: 0.3s; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
        .product-card:hover { box-shadow: 0 5px 15px rgba(0,0,0,0.15); transform: translateY(-3px); }
        .product-card .status { color: #27ae60; font-weight: bold; }
        .product-card h3 { color: #2c3e50; font-size: 1.3em; margin: 5px 0; }
        .product-card .price { color: #e74c3c; font-size: 1.4em; font-weight: bold; margin: 10px 0; }
        .product-card .stock { color: #27ae60; }
        .btn-buy { background: #27ae60; color: white; padding: 10px 20px; border: none; border-radius: 25px; cursor: pointer; margin-top: 10px; font-weight: bold; width: 100%; }
        .btn-buy:hover { background: #2ecc71; }
        .login-form { max-width: 450px; margin: 40px auto; padding: 30px; background: #f9f9f9; border-radius: 12px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }
        .login-form input { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 25px; }
        .login-form button { width: 100%; padding: 12px; background: #3498db; color: white; border: none; border-radius: 25px; cursor: pointer; font-weight: bold; }
        .flash { padding: 12px; background: #f1c40f; margin: 15px 0; border-radius: 8px; text-align: center; font-weight: bold; }
        .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 2px solid #ddd; color: #7f8c8d; }
        .admin-panel { background: #ecf0f1; padding: 20px; border-radius: 12px; margin: 20px 0; }
        .admin-panel input, .admin-panel textarea, .admin-panel select { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ddd; border-radius: 25px; }
        .admin-panel button { background: #e67e22; color: white; padding: 12px; border: none; border-radius: 25px; cursor: pointer; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; }
        th { background: #2c3e50; color: white; padding: 10px; }
        td { padding: 10px; border-bottom: 1px solid #ddd; }
        .btn-small { padding: 5px 12px; border: none; border-radius: 15px; cursor: pointer; font-weight: bold; }
        .btn-danger { background: #e74c3c; color: white; }
        .btn-success { background: #27ae60; color: white; }
        .btn-warning { background: #f39c12; color: white; }
        .btn-primary { background: #3498db; color: white; }
        .order-item { border-bottom: 1px solid #eee; padding: 12px 0; }
        @media (max-width: 600px) { .products { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏪 {{ shop_vietanh }}</h1>
            <div class="admin-badge">{{ shop_owner }}</div>
            <div class="zalo-badge">📱 Zalo: {{ zalo }}</div>
            {% if session.user %}
                <p>👤 {{ session.user.full_name or session.user.username }} 
                {% if session.user.role == 'admin' %}⭐ Admin{% endif %}
                | <a href="{{ url_for('logout') }}" style="color:#e74c3c;">Đăng xuất</a></p>
            {% endif %}
        </div>

        <div class="hot-deal">🔥 HOT DEAL: {{ hot_deal }}</div>
        <div class="thong-bao">📢 {{ thong_bao }}</div>

        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="flash">{{ messages[0] }}</div>
            {% endif %}
        {% endwith %}

        {% if not session.user %}
        <!-- FORM DANG NHAP -->
        <div class="login-form">
            <h2>Chào mừng quay trở lại</h2>
            <p style="text-align:center; color:#555;">Hệ thống bán acc tự động, nạp tiền 24/7</p>
            <form method="POST" action="{{ url_for('login') }}">
                <input type="text" name="username" placeholder="Email / Username" required>
                <input type="password" name="password" placeholder="Mật khẩu" required>
                <button type="submit">Đăng nhập</button>
            </form>
            <div style="text-align:center; margin-top:15px;">
                <a href="{{ url_for('register') }}">Đăng ký tài khoản mới</a>
            </div>
        </div>
        {% else %}
        <!-- MENU CHINH -->
        <div class="menu">
            <a href="{{ url_for('index') }}">🏠 Trang chủ</a>
            <a href="{{ url_for('category', cat='Adroid') }}">📱 Adroid</a>
            <a href="{{ url_for('category', cat='Ios') }}">🍎 Ios</a>
            <a href="{{ url_for('category', cat='Pc') }}">💻 Pc</a>
            <a href="{{ url_for('orders') }}">📦 Đơn hàng</a>
            {% if session.user.role == 'admin' %}
                <a href="{{ url_for('admin_dashboard') }}" class="admin">⚙️ Admin</a>
            {% endif %}
        </div>

        <h2 style="margin:20px 0 10px; border-left:5px solid #e74c3c; padding-left:15px;">Danh mục sản phẩm</h2>
        <!-- HIEN THI SAN PHAM -->
        <div class="products">
            {% for p in products %}
            <div class="product-card">
                <div class="status">✅ Sẵn hàng</div>
                <h3>{{ p.name }}</h3>
                <div>{{ p.features }}</div>
                <div style="color:#2980b9; font-style:italic;">{{ p.warranty }}</div>
                <div class="price">{{ p.price }} {{ currency }}</div>
                <div class="stock">Còn: {{ p.stock }} | Đã bán: {{ p.sold }}</div>
                <div style="background:#ecf0f1; display:inline-block; padding:3px 10px; border-radius:15px; font-size:0.9em;">{{ p.platform }}</div>
                <form method="POST" action="{{ url_for('buy') }}">
                    <input type="hidden" name="product_id" value="{{ p.id }}">
                    <input type="number" name="quantity" value="1" min="1" max="{{ p.stock }}" style="width:60px; padding:5px; border-radius:15px; border:1px solid #ddd;">
                    <button class="btn-buy" type="submit">Mua ngay</button>
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

# === ROUTES ===
@app.route('/')
def index():
    products = load_products()
    return render_template_string(HTML_TEMPLATE, 
                                shop_name=SHOP_NAME,
                                shop_owner=SHOP_OWNER,
                                welcome=WELCOME,
                                zalo=ZALO,
                                hot_deal=HOT_DEAL,
                                thong_bao=THONG_BAO,
                                currency=CURRENCY,
                                products=products,
                                session=session)

@app.route('/category/<cat>')
def category(cat):
    products = [p for p in load_products() if p["category"].lower() == cat.lower()]
    return render_template_string(HTML_TEMPLATE,
                                shop_name=SHOP_NAME,
                                shop_owner=SHOP_OWNER,
                                welcome=WELCOME,
                                zalo=ZALO,
                                hot_deal=HOT_DEAL,
                                thong_bao=THONG_BAO,
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
    return '''
    <div style="max-width:450px; margin:40px auto; padding:30px; background:white; border-radius:12px; box-shadow:0 0 15px rgba(0,0,0,0.1);">
        <h2 style="text-align:center;">Đăng ký tài khoản</h2>
        <form method="POST">
            <input type="text" name="username" placeholder="Tên đăng nhập" required style="width:100%; padding:12px; margin:8px 0; border-radius:25px; border:1px solid #ddd;">
            <input type="email" name="email" placeholder="Email" required style="width:100%; padding:12px; margin:8px 0; border-radius:25px; border:1px solid #ddd;">
            <input type="password" name="password" placeholder="Mật khẩu" required style="width:100%; padding:12px; margin:8px 0; border-radius:25px; border:1px solid #ddd;">
            <input type="text" name="full_name" placeholder="Họ tên" style="width:100%; padding:12px; margin:8px 0; border-radius:25px; border:1px solid #ddd;">
            <input type="text" name="phone" placeholder="Số điện thoại" style="width:100%; padding:12px; margin:8px 0; border-radius:25px; border:1px solid #ddd;">
            <button type="submit" style="width:100%; padding:12px; background:#3498db; color:white; border:none; border-radius:25px; cursor:pointer; font-weight:bold;">Đăng ký</button>
        </form>
        <p style="text-align:center; margin-top:15px;"><a href="/">Quay lại trang chủ</a></p>
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
    <div style="max-width:800px; margin:20px auto; padding:20px; background:white; border-radius:12px; box-shadow:0 0 10px rgba(0,0,0,0.1);">
        <h2>📦 Đơn hàng của tôi</h2>
        <a href="/">← Quay lại trang chủ</a>
        <div style="margin-top:20px;">
    '''
    if not user_orders:
        html += '<p>Bạn chưa có đơn hàng nào.</p>'
    else:
        for o in user_orders:
            html += f'''
            <div class="order-item">
                <b>{o['order_id']}</b> - {o['product_name']} x{o['quantity']} - <b>{o['total']} {CURRENCY}</b> - Trạng thái: <b>{o['status']}</b>
                <br><small>Ngày đặt: {o['created']}</small>
            </div>
            '''
    html += '</div></div>'
    return html

# ==================== ADMIN DASHBOARD ====================
@app.route('/admin')
def admin_dashboard():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash('Bạn cần quyền Admin để truy cập!')
        return redirect(url_for('index'))
    
    users = load_users()
    orders = load_orders()
    products = load_products()
    
    html = '''
    <div style="max-width:1200px; margin:20px auto; padding:20px; background:white; border-radius:12px; box-shadow:0 0 10px rgba(0,0,0,0.1);">
        <h2>⚙️ ADMIN DASHBOARD</h2>
        <a href="/">← Trang chủ</a>
        <div style="display:flex; gap:20px; margin:20px 0; flex-wrap:wrap;">
            <div style="background:#3498db; color:white; padding:20px; border-radius:12px; flex:1; text-align:center;">
                <h3>Sản phẩm</h3>
                <p style="font-size:2em;">''' + str(len(products)) + '''</p>
                <a href="/admin/products" style="color:white; text-decoration:underline;">Quản lý</a>
            </div>
            <div style="background:#27ae60; color:white; padding:20px; border-radius:12px; flex:1; text-align:center;">
                <h3>Đơn hàng</h3>
                <p style="font-size:2em;">''' + str(len(orders)) + '''</p>
                <a href="/admin/orders" style="color:white; text-decoration:underline;">Quản lý</a>
            </div>
            <div style="background:#e67e22; color:white; padding:20px; border-radius:12px; flex:1; text-align:center;">
                <h3>Người dùng</h3>
                <p style="font-size:2em;">''' + str(len(users)) + '''</p>
                <a href="/admin/users" style="color:white; text-decoration:underline;">Quản lý</a>
            </div>
        </div>
    </div>
    '''
    return html

# === ADMIN: QUAN LY SAN PHAM ===
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
            add_product(name, category, price, stock, description, features, platform, warranty)
            flash('Thêm sản phẩm thành công!')
        elif action == 'delete':
            pid = request.form.get('pid')
            if delete_product(pid):
                flash('Xóa sản phẩm thành công!')
            else:
                flash('Không tìm thấy sản phẩm!')
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
            if update_product(pid, name, category, price, stock, description, features, platform, warranty):
                flash('Cập nhật sản phẩm thành công!')
            else:
                flash('Không tìm thấy sản phẩm!')
        return redirect(url_for('admin_products'))
    
    products = load_products()
    html = '''
    <div style="max-width:1200px; margin:20px auto; padding:20px; background:white; border-radius:12px; box-shadow:0 0 10px rgba(0,0,0,0.1);">
        <h2>📦 Quản lý sản phẩm</h2>
        <a href="/admin">← Dashboard</a> | <a href="/">Trang chủ</a>
        
        <!-- FORM THEM SAN PHAM -->
        <div class="admin-panel" style="margin:20px 0;">
            <h3>➕ Thêm sản phẩm mới</h3>
            <form method="POST">
                <input type="hidden" name="action" value="add">
                <input type="text" name="name" placeholder="Tên sản phẩm" required>
                <input type="text" name="category" placeholder="Danh mục (Adroid/Ios/Pc)" required>
                <input type="number" name="price" placeholder="Giá (VND)" required>
                <input type="number" name="stock" placeholder="Số lượng" required>
                <textarea name="description" placeholder="Mô tả"></textarea>
                <input type="text" name="features" placeholder="Tính năng nổi bật">
                <input type="text" name="platform" placeholder="Nền tảng">
                <input type="text" name="warranty" placeholder="Bảo hành">
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
            <td>{p['id'][:6]}</td>
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
                <button class="btn-small btn-warning" onclick="editProduct('{p['id']}','{p['name']}','{p['category']}','{p['price']}','{p['stock']}','{p['description']}','{p['features']}','{p['platform']}','{p['warranty']}')">Sửa</button>
            </td>
        </tr>
        '''
    
    html += '''
        </table>
    </div>
    <script>
    function editProduct(id, name, category, price, stock, description, features, platform, warranty) {
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
            <button type="submit" class="btn-small btn-success">Cập nhật</button>
            <button type="button" class="btn-small btn-danger" onclick="this.parentElement.remove()">Hủy</button>
        `;
        // Chen vao vi tri thich hop (duoi hang hien tai)
        var row = event.target.closest('tr');
        row.parentNode.insertBefore(form, row.nextSibling);
    }
    </script>
    '''
    return html

# === ADMIN: QUAN LY DON HANG ===
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
            if update_order_status(order_id, new_status):
                flash('Cập nhật trạng thái đơn hàng thành công!')
            else:
                flash('Không tìm thấy đơn hàng!')
        elif action == 'delete':
            if delete_order(order_id):
                flash('Xóa đơn hàng thành công!')
            else:
                flash('Không tìm thấy đơn hàng!')
        return redirect(url_for('admin_orders'))
    
    orders = load_orders()
    html = '''
    <div style="max-width:1200px; margin:20px auto; padding:20px; background:white; border-radius:12px; box-shadow:0 0 10px rgba(0,0,0,0.1);">
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
                        <option value="Chờ xác nhận" {"selected" if o['status']=='Chờ xác nhận' else ""}>Chờ xác nhận</option>
                        <option value="Đã xác nhận" {"selected" if o['status']=='Đã xác nhận' else ""}>Đã xác nhận</option>
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

# === ADMIN: QUAN LY NGUOI DUNG ===
@app.route('/admin/users', methods=['GET', 'POST'])
def admin_users():
    if 'user' not in session or session['user']['role'] != 'admin':
        flash('Bạn cần quyền Admin!')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        user_id = request.form.get('user_id')
        if action == 'delete':
            if delete_user(user_id):
                flash('Xóa người dùng thành công!')
            else:
                flash('Không tìm thấy người dùng!')
        elif action == 'change_role':
            new_role = request.form.get('role')
            if update_user_role(user_id, new_role):
                flash('Cập nhật vai trò thành công!')
            else:
                flash('Không tìm thấy người dùng!')
        elif action == 'toggle_status':
            if toggle_user_status(user_id):
                flash('Cập nhật trạng thái thành công!')
            else:
                flash('Không tìm thấy người dùng!')
        return redirect(url_for('admin_users'))
    
    users = load_users()
    html = '''
    <div style="max-width:1200px; margin:20px auto; padding:20px; background:white; border-radius:12px; box-shadow:0 0 10px rgba(0,0,0,0.1);">
        <h2>👥 Quản lý người dùng</h2>
        <a href="/admin">← Dashboard</a> | <a href="/">Trang chủ</a>
        
        <h3>Danh sách người dùng</h3>
        <table>
            <tr><th>ID</th><th>Tên đăng nhập</th><th>Email</th><th>Họ tên</th><th>Vai trò</th><th>Trạng thái</th><th>Hành động</th></tr>
    '''
    for u in users:
        html += f'''
        <tr>
            <td>{u['user_id'][:6]}</td>
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

# === KHOI TAO DU LIEU ===
def init_sample_data():
    init_files()
    if not load_products():
        sample = [
            ("Pixel 1.0", "Adroid", 350000, 10, "Nhiều Chức Năng Hot", "Full Đỏ Dễ Dàng Với AimLegit", "Adroid", "An Toàn Acc Chính Band Hoàn X2"),
            ("Aim Proxy", "Ios", 0, 6, "Kéo Là Đỏ", "Đi Rank Phòng Đều Ok", "Ios", ""),
            ("AimBot PC", "Pc", 0, 9, "Esp,Aimbot,Ai player", "An Toàn Trên Acc Chính", "Pc", ""),
            ("Migul Pro 1 Tháng", "Ios", 0, 9, "Nhiều Chức Năng Hơn Lite", "Antiban", "Ios", ""),
            ("Fluorite 1 Tháng", "Ios", 0, 9, "Nhiều Chức Năng", "Chơi Được Acc Chính", "Ios", ""),
            ("Aim Cổ", "Pc", 0, 10, "Kéo Là Đỏ", "An toàn Acc Chính", "Pc", ""),
            ("HeadLock", "Adroid", 0, 10, "Khóa Tâm Vùng Đầu", "An Toàn Acc Chính, Cân Mọi Chế Độ", "Adroid", ""),
            ("Aimlock V2", "Adroid", 0, 10, "Khả Năng Bám Đầu Cao Hơn V1", "Cân Mọi Map, An Toàn Cho Acc Chính", "Adroid", ""),
            ("AimLock V1", "Adroid", 0, 10, "Tăng Tỉ Lệ Bám Đầu", "An Toàn Acc Chính, Cân Mọi Chế Độ", "Adroid", ""),
            ("Menu Drip", "Adroid", 0, 10, "Khá An Toàn", "Đi Rank ổn", "Adroid", ""),
            ("Pixel 2.0", "Adroid", 0, 10, "Menu Nhiều Chức Năng", "Đi Rank Phòng Đều Ngon, Full Đỏ Dễ Dàng", "Adroid", ""),
            ("Migul Pro 1 Tuần", "Ios", 0, 12, "Nhiều Chức Năng Hơn Lite", "Antiban", "Ios", ""),
            ("Fluorite 1 Tuần", "Ios", 0, 10, "", "", "Ios", "")
        ]
        for name, cat, price, stock, desc, features, platform, warranty in sample:
            add_product(name, cat, price, stock, desc, features, platform, warranty)
    
    users = load_users()
    if not any(u["username"] == "admin" for u in users):
        register_user("admin", "admin@thanhson.shop", "admin123", "Administrator", ZALO, "admin")
        users = load_users()
        for u in users:
            if u["username"] == "admin":
                u["role"] = "admin"
                save_users(users)
                break

init_sample_data()

# === DUNG CHO PRODUCTION ===
application = app

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=10000)
