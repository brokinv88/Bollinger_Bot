import sqlite3

class PortfolioDB:
    def __init__(self, db_file):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
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
        conn.close()

    def get_open_positions(self):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('SELECT symbol, total_qty, total_invested, pyramid_level, first_entry_date, last_entry_date, avg_entry_price FROM positions')
        rows = cursor.fetchall()
        conn.close()
        positions = {}
        for r in rows:
            positions[r[0]] = {
                'total_qty': r[1],
                'total_invested': r[2],
                'pyramid_level': r[3],
                'first_entry_date': r[4],
                'last_entry_date': r[5],
                'avg_entry_price': r[6]
            }
        return positions

    def add_or_pyramid_position(self, symbol, qty, cash, price, today_str):
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('SELECT total_qty, total_invested, pyramid_level, first_entry_date FROM positions WHERE symbol = ?', (symbol,))
        row = cursor.fetchone()
        
        if row is None:
            cursor.execute('''
            INSERT INTO positions (symbol, total_qty, total_invested, pyramid_level, first_entry_date, last_entry_date, avg_entry_price)
            VALUES (?, ?, ?, 1, ?, ?, ?)
            ''', (symbol, qty, cash, today_str, today_str, price))
            level = 1
        else:
            new_qty = row[0] + qty
            new_invested = row[1] + cash
            new_level = row[2] + 1
            new_avg_price = new_invested / new_qty
            cursor.execute('''
            UPDATE positions 
            SET total_qty = ?, total_invested = ?, pyramid_level = ?, last_entry_date = ?, avg_entry_price = ?
            WHERE symbol = ?
            ''', (new_qty, new_invested, new_level, today_str, new_avg_price, symbol))
            level = new_level
            
        conn.commit()
        conn.close()
        return level

    def close_position_db(self, symbol, exit_price, today_str, reason):
        conn = sqlite3.connect(self.db_file)
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
            INSERT INTO trade_history (symbol, entry_date, exit_date, invested, exit_price, pnl_usd, pnl_pct, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, first_date, today_str, invested, exit_price, pnl_usd, pnl_pct, reason))
            
            cursor.execute('DELETE FROM positions WHERE symbol = ?', (symbol,))
            conn.commit()
            conn.close()
            return pnl_usd, pnl_pct, invested
        conn.close()
        return 0.0, 0.0, 0.0
