"""Tham số runtime: mặc định trong config.DEFAULTS, ghi đè lưu ở bảng settings (sửa từ app/CLI)."""
import copy
import json

from . import config


def get(conn, key):
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else copy.deepcopy(config.DEFAULTS[key])


def set(conn, key, value):
    if key not in config.DEFAULTS:
        raise KeyError(f"Không có tham số {key}")
    default = config.DEFAULTS[key]
    if isinstance(default, float) and isinstance(value, int):
        value = float(value)
    if type(value) is not type(default):
        raise TypeError(f"{key} phải là {type(default).__name__}")
    conn.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value)))
    conn.commit()


def reset(conn, key):
    conn.execute("DELETE FROM settings WHERE key=?", (key,))
    conn.commit()


def all(conn):
    return {k: get(conn, k) for k in config.DEFAULTS}
