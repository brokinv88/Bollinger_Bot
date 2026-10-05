"""Chấm điểm + gắn nhãn ví từ lịch sử giao dịch (kiểu GMGN: PnL/winrate 7D/30D, thời gian giữ...).

Thêm nhãn mới: viết hàm (metrics, trades) -> (label, detail) | None và gắn @labeler.
"""
import time
from collections import defaultdict

from . import db, settings
from .providers import get_provider

DAY = 86400
LABELERS = []
METRIC_LABELS = set()      # nhãn do scoring quản lý (xóa khi không còn đúng)


def labeler(name):
    def deco(fn):
        LABELERS.append(fn)
        METRIC_LABELS.add(name)
        return fn
    return deco


def compute_metrics(trades, now=None):
    """trades: [{ts, token, side, qty, usd}] tăng dần theo ts. Giá vốn bình quân; lệnh bán không có giá vốn bỏ qua."""
    now = now or time.time()
    pos = defaultdict(lambda: {"qty": 0.0, "cost": 0.0, "first_buy": None})
    sells = []                 # (ts, token, realized, hold_s)
    per_token_trades = defaultdict(list)
    for t in trades:
        p = pos[t["token"]]
        per_token_trades[t["token"]].append(t)
        if t["side"] == "buy":
            p["qty"] += t["qty"]
            p["cost"] += t["usd"]
            p["first_buy"] = p["first_buy"] or t["ts"]
        elif p["qty"] > 0:
            q = min(t["qty"], p["qty"])
            cost = p["cost"] * q / p["qty"]
            realized = t["usd"] * q / t["qty"] - cost
            p["qty"] -= q
            p["cost"] -= cost
            sells.append((t["ts"], t["token"], realized, t["ts"] - p["first_buy"]))
            if p["qty"] <= 1e-12:
                p["first_buy"] = None

    m = {}
    for d in (7, 30):
        since = now - d * DAY
        win = [s for s in sells if s[0] >= since]
        by_token = defaultdict(float)
        for _, tok, r, _ in win:
            by_token[tok] += r
        m[f"pnl_{d}d"] = sum(by_token.values())
        m[f"winrate_{d}d"] = sum(v > 0 for v in by_token.values()) / len(by_token) if by_token else 0.0
        m[f"tokens_{d}d"] = len(by_token)
        m[f"trades_{d}d"] = sum(1 for t in trades if t["ts"] >= since)
    m["volume_30d"] = sum(t["usd"] for t in trades if t["ts"] >= now - 30 * DAY)
    holds = [s[3] for s in sells if s[0] >= now - 30 * DAY]
    m["avg_hold_s"] = sum(holds) / len(holds) if holds else None
    m["score"] = (m["winrate_30d"] * 50 + max(-25, min(25, m["pnl_30d"] / 1000))
                  + min(m["tokens_30d"], 25)) if m["tokens_30d"] else 0.0
    m["_per_token_trades"] = per_token_trades
    return m


@labeler("bot_flipper")
def _flipper(m, trades):
    holds = []
    for tok_trades in m["_per_token_trades"].values():
        buys = [t["ts"] for t in tok_trades if t["side"] == "buy"]
        sells = [t["ts"] for t in tok_trades if t["side"] == "sell"]
        if buys and sells:
            holds.append(min(sells) - min(buys))
    fast = sum(h < 60 for h in holds)
    if len(holds) >= 5 and fast / len(holds) >= 0.5:
        return "bot_flipper", f"{fast}/{len(holds)} token bán trong < 60s"


@labeler("wash_trader")
def _wash(m, trades):
    """Nhiều vòng mua-bán cùng token trong 1h mà gần như hòa vốn -> tạo volume giả."""
    n = 0
    for tok_trades in m["_per_token_trades"].values():
        for i, t in enumerate(tok_trades):
            window = [x for x in tok_trades[i:] if x["ts"] - t["ts"] <= 3600]
            if len(window) >= 10:
                buy = sum(x["usd"] for x in window if x["side"] == "buy")
                sell = sum(x["usd"] for x in window if x["side"] == "sell")
                if buy and abs(sell - buy) / buy < 0.02:
                    n += 1
                break
    if n >= 2:
        return "wash_trader", f"{n} token có >= 10 lệnh/giờ hòa vốn"


@labeler("high_winrate")
def _high(m, trades):
    if m["tokens_30d"] >= 10 and m["winrate_30d"] >= 0.6 and m["pnl_30d"] > 0:
        return "high_winrate", f"win {m['winrate_30d']:.0%} / {m['tokens_30d']} token 30D"


@labeler("losing")
def _losing(m, trades):
    if m["tokens_30d"] >= 5 and m["pnl_30d"] < 0:
        return "losing", f"PnL 30D ${m['pnl_30d']:,.0f}"


def score_wallet(conn, chain, wallet, provider=None, now=None):
    provider = provider or get_provider(conn)
    trades = provider.trades(chain, wallet, 60)       # 60 ngày để có giá vốn cho cửa sổ 30D
    m = compute_metrics(trades, now)
    db.save_metrics(conn, chain, wallet, m, provider.name)
    db.clear_labels(conn, chain, wallet, METRIC_LABELS)
    for fn in LABELERS:
        res = fn(m, trades)
        if res:
            db.set_label(conn, chain, wallet, *res)
    return m


def score_due(conn, provider=None):
    """Chấm các ví đang theo dõi/ứng viên có dữ liệu cũ hơn SCORE_STALE_H, tối đa SCORE_MAX_PER_RUN ví."""
    provider = provider or get_provider(conn)
    stale = time.time() - settings.get(conn, "SCORE_STALE_H") * 3600
    rows = conn.execute(
        "SELECT w.chain, w.address FROM wallets w LEFT JOIN wallet_metrics m"
        " ON m.chain=w.chain AND m.address=w.address"
        " WHERE w.status!='disabled' AND (m.updated_at IS NULL OR m.updated_at<?)"
        " ORDER BY (w.status='candidate'), w.early_hits DESC LIMIT ?",
        (stale, settings.get(conn, "SCORE_MAX_PER_RUN"))).fetchall()
    done = []
    for r in rows:
        try:
            score_wallet(conn, r["chain"], r["address"], provider)
            done.append((r["chain"], r["address"]))
        except Exception as e:
            print(f"[score] {r['chain']} {r['address']}: {e}")
    return done


def wallet_passes(conn, chain, wallet):
    """Đủ chuẩn smart money theo chỉ số (dùng để tự thêm ứng viên)."""
    m = db.get_metrics(conn, chain, wallet)
    if not m:
        return False
    return (m["winrate_30d"] >= settings.get(conn, "PROMOTE_MIN_WINRATE")
            and m["pnl_30d"] >= settings.get(conn, "PROMOTE_MIN_PNL_30D")
            and m["tokens_30d"] >= settings.get(conn, "PROMOTE_MIN_TOKENS"))
