"""Event bus trong tiến trình. Tính năng mới = 1 module đăng ký handler, không sửa monitor.

Sự kiện:
  signal(conn, sig)                 — ví theo dõi mua/bán (sig: models.Signal)
  position_fill(conn, fill)         — lệnh paper mở / chốt một phần / đóng
  wallet_changed(conn, chain, address, status, reason)
"""
import traceback
from collections import defaultdict

_subs = defaultdict(list)


def on(event):
    def deco(fn):
        if fn not in _subs[event]:
            _subs[event].append(fn)
        return fn
    return deco


def emit(event, **data):
    for fn in list(_subs[event]):
        try:
            fn(**data)
        except Exception:
            print(f"[event {event}] lỗi ở {fn.__module__}.{fn.__name__}")
            traceback.print_exc()
