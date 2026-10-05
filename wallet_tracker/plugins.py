"""Danh sách module subscriber. Thứ tự quan trọng: paper chạy trước để alert hiển thị kết quả paper.
Thêm tính năng (vd webhook, Discord, giao dịch thật): viết module dùng @events.on(...) rồi thêm vào đây
hoặc biến môi trường WT_PLUGINS=pkg.module1,pkg.module2."""
import importlib
import os

PLUGINS = ["wallet_tracker.paper", "wallet_tracker.alerts"]
_loaded = False


def load():
    global _loaded
    if _loaded:
        return
    extra = [m.strip() for m in os.environ.get("WT_PLUGINS", "").split(",") if m.strip()]
    for name in PLUGINS + extra:
        importlib.import_module(name)
    _loaded = True
