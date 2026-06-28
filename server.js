const express = require('express');
const session = require('express-session');
const cookieParser = require('cookie-parser');
const bcrypt = require('bcrypt');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const crypto = require('crypto');
process.on('uncaughtException', (err) => {
  console.error('❌ UNCAUGHT EXCEPTION:', err.stack || err);
});
process.on('unhandledRejection', (reason) => {
  console.error('❌ UNHANDLED REJECTION:', reason);
});
const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(session({
  secret: 'super_secret_key_change_me',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 24 * 60 * 60 * 1000 } // 1 ngày
}));

// Phục vụ file tĩnh (frontend)
app. use (express. static(__dirname)) ;
// Khởi tạo database
const db = new sqlite3.Database('./database.sqlite');

// Tạo bảng (nếu chưa có)
db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    balance INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS packages (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price INTEGER NOT NULL,
    days INTEGER NOT NULL,
    description TEXT
  )`);

  // Chèn các gói mặc định nếu chưa có
  const pkgStmt = db.prepare(`INSERT OR IGNORE INTO packages (id, name, price, days) VALUES (?, ?, ?, ?)`);
  pkgStmt.run('p1', 'Key 1 Ngày', 10000, 1);
  pkgStmt.run('p2', 'Key 7 Ngày', 30000, 7);
  pkgStmt.run('p3', 'Key 30 Ngày', 65000, 30);
  pkgStmt.run('padced7', 'Proxy Key Vĩnh Viễn', 200000, 9999);
  pkgStmt.finalize();

  db.run(`CREATE TABLE IF NOT EXISTS keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_text TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    package_id TEXT NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active',
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(package_id) REFERENCES packages(id)
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,          -- 'buy' hoặc 'topup'
    amount INTEGER NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
  )`);

  // Tạo user admin mặc định (để test)
  const adminPwd = bcrypt.hashSync('admin123', 10);
  db.run(`INSERT OR IGNORE INTO users (username, password, balance) VALUES (?, ?, ?)`, ['admin', adminPwd, 999999]);
});

// Helper: lấy user từ session
function getUser(req) {
  return new Promise((resolve, reject) => {
    if (!req.session.userId) return resolve(null);
    db.get('SELECT id, username, balance FROM users WHERE id = ?', [req.session.userId], (err, row) => {
      if (err) return reject(err);
      resolve(row);
    });
  });
}

// Helper: tạo key ngẫu nhiên
function generateKey() {
  return crypto.randomBytes(8).toString('hex').toUpperCase();
}

// Helper: tính ngày hết hạn
function addDays(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

// ─── API ROUTES ─────────────────────────

// Đăng ký
app.post('/api/register', async (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ ok: false, err: 'Thiếu thông tin' });
  }
  try {
    const hashed = await bcrypt.hash(password, 10);
    db.run('INSERT INTO users (username, password) VALUES (?, ?)', [username, hashed], function(err) {
      if (err) {
        if (err.message.includes('UNIQUE')) {
          return res.status(400).json({ ok: false, err: 'Tên đăng nhập đã tồn tại' });
        }
        return res.status(500).json({ ok: false, err: err.message });
      }
      res.json({ ok: true, id: this.lastID });
    });
  } catch (err) {
    res.status(500).json({ ok: false, err: err.message });
  }
});

// Đăng nhập
app.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) {
    return res.status(400).json({ ok: false, err: 'Thiếu thông tin' });
  }
  db.get('SELECT * FROM users WHERE username = ?', [username], async (err, user) => {
    if (err || !user) {
      return res.status(401).json({ ok: false, err: 'Sai tên đăng nhập hoặc mật khẩu' });
    }
    const match = await bcrypt.compare(password, user.password);
    if (!match) {
      return res.status(401).json({ ok: false, err: 'Sai tên đăng nhập hoặc mật khẩu' });
    }
    req.session.userId = user.id;
    res.json({ ok: true, username: user.username, balance: user.balance });
  });
});

// Kiểm tra trạng thái đăng nhập + số dư
app.get('/api/balance', async (req, res) => {
  const user = await getUser(req);
  if (!user) {
    return res.json({ logged_in: false });
  }
  res.json({ logged_in: true, username: user.username, balance: user.balance });
});

// Mua gói
app.post('/api/buy/:pid', async (req, res) => {
  const pid = req.params.pid;
  const user = await getUser(req);
  if (!user) {
    return res.status(401).json({ ok: false, err: 'Vui lòng đăng nhập' });
  }

  // Lấy thông tin gói
  db.get('SELECT * FROM packages WHERE id = ?', [pid], (err, pkg) => {
    if (err || !pkg) {
      return res.status(404).json({ ok: false, err: 'Gói không tồn tại' });
    }

    if (user.balance < pkg.price) {
      return res.status(400).json({ ok: false, err: 'Số dư không đủ', need_topup: true });
    }

    // Bắt đầu transaction (dùng db.run trong callback)
    db.run('BEGIN TRANSACTION');

    // 1. Trừ tiền
    const newBalance = user.balance - pkg.price;
    db.run('UPDATE users SET balance = ? WHERE id = ?', [newBalance, user.id]);

    // 2. Tạo key
    const keyText = generateKey();
    const expiresAt = addDays(new Date(), pkg.days);
    db.run('INSERT INTO keys (key_text, user_id, package_id, expires_at) VALUES (?, ?, ?, ?)',
      [keyText, user.id, pid, expiresAt.toISOString()]);

    // 3. Ghi transaction (buy)
    db.run('INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)',
      [user.id, 'buy', pkg.price, `Mua ${pkg.name}`]);

    db.run('COMMIT', (err) => {
      if (err) {
        db.run('ROLLBACK');
        return res.status(500).json({ ok: false, err: err.message });
      }
      res.json({
        ok: true,
        key: keyText,
        expires: expiresAt.toLocaleDateString('vi-VN'),
        new_balance: newBalance,
        package: pkg.name
      });
    });
  });
});

// Activity: Top nạp + lịch sử gần đây
app.get('/api/activity', (req, res) => {
  // 1. Top nạp (tổng số tiền nạp của từng user)
  const topNap = db.all(`SELECT u.username, SUM(t.amount) as total 
                         FROM transactions t 
                         JOIN users u ON u.id = t.user_id 
                         WHERE t.type = 'topup' 
                         GROUP BY u.id 
                         ORDER BY total DESC 
                         LIMIT 10`, (err, topRows) => {
    if (err) return res.status(500).json({ err: err.message });

    // 2. Lịch sử gần đây (lấy 20 giao dịch)
    db.all(`SELECT t.id, t.type, t.amount, t.description, t.created_at as time, u.username 
            FROM transactions t 
            JOIN users u ON u.id = t.user_id 
            ORDER BY t.created_at DESC 
            LIMIT 20`, (err2, histRows) => {
      if (err2) return res.status(500).json({ err: err2.message });
      res.json({
        top_nap: topRows.map(r => ({ username: r.username, total: r.total })),
        history: histRows.map(r => ({
          type: r.type,
          username: r.username,
          amount: r.amount,
          desc: r.description,
          time: r.time
        }))
      });
    });
  });
});

// Lấy danh sách đơn hàng của user (để hiển thị trang /orders)
app.get('/api/orders', async (req, res) => {
  const user = await getUser(req);
  if (!user) return res.status(401).json({ ok: false, err: 'Chưa đăng nhập' });

  db.all(`SELECT k.key_text, k.expires_at, k.created_at, p.name as package_name, p.days 
          FROM keys k 
          JOIN packages p ON k.package_id = p.id 
          WHERE k.user_id = ? 
          ORDER BY k.created_at DESC`, [user.id], (err, rows) => {
    if (err) return res.status(500).json({ ok: false, err: err.message });
    res.json({ ok: true, orders: rows });
  });
});

// Đăng xuất
app.get('/api/logout', (req, res) => {
  req.session.destroy();
  res.json({ ok: true });
});

// Bắt tất cả route khác trả về index.html (cho SPA)
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Khởi động server
app.get ('*', (req, res) => {
  res. sendFile(path.join(__dirname,
'index.html'));
}) ;
