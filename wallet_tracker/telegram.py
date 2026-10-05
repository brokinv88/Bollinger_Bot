"""Telegram riêng cho Wallet Tracker: gửi alert + nhận lệnh /add /remove /list /stats từ đúng chat."""
import requests

from . import config, db, paper

HELP = ("Lệnh:\n/add <chain> <ví> [ghi chú]\n/remove <chain> <ví>\n/list\n/stats\n"
        f"chain: {', '.join(config.CHAINS)}")


def _api(method, **kw):
    return requests.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/{method}", json=kw, timeout=15)


def send(text):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("\n[TELEGRAM PREVIEW]\n" + text + "\n" + "-" * 50)
        return
    try:
        r = _api("sendMessage", chat_id=config.TELEGRAM_CHAT_ID, text=text, disable_web_page_preview=True)
        if not r.json().get("ok"):
            print(f"Telegram API Error: {r.text}")
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")


def handle_command(conn, text):
    parts = text.strip().split()
    if not parts:
        return HELP
    cmd = parts[0].split("@")[0].lower()
    if cmd == "/add" and len(parts) >= 3 and parts[1] in config.CHAINS:
        new = db.add_wallet(conn, parts[1], parts[2], note=" ".join(parts[3:]))
        return f"{'Đã thêm' if new else 'Đã bật lại'} ví {parts[2]} ({parts[1]})"
    if cmd == "/remove" and len(parts) >= 3 and parts[1] in config.CHAINS:
        ok = db.set_status(conn, parts[1], parts[2], "disabled")
        return "Đã tắt ví" if ok else "Không tìm thấy ví"
    if cmd == "/list":
        rows = db.list_wallets(conn, statuses=("active", "watch_only"))
        lines = [f"{r['chain']} {r['address']} [{r['status']}] hits={r['early_hits']} {r['note']}" for r in rows]
        return "\n".join(lines[:50]) or "Chưa có ví nào"
    if cmd == "/stats":
        return format_stats(conn)
    return HELP


def format_stats(conn):
    lines = ["📊 Paper trade"]
    for book, s in paper.book_stats(conn).items():
        lines.append(f"{book}: đóng {s['closed']} | win {s['winrate']:.0%} | PnL ${s['pnl']:+.2f} | "
                     f"mở {s['open']} | tiền mặt ${s['cash']:.0f}")
    return "\n".join(lines)


def poll_commands(conn):
    """Đọc tin nhắn mới (getUpdates, không webhook). Chỉ nhận lệnh từ WT_TELEGRAM_CHAT_ID."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    offset = int(db.get_cursor(conn, "tg_offset") or 0)
    try:
        updates = _api("getUpdates", offset=offset, timeout=0).json().get("result") or []
    except Exception as e:
        print(f"Lỗi đọc Telegram: {e}")
        return
    for u in updates:
        offset = u["update_id"] + 1
        msg = u.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) != str(config.TELEGRAM_CHAT_ID):
            continue
        if (msg.get("text") or "").startswith("/"):
            send(handle_command(conn, msg["text"]))
    db.set_cursor(conn, "tg_offset", offset)
