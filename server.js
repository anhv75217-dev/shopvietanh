const express = require('express');
const session = require('express-session');
const cookieParser = require('cookie-parser');
const bcrypt = require('bcrypt');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const crypto = require('crypto');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(session({
  secret: 'super_secret_key_please_change',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 24 * 60 * 60 * 1000 }
}));

// Phục vụ file tĩnh
app.use(express.static(path.join(__dirname, 'public')));

// Database
const db = new sqlite3.Database('./database.sqlite', (err) => {
  if (err) console.error('❌ Lỗi DB:', err.message);
  else console.log('✅ Kết nối DB thành công');
});

db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT,
    password TEXT NOT NULL,
    balance INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS packages (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    price INTEGER NOT NULL,
    days INTEGER NOT NULL
  )`);

  const pkgStmt = db.prepare(`INSERT OR IGNORE INTO packages (id, name, price, days) VALUES (?, ?, ?, ?)`);
  pkgStmt.run('p1', 'Proxy 1 Ngày', 10000, 1);
  pkgStmt.run('p2', 'Proxy 1 Tuần', 30000, 7);
  pkgStmt.run('p3', 'Proxy 1 Tháng', 65000, 30);
  pkgStmt.run('padced7', 'Proxy Vĩnh Viễn', 200000, 9999);
  pkgStmt.finalize();

  db.run(`CREATE TABLE IF NOT EXISTS keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_text TEXT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    package_id TEXT NOT NULL,
    price INTEGER NOT NULL,
    expires_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active',
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(package_id) REFERENCES packages(id)
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    amount INTEGER NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
  )`);

  const adminPwd = bcrypt.hashSync('admin123', 10);
  db.run(`INSERT OR IGNORE INTO users (username, email, password, balance) VALUES (?, ?, ?, ?)`,
    ['admin', 'admin@shop.com', adminPwd, 999999]);
});

// Helper functions
function getUser(req) {
  return new Promise((resolve, reject) => {
    if (!req.session.userId) return resolve(null);
    db.get('SELECT id, username, email, balance FROM users WHERE id = ?', [req.session.userId], (err, row) => {
      if (err) return reject(err);
      resolve(row);
    });
  });
}

function generateKey() {
  return crypto.randomBytes(8).toString('hex').toUpperCase();
}

function addDays(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

// ─── API ────────────────────────────────

// 1. Đăng ký
app.post('/api/register', async (req, res) => {
  const { username, email, password, captcha } = req.body;
  if (!username || !password) return res.status(400).json({ ok: false, err: 'Vui lòng điền đầy đủ' });
  if (password.length < 6) return res.status(400).json({ ok: false, err: 'Mật khẩu tối thiểu 6 ký tự' });
  if (captcha !== '3') return res.status(400).json({ ok: false, err: 'Captcha không đúng' });
  try {
    const hashed = await bcrypt.hash(password, 10);
    db.run('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
      [username, email || null, hashed], function(err) {
        if (err) {
          if (err.message.includes('UNIQUE')) return res.status(400).json({ ok: false, err: 'Tên đăng nhập đã tồn tại' });
          return res.status(500).json({ ok: false, err: err.message });
        }
        res.json({ ok: true, id: this.lastID });
      });
  } catch (e) {
    res.status(500).json({ ok: false, err: e.message });
  }
});

// 2. Đăng nhập
app.post('/api/login', (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) return res.status(400).json({ ok: false, err: 'Thiếu thông tin' });
  db.get('SELECT * FROM users WHERE username = ?', [username], async (err, user) => {
    if (err || !user) return res.status(401).json({ ok: false, err: 'Sai tên hoặc mật khẩu' });
    const match = await bcrypt.compare(password, user.password);
    if (!match) return res.status(401).json({ ok: false, err: 'Sai tên hoặc mật khẩu' });
    req.session.userId = user.id;
    res.json({ ok: true, username: user.username, balance: user.balance });
  });
});

// 3. Lấy số dư
app.get('/api/balance', async (req, res) => {
  const user = await getUser(req);
  if (!user) return res.json({ logged_in: false });
  res.json({ logged_in: true, username: user.username, balance: user.balance });
});

// 4. Đăng xuất
app.get('/api/logout', (req, res) => {
  req.session.destroy();
  res.json({ ok: true });
});

// 5. Mua gói
app.post('/api/buy/:pid', async (req, res) => {
  const pid = req.params.pid;
  const user = await getUser(req);
  if (!user) return res.status(401).json({ ok: false, err: 'Vui lòng đăng nhập' });

  db.get('SELECT * FROM packages WHERE id = ?', [pid], (err, pkg) => {
    if (err || !pkg) return res.status(404).json({ ok: false, err: 'Gói không tồn tại' });
    if (user.balance < pkg.price) {
      return res.status(400).json({ ok: false, err: 'Số dư không đủ', need_topup: true });
    }

    db.run('BEGIN TRANSACTION');
    const newBalance = user.balance - pkg.price;
    db.run('UPDATE users SET balance = ? WHERE id = ?', [newBalance, user.id]);
    const keyText = generateKey();
    const expiresAt = addDays(new Date(), pkg.days);
    db.run('INSERT INTO keys (key_text, user_id, package_id, price, expires_at) VALUES (?, ?, ?, ?, ?)',
      [keyText, user.id, pid, pkg.price, expiresAt.toISOString()]);
    db.run('INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)',
      [user.id, 'buy', pkg.price, `Mua ${pkg.name}`]);
    db.run('COMMIT', (err) => {
      if (err) { db.run('ROLLBACK'); return res.status(500).json({ ok: false, err: err.message }); }
      res.json({ ok: true, key: keyText, expires: expiresAt.toLocaleDateString('vi-VN'), new_balance: newBalance });
    });
  });
});

// 6. Nạp tiền
app.post('/api/topup', async (req, res) => {
  const user = await getUser(req);
  if (!user) return res.status(401).json({ ok: false, err: 'Vui lòng đăng nhập' });
  const { amount } = req.body;
  if (!amount || amount <= 0) return res.status(400).json({ ok: false, err: 'Số tiền không hợp lệ' });
  db.run('BEGIN TRANSACTION');
  db.run('UPDATE users SET balance = balance + ? WHERE id = ?', [amount, user.id]);
  db.run('INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)',
    [user.id, 'topup', amount, 'Nạp tiền']);
  db.run('COMMIT', (err) => {
    if (err) { db.run('ROLLBACK'); return res.status(500).json({ ok: false, err: err.message }); }
    db.get('SELECT balance FROM users WHERE id = ?', [user.id], (err2, row) => {
      if (err2) return res.status(500).json({ ok: false, err: err2.message });
      res.json({ ok: true, new_balance: row.balance });
    });
  });
});

// 7. Lịch sử đơn hàng
app.get('/api/orders', async (req, res) => {
  const user = await getUser(req);
  if (!user) return res.status(401).json({ ok: false, err: 'Chưa đăng nhập' });
  db.all(`SELECT k.key_text, k.expires_at, k.created_at, k.price, p.name as package_name, p.days
          FROM keys k
          JOIN packages p ON k.package_id = p.id
          WHERE k.user_id = ?
          ORDER BY k.created_at DESC`, [user.id], (err, rows) => {
    if (err) return res.status(500).json({ ok: false, err: err.message });
    res.json({ ok: true, orders: rows });
  });
});

// 8. Activity
app.get('/api/activity', (req, res) => {
  db.all(`SELECT u.username, SUM(t.amount) as total
           FROM transactions t
           JOIN users u ON u.id = t.user_id
           WHERE t.type = 'topup'
           GROUP BY u.id
           ORDER BY total DESC
           LIMIT 10`, (err, topRows) => {
    if (err) return res.status(500).json({ err: err.message });
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

// ─── ADMIN API ──────────────────────────
async function isAdmin(req, res, next) {
  const user = await getUser(req);
  if (!user || user.username !== 'admin') {
    return res.status(403).json({ ok: false, err: 'Bạn không có quyền' });
  }
  next();
}

app.get('/api/admin/users', isAdmin, (req, res) => {
  db.all('SELECT id, username, email, balance, created_at FROM users ORDER BY id DESC', (err, rows) => {
    if (err) return res.status(500).json({ ok: false, err: err.message });
    res.json({ ok: true, users: rows });
  });
});

app.get('/api/admin/keys', isAdmin, (req, res) => {
  db.all(`SELECT k.id, k.key_text, k.user_id, u.username, k.package_id, k.price, k.expires_at, k.created_at, k.status
          FROM keys k
          JOIN users u ON u.id = k.user_id
          ORDER BY k.created_at DESC`, (err, rows) => {
    if (err) return res.status(500).json({ ok: false, err: err.message });
    res.json({ ok: true, keys: rows });
  });
});

app.get('/api/admin/transactions', isAdmin, (req, res) => {
  db.all(`SELECT t.id, t.user_id, u.username, t.type, t.amount, t.description, t.created_at as time
          FROM transactions t
          JOIN users u ON u.id = t.user_id
          ORDER BY t.created_at DESC`, (err, rows) => {
    if (err) return res.status(500).json({ ok: false, err: err.message });
    res.json({ ok: true, transactions: rows });
  });
});

app.post('/api/admin/topup', isAdmin, (req, res) => {
  const { userId, amount } = req.body;
  if (!userId || !amount || amount <= 0) {
    return res.status(400).json({ ok: false, err: 'Dữ liệu không hợp lệ' });
  }
  db.run('BEGIN TRANSACTION');
  db.run('UPDATE users SET balance = balance + ? WHERE id = ?', [amount, userId]);
  db.run('INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)',
    [userId, 'topup', amount, 'Admin nạp tiền']);
  db.run('COMMIT', (err) => {
    if (err) { db.run('ROLLBACK'); return res.status(500).json({ ok: false, err: err.message }); }
    db.get('SELECT balance FROM users WHERE id = ?', [userId], (err2, row) => {
      if (err2) return res.status(500).json({ ok: false, err: err2.message });
      res.json({ ok: true, new_balance: row.balance });
    });
  });
});

// Route mặc định trả về index.html
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`✅ Server chạy tại http://localhost:${PORT}`);
});
