"""SQLite storage cho Wallet Tracker (WAL: monitor và app web dùng chung file)."""
import json
import sqlite3
import statistics
import time

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS wallets (
    chain TEXT, address TEXT,
    status TEXT,            -- active | watch_only | candidate | disabled
    source TEXT,            -- manual | discovery
    label TEXT DEFAULT '', note TEXT DEFAULT '',
    early_hits INTEGER DEFAULT 0,
    added_at INTEGER,
    PRIMARY KEY (chain, address)
);
CREATE TABLE IF NOT EXISTS wallet_metrics (
    chain TEXT, address TEXT, updated_at INTEGER, source TEXT,
    pnl_7d REAL, pnl_30d REAL, winrate_7d REAL, winrate_30d REAL,
    trades_7d INTEGER, trades_30d INTEGER, tokens_7d INTEGER, tokens_30d INTEGER,
    volume_30d REAL, avg_hold_s REAL, score REAL,
    PRIMARY KEY (chain, address)
);
CREATE TABLE IF NOT EXISTS wallet_labels (
    chain TEXT, address TEXT, label TEXT, detail TEXT DEFAULT '', updated_at INTEGER,
    PRIMARY KEY (chain, address, label)
);
CREATE TABLE IF NOT EXISTS early_buys (
    chain TEXT, token TEXT, wallet TEXT, delay_s REAL,
    PRIMARY KEY (chain, token, wallet)
);
CREATE TABLE IF NOT EXISTS cursors (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain TEXT, wallet TEXT, token TEXT, side TEXT, amount REAL, tx TEXT, ts INTEGER,
    price REAL,
    UNIQUE (chain, tx, wallet, token, side)
);
CREATE TABLE IF NOT EXISTS holdings (
    chain TEXT, wallet TEXT, token TEXT, qty REAL,
    PRIMARY KEY (chain, wallet, token)
);
CREATE TABLE IF NOT EXISTS tokens (
    chain TEXT, token TEXT, symbol TEXT,
    first_price REAL, first_ts INTEGER, max_price REAL,
    discovered INTEGER DEFAULT 0,
    PRIMARY KEY (chain, token)
);
CREATE TABLE IF NOT EXISTS blacklist (
    chain TEXT, token TEXT, reason TEXT DEFAULT '', added_at INTEGER,
    PRIMARY KEY (chain, token)
);
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER, chain TEXT, wallet TEXT, token TEXT, symbol TEXT, kind TEXT,
    price REAL, liquidity REAL, confluence INTEGER, sell_fraction REAL,
    passed INTEGER, reasons TEXT, actions TEXT, tx TEXT
);
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book TEXT, chain TEXT, token TEXT, symbol TEXT, wallet TEXT,
    entry_price REAL, entry_ts INTEGER, size_usd REAL,
    status TEXT DEFAULT 'open',
    exit_price REAL, exit_ts INTEGER, reason TEXT, pnl_usd REAL
);
CREATE TABLE IF NOT EXISTS fills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER, ts INTEGER, side TEXT, price REAL, qty REAL, usd REAL, reason TEXT
);
CREATE TABLE IF NOT EXISTS wallet_positions (
    chain TEXT, wallet TEXT, token TEXT, symbol TEXT, name TEXT,
    qty REAL, value_usd REAL, price REAL, is_quote INTEGER DEFAULT 0, updated_at INTEGER,
    PRIMARY KEY (chain, wallet, token)
);
CREATE TABLE IF NOT EXISTS equity_snapshots (ts INTEGER, book TEXT, equity REAL, cash REAL);
CREATE INDEX IF NOT EXISTS idx_trades_token ON trades(chain, token, ts);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(ts);
"""

# Cột thêm sau (migrate DB cũ)
EXTRA_COLUMNS = {
    "positions": {"qty": "REAL", "remaining_qty": "REAL", "realized_usd": "REAL DEFAULT 0",
                  "peak_price": "REAL", "last_price": "REAL", "tp_level": "INTEGER DEFAULT 0"},
}


def connect(path=None):
    conn = sqlite3.connect(path or config.DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    for table, cols in EXTRA_COLUMNS.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, typ in cols.items():
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
    conn.commit()
    return conn


# --- wallets ---
def add_wallet(conn, chain, address, status="active", source="manual", label="", note=""):
    """Thêm ví. Ví đã có: nhập tay sẽ ghi đè status (bật lại ví bị tắt). Trả True nếu là ví mới."""
    address = config.norm(chain, address)
    row = get_wallet(conn, chain, address)
    if row is None:
        conn.execute("INSERT INTO wallets(chain,address,status,source,label,note,added_at) VALUES (?,?,?,?,?,?,?)",
                     (chain, address, status, source, label, note, int(time.time())))
        conn.commit()
        return True
    if source == "manual":
        conn.execute("UPDATE wallets SET status=?, source='manual', label=COALESCE(NULLIF(?,''),label),"
                     " note=COALESCE(NULLIF(?,''),note) WHERE chain=? AND address=?",
                     (status, label, note, chain, address))
        conn.commit()
    return False


def get_wallet(conn, chain, address):
    return conn.execute("SELECT * FROM wallets WHERE chain=? AND address=?",
                        (chain, config.norm(chain, address))).fetchone()


def set_status(conn, chain, address, status):
    cur = conn.execute("UPDATE wallets SET status=? WHERE chain=? AND address=?",
                       (status, chain, config.norm(chain, address)))
    conn.commit()
    return cur.rowcount > 0


def set_note(conn, chain, address, note):
    conn.execute("UPDATE wallets SET note=? WHERE chain=? AND address=?", (note, chain, config.norm(chain, address)))
    conn.commit()


def list_wallets(conn, chain=None, statuses=None):
    sql, args = "SELECT * FROM wallets WHERE 1=1", []
    if chain:
        sql += " AND chain=?"
        args.append(chain)
    if statuses:
        sql += f" AND status IN ({','.join('?' * len(statuses))})"
        args += list(statuses)
    return conn.execute(sql + " ORDER BY chain, early_hits DESC", args).fetchall()


def record_early_buy(conn, chain, token, wallet, delay_s):
    """Ghi 1 lần vào sớm (mỗi token tính 1 lần). Trả True nếu mới."""
    cur = conn.execute("INSERT OR IGNORE INTO early_buys VALUES (?,?,?,?)", (chain, token, wallet, delay_s))
    if cur.rowcount:
        conn.execute("UPDATE wallets SET early_hits=early_hits+1 WHERE chain=? AND address=?", (chain, wallet))
    conn.commit()
    return cur.rowcount > 0


def median_delay(conn, chain, wallet):
    rows = conn.execute("SELECT delay_s FROM early_buys WHERE chain=? AND wallet=?", (chain, wallet)).fetchall()
    return statistics.median(r[0] for r in rows) if rows else None


# --- metrics / labels ---
def save_metrics(conn, chain, address, m, source):
    cols = ["pnl_7d", "pnl_30d", "winrate_7d", "winrate_30d", "trades_7d", "trades_30d", "tokens_7d",
            "tokens_30d", "volume_30d", "avg_hold_s", "score"]
    conn.execute(f"INSERT OR REPLACE INTO wallet_metrics(chain,address,updated_at,source,{','.join(cols)})"
                 f" VALUES (?,?,?,?,{','.join('?' * len(cols))})",
                 [chain, address, int(time.time()), source] + [m.get(c) for c in cols])
    conn.commit()


def get_metrics(conn, chain, address):
    return conn.execute("SELECT * FROM wallet_metrics WHERE chain=? AND address=?", (chain, address)).fetchone()


def set_label(conn, chain, address, label, detail=""):
    conn.execute("INSERT OR REPLACE INTO wallet_labels VALUES (?,?,?,?,?)",
                 (chain, address, label, detail, int(time.time())))
    conn.commit()


def clear_labels(conn, chain, address, labels):
    conn.executemany("DELETE FROM wallet_labels WHERE chain=? AND address=? AND label=?",
                     [(chain, address, l) for l in labels])
    conn.commit()


def get_labels(conn, chain, address):
    return [r[0] for r in conn.execute("SELECT label FROM wallet_labels WHERE chain=? AND address=?",
                                       (chain, address))]


# --- cursors ---
def get_cursor(conn, key):
    row = conn.execute("SELECT value FROM cursors WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def set_cursor(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO cursors VALUES (?,?)", (key, str(value)))
    conn.commit()


# --- trades / holdings / tokens ---
def insert_trade(conn, chain, wallet, token, side, amount, tx, ts, price=None):
    cur = conn.execute("INSERT OR IGNORE INTO trades(chain,wallet,token,side,amount,tx,ts,price) VALUES (?,?,?,?,?,?,?,?)",
                       (chain, wallet, token, side, amount, tx, ts, price))
    conn.commit()
    return cur.rowcount > 0


def update_holding(conn, chain, wallet, token, delta):
    """Cộng dồn số dư token ví (theo các swap quan sát được). Trả số dư TRƯỚC khi cập nhật."""
    row = conn.execute("SELECT qty FROM holdings WHERE chain=? AND wallet=? AND token=?",
                       (chain, wallet, token)).fetchone()
    before = row[0] if row else 0.0
    conn.execute("INSERT OR REPLACE INTO holdings VALUES (?,?,?,?)", (chain, wallet, token, max(0.0, before + delta)))
    conn.commit()
    return before


def distinct_buyers(conn, chain, token, since_ts):
    return [r[0] for r in conn.execute(
        "SELECT DISTINCT wallet FROM trades WHERE chain=? AND token=? AND side='buy' AND ts>=?",
        (chain, token, since_ts))]


def upsert_token(conn, chain, token, symbol, price, ts):
    conn.execute("INSERT OR IGNORE INTO tokens(chain,token,symbol,first_price,first_ts,max_price) VALUES (?,?,?,?,?,?)",
                 (chain, token, symbol, price, ts, price))
    update_token_price(conn, chain, token, price)


def update_token_price(conn, chain, token, price):
    if price:
        conn.execute("UPDATE tokens SET max_price=MAX(COALESCE(max_price,0),?) WHERE chain=? AND token=?",
                     (price, chain, token))
        conn.commit()


def pumped_tokens(conn, x):
    return conn.execute("SELECT * FROM tokens WHERE discovered=0 AND first_price>0 AND max_price>=first_price*?",
                        (x,)).fetchall()


def mark_discovered(conn, chain, token):
    conn.execute("INSERT OR IGNORE INTO tokens(chain,token) VALUES (?,?)", (chain, token))
    conn.execute("UPDATE tokens SET discovered=1 WHERE chain=? AND token=?", (chain, token))
    conn.commit()


# --- blacklist ---
def blacklist_add(conn, chain, token, reason=""):
    token = token if chain == "*" else config.norm(chain, token)
    conn.execute("INSERT OR REPLACE INTO blacklist VALUES (?,?,?,?)", (chain, token, reason, int(time.time())))
    conn.commit()


def blacklist_remove(conn, chain, token):
    conn.execute("DELETE FROM blacklist WHERE chain=? AND token=?", (chain, token))
    conn.commit()


def is_blacklisted(conn, chain, token):
    return conn.execute("SELECT reason FROM blacklist WHERE (chain=? OR chain='*') AND token=?",
                        (chain, token)).fetchone()


# --- signals ---
def save_signal(conn, sig):
    cur = conn.execute(
        "INSERT INTO signals(ts,chain,wallet,token,symbol,kind,price,liquidity,confluence,sell_fraction,passed,"
        "reasons,actions,tx) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (sig.ts, sig.chain, sig.wallet, sig.token, sig.symbol, sig.kind, sig.price, sig.liquidity, sig.confluence,
         sig.sell_fraction, int(sig.passed), json.dumps(sig.reasons, ensure_ascii=False), "[]", sig.tx))
    conn.commit()
    return cur.lastrowid


def update_signal_actions(conn, sig):
    conn.execute("UPDATE signals SET actions=? WHERE id=?", (json.dumps(sig.actions, ensure_ascii=False), sig.id))
    conn.commit()


# --- danh mục token ví đang nắm ---
def save_positions(conn, chain, wallet, rows):
    """Thay toàn bộ danh mục của ví trên chain bằng rows: [{token, symbol, name, qty, value_usd, price, is_quote}]."""
    now = int(time.time())
    conn.execute("DELETE FROM wallet_positions WHERE chain=? AND wallet=?", (chain, wallet))
    conn.executemany("INSERT OR REPLACE INTO wallet_positions VALUES (?,?,?,?,?,?,?,?,?,?)",
                     [(chain, wallet, r["token"], r.get("symbol"), r.get("name"), r.get("qty"), r.get("value_usd"),
                       r.get("price"), int(bool(r.get("is_quote"))), now) for r in rows])
    conn.commit()


def get_positions(conn, chain, wallet):
    return conn.execute("SELECT * FROM wallet_positions WHERE chain=? AND wallet=? ORDER BY value_usd DESC",
                        (chain, wallet)).fetchall()
