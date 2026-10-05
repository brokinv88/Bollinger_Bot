"""Tìm ví mới: quét người mua sớm của token thắng lớn, gắn nhãn sniper/insider/bundler, tự thêm khi đủ chuẩn.

Cơ chế thêm ví:
  1. Mỗi người mua sớm -> ví 'candidate', early_hits +1 mỗi token.
  2. Nguồn nạp tiền (nếu có provider): trùng creator token -> 'insider'; >= BUNDLER_MIN_SHARED ví cùng nguồn -> 'bundler'.
  3. evaluate(): early_hits >= PROMOTE_MIN_HITS hoặc chỉ số đạt chuẩn (scoring) và không có nhãn chặn ->
       trễ trung vị < SNIPER_DELAY_S -> 'watch_only' (sniper: chỉ alert), ngược lại 'active'.
  4. Ví discovery có >= DEMOTE_MIN_TRADES lệnh paper đóng mà tổng lỗ -> 'disabled'.
"""
from collections import defaultdict

from . import config, db, events, market, paper, scoring, settings
from .chains import make_client
from .providers import get_provider


def evaluate(conn, chain, wallet):
    """Xét tự thêm 1 ứng viên. Trả status mới hoặc None."""
    row = db.get_wallet(conn, chain, wallet)
    if not row or row["status"] != "candidate":
        return None
    labels = set(db.get_labels(conn, chain, wallet))
    if labels & set(settings.get(conn, "BLOCK_LABELS")):
        return None
    if row["early_hits"] < settings.get(conn, "PROMOTE_MIN_HITS") and not scoring.wallet_passes(conn, chain, wallet):
        return None
    med = db.median_delay(conn, chain, wallet)
    sniper = med is not None and med < settings.get(conn, "SNIPER_DELAY_S")
    status = "watch_only" if sniper else "active"
    if sniper:
        db.set_label(conn, chain, wallet, "sniper", f"trễ trung vị {med:.0f}s")
    db.set_status(conn, chain, wallet, status)
    events.emit("wallet_changed", conn=conn, chain=chain, address=wallet, status=status,
                reason=f"vào sớm {row['early_hits']} token" + (f", trễ {med:.0f}s" if med is not None else ""))
    return status


def tag_funding(conn, chain, token, buyers, provider):
    """Gắn nhãn insider/bundler theo nguồn nạp tiền của người mua sớm."""
    if provider.name == "local":
        return
    creator = market.token_security(chain, token).get("creator")
    by_source = defaultdict(list)
    limit = settings.get(conn, "FUNDING_CHECK_MAX")
    for wallet in sorted(buyers, key=buyers.get)[:limit]:
        try:
            sources = provider.funding_sources(chain, wallet)[:3]
        except Exception as e:
            print(f"[funding] {wallet}: {e}")
            continue
        if creator and creator in sources:
            db.set_label(conn, chain, wallet, "insider", f"được creator {creator[:10]}… nạp tiền")
        for s in sources:
            by_source[s].append(wallet)
    for source, wallets in by_source.items():
        if len(wallets) >= settings.get(conn, "BUNDLER_MIN_SHARED"):
            for w in wallets:
                db.set_label(conn, chain, w, "bundler", f"chung nguồn {source[:10]}… với {len(wallets) - 1} ví")


def discover_token(conn, chain, token, window_min=None, client=None, provider=None):
    token = config.norm(chain, token)
    pair = market.token_pairs(chain, [token]).get(token)
    if not pair or not pair["created_ts"]:
        raise RuntimeError(f"Không tìm thấy pool của {token} trên DexScreener ({chain})")
    client = client or make_client(chain)
    provider = provider or get_provider(conn)
    window_s = (window_min or settings.get(conn, "DISCOVERY_WINDOW_MIN")) * 60
    buyers = client.early_buyers(token, pair["pair"], pair["created_ts"], window_s,
                                 settings.get(conn, "DISCOVERY_MAX_LOGS"))
    new_wallets = 0
    for wallet, delay in buyers.items():
        if db.add_wallet(conn, chain, wallet, status="candidate", source="discovery",
                         note=f"vào sớm {pair['symbol']}"):
            new_wallets += 1
        db.record_early_buy(conn, chain, token, wallet, delay)
    tag_funding(conn, chain, token, buyers, provider)
    promoted = [(w, s) for w in buyers if (s := evaluate(conn, chain, w))]
    db.mark_discovered(conn, chain, token)
    return {"symbol": pair["symbol"], "buyers": len(buyers), "new": new_wallets, "promoted": promoted}


def format_discovery(chain, res):
    lines = [f"🔎 Discovery {res['symbol']} ({chain}): {res['buyers']} ví mua sớm, {res['new']} ví mới, "
             f"{len(res['promoted'])} ví được thêm theo dõi"]
    return "\n".join(lines)


def auto_discover(conn):
    """Token mà ví theo dõi đã mua và sau đó tăng >= DISCOVERY_PUMP_X -> quét người mua sớm."""
    msgs = []
    active = set(config.active_chains())
    for t in db.pumped_tokens(conn, settings.get(conn, "DISCOVERY_PUMP_X")):
        if t["chain"] not in active:
            continue
        try:
            msgs.append(format_discovery(t["chain"], discover_token(conn, t["chain"], t["token"])))
        except NotImplementedError:
            db.mark_discovered(conn, t["chain"], t["token"])
        except Exception as e:
            print(f"[discovery] {t['chain']} {t['token']}: {e}")
    return msgs


def promote_scored(conn):
    """Sau khi chấm điểm: ứng viên đạt chuẩn -> tự thêm theo dõi."""
    rows = db.list_wallets(conn, statuses=("candidate",))
    return [(r["chain"], r["address"], s) for r in rows if (s := evaluate(conn, r["chain"], r["address"]))]


def demote_losers(conn):
    msgs = []
    for r in paper.wallet_stats(conn, "fixed"):
        if r["n"] < settings.get(conn, "DEMOTE_MIN_TRADES") or r["pnl"] >= 0:
            continue
        w = db.get_wallet(conn, r["chain"], r["wallet"])
        if not w or w["status"] == "disabled":
            continue
        if w["source"] == "discovery":
            db.set_status(conn, r["chain"], r["wallet"], "disabled")
            events.emit("wallet_changed", conn=conn, chain=r["chain"], address=r["wallet"], status="disabled",
                        reason=f"{r['n']} lệnh paper, PnL ${r['pnl']:+.2f}")
        else:
            msgs.append(f"⚠️ Ví nhập tay {r['wallet']} ({r['chain']}) đang lỗ: {r['n']} lệnh, PnL ${r['pnl']:+.2f}")
    return msgs
