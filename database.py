import sqlite3

class PortfolioDB:
    def __init__(self, db_file):
        self.db_file = db_file
        self.init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_file)
        return conn

    def _table_columns(self, conn, table):
        cur = conn.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cur.fetchall()}

    def init_db(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT PRIMARY KEY,
            total_qty REAL,
            total_invested REAL,
            pyramid_level INTEGER,
            first_entry_date TEXT,
            last_entry_date TEXT,
            avg_entry_price REAL
        )
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            entry_date TEXT,
            exit_date TEXT,
            invested REAL,
            exit_price REAL,
            pnl_usd REAL,
            pnl_pct REAL,
            reason TEXT
        )
        ''')
        conn.commit()

        # --- Migration (an toàn cho DB cũ không làm hỏng dữ liệu) ---
        cols_pos = self._table_columns(conn, "positions")
        if "sl_price" not in cols_pos:
            cursor.execute("ALTER TABLE positions ADD COLUMN sl_price REAL")
        if "source" not in cols_pos:
            cursor.execute("ALTER TABLE positions ADD COLUMN source TEXT DEFAULT 'manual'")
            # Dữ liệu active cũ xem như thủ công

        cols_hist = self._table_columns(conn, "trade_history")
        if "source" not in cols_hist:
            cursor.execute("ALTER TABLE trade_history ADD COLUMN source TEXT DEFAULT 'manual'")

        conn.commit()
        conn.close()

    def get_open_positions(self):
        conn = self._get_conn()
        cursor = conn.cursor()
        cols = self._table_columns(conn, "positions")
        cursor.execute('SELECT symbol, total_qty, total_invested, pyramid_level, first_entry_date, last_entry_date, avg_entry_price FROM positions')
        rows = cursor.fetchall()
        conn.close()
        positions = {}
        for r in rows:
            positions[r[0]] = {
                'symbol': r[0],
                'total_qty': r[1],
                'total_invested': r[2],
                'pyramid_level': r[3],
                'first_entry_date': r[4],
                'last_entry_date': r[5],
                'avg_entry_price': r[6],
                'sl_price': None,
                'source': 'manual'
            }
        # Nạp thêm cột mới nếu có
        if "sl_price" in cols:
            conn = self._get_conn()
            cur = conn.cursor()
            cur.execute('SELECT symbol, sl_price, source FROM positions')
            for sym, sl, src in cur.fetchall():
                if sym in positions:
                    positions[sym]['sl_price'] = sl
                    positions[sym]['source'] = src or 'manual'
            conn.close()
        return positions

    def add_or_pyramid_position(self, symbol, qty, cash, price, today_str, source="manual", sl_price=None):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT total_qty, total_invested, pyramid_level, first_entry_date FROM positions WHERE symbol = ?', (symbol,))
        row = cursor.fetchone()

        if row is None:
            cursor.execute('''
            INSERT INTO positions (symbol, total_qty, total_invested, pyramid_level, first_entry_date, last_entry_date, avg_entry_price, sl_price, source)
            VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?)
            ''', (symbol, qty, cash, today_str, today_str, price, sl_price, source))
            level = 1
        else:
            new_qty = row[0] + qty
            new_invested = row[1] + cash
            new_level = row[2] + 1
            new_avg_price = new_invested / new_qty
            cursor.execute('''
            UPDATE positions
            SET total_qty = ?, total_invested = ?, pyramid_level = ?, last_entry_date = ?, avg_entry_price = ?, sl_price = coalesce(?, sl_price)
            WHERE symbol = ?
            ''', (new_qty, new_invested, new_level, today_str, new_avg_price, sl_price, symbol))
            level = new_level

        conn.commit()
        conn.close()
        return level

    def update_sl_price(self, symbol, sl_price):
        """Cập nhật mức cắt lỗ (SL) mới nhất cho vị thế đang mở. Không phải trailing —
        ghi đúng giá trị mới tính từ công thức mới nhất."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('UPDATE positions SET sl_price = ? WHERE symbol = ?', (sl_price, symbol))
        conn.commit()
        conn.close()

    def auto_entered_today(self, symbol, today_str):
        """Kiểm tra: hôm nay đã TỰ ĐỘNG mua (source='auto') coin này chưa.
        Bao phủ cả vị thế đang mở (positions) lẫn đã đóng (trade_history):
        căn cứ theo NGÀY VÀO lệnh để chống mua lại lần 1 trong ngày."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT COUNT(*) FROM positions WHERE symbol = ? AND source = 'auto' AND first_entry_date = ?",
                (symbol, today_str)
            )
            open_count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT COUNT(*) FROM trade_history WHERE symbol = ? AND source = 'auto' AND entry_date = ?",
                (symbol, today_str)
            )
            closed_count = cursor.fetchone()[0]
        except Exception:
            open_count = closed_count = 0
        conn.close()
        return open_count > 0 or closed_count > 0

    def close_position_db(self, symbol, exit_price, today_str, reason, source="auto"):
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT total_qty, total_invested, first_entry_date FROM positions WHERE symbol = ?', (symbol,))
        row = cursor.fetchone()

        if row:
            qty, invested, first_date = row
            gross = qty * exit_price
            commission = gross * 0.00075
            net = gross - commission
            pnl_usd = net - invested
            pnl_pct = (pnl_usd / invested) * 100.0

            cursor.execute('''
            INSERT INTO trade_history (symbol, entry_date, exit_date, invested, exit_price, pnl_usd, pnl_pct, reason, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, first_date, today_str, invested, exit_price, pnl_usd, pnl_pct, reason, source))

            cursor.execute('DELETE FROM positions WHERE symbol = ?', (symbol,))
            conn.commit()
            conn.close()
            return pnl_usd, pnl_pct, invested
        conn.close()
        return 0.0, 0.0, 0.0
