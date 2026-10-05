"""SQLite storage cho Wallet Tracker."""
import sqlite3
import statistics
import time

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS wallets (
    chain TEXT, address TEXT,
    status TEXT,            -- active | watch_only | candidate | disabled
    source TEXT,            -- manual | discovery
    label TEXT DEFAULT '', note TEXT DEFAULT '',
    early_hits INTEGER DEFAULT 0,
    added_at INTEGER,
    PRIMARY KEY (chain, address)
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
CREATE TABLE IF NOT EXISTS tokens (
    chain TEXT, token TEXT, symbol TEXT,
    first_price REAL, first_ts INTEGER, max_price REAL,
    discovered INTEGER DEFAULT 0,
    PRIMARY KEY (chain, token)
);
CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book TEXT, chain TEXT, token TEXT, symbol TEXT, wallet TEXT,
    entry_price REAL, entry_ts INTEGER, size_usd REAL,
    status TEXT DEFAULT 'open',
    exit_price REAL, exit_ts INTEGER, reason TEXT, pnl_usd REAL
);
"""


def connect(path=None):
    conn = sqlite3.connect(path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
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


# --- cursors ---
def get_cursor(conn, key):
    row = conn.execute("SELECT value FROM cursors WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def set_cursor(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO cursors VALUES (?,?)", (key, str(value)))
    conn.commit()


# --- trades / tokens ---
def insert_trade(conn, chain, wallet, token, side, amount, tx, ts, price=None):
    cur = conn.execute("INSERT OR IGNORE INTO trades(chain,wallet,token,side,amount,tx,ts,price) VALUES (?,?,?,?,?,?,?,?)",
                       (chain, wallet, token, side, amount, tx, ts, price))
    conn.commit()
    return cur.rowcount > 0


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
