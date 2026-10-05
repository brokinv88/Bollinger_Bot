"""Subscriber gửi Telegram cho các sự kiện. Đổi kênh (Discord, webhook...): viết module tương tự."""
from . import events, settings, telegram

KIND_TITLE = {"buy": "🟢 MUA", "buy_more": "🟢 MUA THÊM", "sell_partial": "🟠 BÁN MỘT PHẦN", "sell_all": "🔴 BÁN HẾT"}


def short(a):
    return f"{a[:6]}…{a[-4:]}"


@events.on("signal")
def on_signal(conn, sig):
    if sig.kind not in settings.get(conn, "ALERT_KINDS"):
        return
    tag = "🎯 SNIPER" if sig.wallet_status == "watch_only" else "🧠 SMART MONEY"
    lines = [f"{KIND_TITLE[sig.kind]} {sig.symbol} ({sig.chain}) — {tag}",
             f"Ví: {sig.wallet}" + (f" — {sig.wallet_note}" if sig.wallet_note else "")]
    if sig.labels:
        lines.append("Nhãn: " + ", ".join(sig.labels))
    if sig.side == "sell":
        lines.append(f"Bán {sig.sell_fraction:.0%} vị thế")
    lines.append(f"Token: {sig.token}")
    if sig.price:
        lines.append(f"Giá ${sig.price:.8g} | Thanh khoản ${sig.liquidity or 0:,.0f}")
    if sig.pair and sig.pair.get("created_ts"):
        lines.append(f"Tuổi pool: {(sig.ts - sig.pair['created_ts']) / 3600:.1f}h")
    if sig.side == "buy":
        if sig.confluence >= 2:
            lines.append(f"🔥 HỢP LƯU: {sig.confluence} ví theo dõi cùng mua trong "
                         f"{settings.get(conn, 'CONFLUENCE_WINDOW_S') // 60} phút")
        if not sig.passed:
            lines.append("⛔ Không paper: " + "; ".join(sig.reasons))
        elif sig.wallet_status == "watch_only":
            lines.append("ℹ️ Sniper: chỉ alert, không paper")
    lines += [f"📝 {a}" for a in sig.actions]
    if sig.pair and sig.pair.get("url"):
        lines.append(sig.pair["url"])
    telegram.send("\n".join(lines))


@events.on("position_fill")
def on_fill(conn, fill):
    icon = "✅" if fill["fill_pnl"] > 0 else "❌"
    head = "Đóng" if fill["closed"] else "Chốt một phần"
    text = (f"{icon} {head} paper [{fill['book']}] {fill['symbol']} ({fill['chain']}) — {fill['reason']}\n"
            f"Bán ${fill['fill_usd']:.2f}, lãi/lỗ phần này ${fill['fill_pnl']:+.2f}")
    if fill["closed"]:
        text += f"\nTổng PnL lệnh ${fill['pnl_usd']:+.2f} ({fill['pnl_usd'] / fill['size_usd']:+.0%})"
    telegram.send(text)


@events.on("wallet_changed")
def on_wallet(conn, chain, address, status, reason):
    icon = {"active": "➕🧠", "watch_only": "➕🎯", "disabled": "➖"}.get(status, "•")
    telegram.send(f"{icon} Ví {address} ({chain}) -> {status}: {reason}")
