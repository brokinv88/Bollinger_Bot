"""Luật thoát lệnh paper. Mỗi luật: fn(pos, price, now, params) -> (tỷ_lệ_bán_của_phần_còn_lại, lý_do, cập_nhật) | None.
Book cấu hình danh sách luật (settings BOOKS). Thêm luật mới: viết hàm và gắn @rule("tên")."""
RULES = {}


def rule(name):
    def deco(fn):
        RULES[name] = fn
        return fn
    return deco


def _ret(pos, price):
    return price / pos["entry_price"] - 1


@rule("stop_loss")
def stop_loss(pos, price, now, p):
    if _ret(pos, price) <= p["pct"]:
        return 1.0, f"SL {p['pct']:.0%}", {}


@rule("take_profit_ladder")
def take_profit_ladder(pos, price, now, p):
    """levels: [[lãi, tỷ lệ của khối lượng BAN ĐẦU], ...] — vd [[1.0, 0.5]] = +100% bán 50%."""
    i = pos["tp_level"] or 0
    if i >= len(p["levels"]):
        return None
    gain, frac = p["levels"][i]
    if _ret(pos, price) >= gain:
        sell = min(1.0, pos["qty"] * frac / pos["remaining_qty"]) if pos["remaining_qty"] else 1.0
        return sell, f"TP{i + 1} +{gain:.0%}", {"tp_level": i + 1}


@rule("take_profit")
def take_profit(pos, price, now, p):
    if _ret(pos, price) >= p["pct"]:
        return 1.0, f"TP +{p['pct']:.0%}", {}


@rule("trailing_stop")
def trailing_stop(pos, price, now, p):
    peak = max(pos["peak_price"] or price, price)
    if peak / pos["entry_price"] - 1 >= p.get("activate", 0) and price <= peak * (1 - p["pct"]):
        return 1.0, f"trailing -{p['pct']:.0%} từ đỉnh", {}


@rule("time_stop")
def time_stop(pos, price, now, p):
    if now - pos["entry_ts"] >= p["hours"] * 3600:
        return 1.0, "hết thời gian", {}


def evaluate(pos, price, now, rules):
    for r in rules:
        fn = RULES.get(r["rule"])
        res = fn(pos, price, now, r) if fn else None
        if res:
            return res
    return None
