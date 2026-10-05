"""Bộ lọc tín hiệu MUA. Thêm bộ lọc mới: viết hàm (conn, sig) -> lý do chặn | None và gắn @signal_filter."""
from . import db, market, settings

FILTERS = []


def signal_filter(name):
    def deco(fn):
        FILTERS.append((name, fn))
        return fn
    return deco


@signal_filter("price")
def _price(conn, sig):
    if not sig.price:
        return "không có giá trên DexScreener"


@signal_filter("liquidity")
def _liquidity(conn, sig):
    minimum = settings.get(conn, "MIN_LIQUIDITY_USD")
    if sig.price and (sig.liquidity or 0) < minimum:
        return f"thanh khoản ${sig.liquidity or 0:,.0f} < ${minimum:,.0f}"


@signal_filter("blacklist")
def _blacklist(conn, sig):
    row = db.is_blacklisted(conn, sig.chain, sig.token)
    if row:
        return "token trong blacklist" + (f" ({row[0]})" if row[0] else "")


@signal_filter("wallet_labels")
def _labels(conn, sig):
    bad = set(sig.labels) & set(settings.get(conn, "BLOCK_LABELS"))
    if bad:
        return "ví bị gắn nhãn " + ", ".join(sorted(bad))


@signal_filter("security")
def _security(conn, sig):
    if not sig.price:
        return None
    sec = market.token_security(sig.chain, sig.token)
    if sec["honeypot"]:
        return "HONEYPOT"
    max_tax = settings.get(conn, "MAX_TAX")
    taxes = [f"{k} {sec[k]:.0%}" for k in ("buy_tax", "sell_tax") if sec[k] is not None and sec[k] > max_tax]
    return "; ".join(taxes) or None


def run(conn, sig):
    """Chạy toàn bộ bộ lọc, ghi sig.passed / sig.reasons."""
    sig.reasons = [r for _, fn in FILTERS if (r := fn(conn, sig))]
    sig.passed = not sig.reasons
    return sig.passed
