const express = require('express');
const session = require('express-session');
const cookieParser = require('cookie-parser');
const bcrypt = require('bcrypt');
const sqlite3 = require('sqlite3').verbose();
const path = require('path');
const crypto = require('crypto');

const app = express();
const PORT = process.env.PORT || 3000;

// Bắt lỗi toàn cục để log chi tiết
process.on('uncaughtException', (err) => {
  console.error('❌ UNCAUGHT EXCEPTION:', err.stack || err);
});
process.on('unhandledRejection', (reason) => {
  console.error('❌ UNHANDLED REJECTION:', reason);
});

app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use(cookieParser());
app.use(session({
  secret: 'super_secret_key_please_change',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 24 * 60 * 60 * 1000 }
}));

// Phục vụ file tĩnh từ thư mục public
app.use(express.static(path.join(__dirname, 'public')));

// Database
const db = new sqlite3.Database('./database.sqlite', (err) => {
  if (err) {
    console.error('❌ Lỗi kết nối database:', err.message);
  } else {
    console.log('✅ Kết nối database thành công');
  }
});

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
    days INTEGER NOT NULL
  )`);

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

  // Tạo admin
  const adminPwd = bcrypt.hashSync('admin123', 10);
  db.run(`INSERT OR IGNORE INTO users (username, password, balance) VALUES (?, ?, ?)`, ['admin', adminPwd, 999999]);
});

// Helper
function getUser(req) {
  return new Promise((resolve, reject) => {
    if (!req.session.userId) return resolve(null);
    db.get('SELECT id, username, balance FROM users WHERE id = ?', [req.session.userId], (err, row) => {
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

// API routes
app.post('/api/register', async (req, res) => {
  const { username, password } = req.body;
  if (!username || !password) return res.status(400).json({ ok: false, err: 'Thiếu thông tin' });
  try {
    const hashed = await bcrypt.hash(password, 10);
    db.run('INSERT INTO users (username, password) VALUES (?, ?)', [username, hashed], function(err) {
      if (err) return res.status(400).json({ ok: false, err: err.message.includes('UNIQUE') ? 'Tên đã tồn tại' : err.message });
      res.json({ ok: true, id: this.lastID });
    });
  } catch (err) {
    res.status(500).json({ ok: false, err: err.message });
  }
});

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

app.get('/api/balance', async (req, res) => {
  const user = await getUser(req);
  if (!user) return res.json({ logged_in: false });
  res.json({ logged_in: true, username: user.username, balance: user.balance });
});

app.post('/api/buy/:pid', async (req, res) => {
  const pid = req.params.pid;
  const user = await getUser(req);
  if (!user) return res.status(401).json({ ok: false, err: 'Vui lòng đăng nhập' });
  db.get('SELECT * FROM packages WHERE id = ?', [pid], (err, pkg) => {
    if (err || !pkg) return res.status(404).json({ ok: false, err: 'Gói không tồn tại' });
    if (user.balance < pkg.price) return res.status(400).json({ ok: false, err: 'Số dư không đủ', need_topup: true });
    db.run('BEGIN TRANSACTION');
    const newBalance = user.balance - pkg.price;
    db.run('UPDATE users SET balance = ? WHERE id = ?', [newBalance, user.id]);
    const keyText = generateKey();
    const expiresAt = addDays(new Date(), pkg.days);
    db.run('INSERT INTO keys (key_text, user_id, package_id, expires_at) VALUES (?, ?, ?, ?)',
      [keyText, user.id, pid, expiresAt.toISOString()]);
    db.run('INSERT INTO transactions (user_id, type, amount, description) VALUES (?, ?, ?, ?)',
      [user.id, 'buy', pkg.price, `Mua ${pkg.name}`]);
    db.run('COMMIT', (err) => {
      if (err) { db.run('ROLLBACK'); return res.status(500).json({ ok: false, err: err.message }); }
      res.json({ ok: true, key: keyText, expires: expiresAt.toLocaleDateString('vi-VN'), new_balance: newBalance });
    });
  });
});

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

app.get('/api/logout', (req, res) => {
  req.session.destroy();
  res.json({ ok: true });
});

// Route mặc định trả về index.html
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`✅ Server chạy tại http://localhost:${PORT}`);
  console.log(`📁 Phục vụ file từ public/`);
});
