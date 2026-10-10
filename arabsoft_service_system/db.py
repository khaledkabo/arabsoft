import sqlite3, os, hashlib, secrets, shutil, datetime

APP_DIR = os.path.join(os.path.expanduser('~'), 'ArabSoftService')
os.makedirs(APP_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DIR, 'service_system.db')


def now(): return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def hash_password(password, salt=None):
    salt = salt or secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 120_000)
    return salt.hex(), h.hex()

def verify_password(password, salt_hex, hash_hex):
    try:
        return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), 120_000).hex() == hash_hex
    except Exception: return False

class DB:
    def __init__(self, path=DB_PATH):
        self.path=path; self.conn=sqlite3.connect(path); self.conn.row_factory=sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON'); self.conn.execute('PRAGMA journal_mode=WAL'); self.init()
    def execute(self, sql, params=(), commit=True):
        cur=self.conn.execute(sql, params)
        if commit: self.conn.commit()
        return cur
    def many(self, sql, params=()): return self.conn.execute(sql, params).fetchall()
    def one(self, sql, params=()): return self.conn.execute(sql, params).fetchone()
    def init(self):
        s='''
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT, salt TEXT NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'employee', active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT, phone2 TEXT, address TEXT, notes TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS technicians(id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT, specialty TEXT, salary REAL DEFAULT 0, active INTEGER DEFAULT 1, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS repairs(id INTEGER PRIMARY KEY, ticket_no TEXT UNIQUE NOT NULL, customer_id INTEGER NOT NULL, device_type TEXT, model TEXT, imei TEXT, serial TEXT, color TEXT, accessories TEXT, condition TEXT, customer_issue TEXT, technical_diagnosis TEXT, technician_id INTEGER, status TEXT NOT NULL DEFAULT 'received', priority TEXT DEFAULT 'normal', warranty_days INTEGER DEFAULT 0, warranty_until TEXT, estimated_cost REAL DEFAULT 0, labor REAL DEFAULT 0, discount REAL DEFAULT 0, paid REAL DEFAULT 0, delivered_at TEXT, notes TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(customer_id) REFERENCES customers(id), FOREIGN KEY(technician_id) REFERENCES technicians(id));
        CREATE TABLE IF NOT EXISTS repair_parts(id INTEGER PRIMARY KEY, repair_id INTEGER NOT NULL, part_id INTEGER NOT NULL, qty REAL NOT NULL, unit_price REAL NOT NULL, FOREIGN KEY(repair_id) REFERENCES repairs(id) ON DELETE CASCADE, FOREIGN KEY(part_id) REFERENCES parts(id));
        CREATE TABLE IF NOT EXISTS parts(id INTEGER PRIMARY KEY, sku TEXT UNIQUE, name TEXT NOT NULL, category TEXT, supplier TEXT, qty REAL DEFAULT 0, min_qty REAL DEFAULT 0, purchase_price REAL DEFAULT 0, sale_price REAL DEFAULT 0, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS stock_moves(id INTEGER PRIMARY KEY, part_id INTEGER NOT NULL, type TEXT NOT NULL, qty REAL NOT NULL, unit_price REAL DEFAULT 0, reference TEXT, created_at TEXT NOT NULL, FOREIGN KEY(part_id) REFERENCES parts(id));
        CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, repair_id INTEGER, customer_id INTEGER, amount REAL NOT NULL, method TEXT DEFAULT 'cash', note TEXT, created_at TEXT NOT NULL, FOREIGN KEY(repair_id) REFERENCES repairs(id), FOREIGN KEY(customer_id) REFERENCES customers(id));
        CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY, title TEXT NOT NULL, amount REAL NOT NULL, category TEXT, note TEXT, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS custom_fields(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
        CREATE TABLE IF NOT EXISTS repair_custom(id INTEGER PRIMARY KEY, repair_id INTEGER NOT NULL, field_id INTEGER NOT NULL, value TEXT, UNIQUE(repair_id,field_id), FOREIGN KEY(repair_id) REFERENCES repairs(id) ON DELETE CASCADE, FOREIGN KEY(field_id) REFERENCES custom_fields(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS repair_photos(id INTEGER PRIMARY KEY, repair_id INTEGER NOT NULL, path TEXT NOT NULL, caption TEXT, created_at TEXT NOT NULL, FOREIGN KEY(repair_id) REFERENCES repairs(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT, entity TEXT, entity_id INTEGER, details TEXT, created_at TEXT NOT NULL);
        '''
        self.conn.executescript(s)
        if not self.one('SELECT id FROM users LIMIT 1'):
            salt,h=hash_password('admin')
            self.execute('INSERT INTO users(username,email,salt,password_hash,role,created_at) VALUES(?,?,?,?,?,?)',('admin','',salt,h,'admin',now()))
        defaults={'shop_name':'ARAB SOFT - مركز صيانة','shop_phone':'','shop_address':'','currency':'ج.م','warranty_default':'30','receipt_footer':'نشكركم لثقتكم بنا'}
        for k,v in defaults.items(): self.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
    def close(self): self.conn.close()
    def backup(self, target):
        # SQLite's online backup API keeps WAL-mode databases consistent.
        target_conn = sqlite3.connect(target)
        try:
            self.conn.backup(target_conn)
            target_conn.commit()
        finally:
            target_conn.close()
