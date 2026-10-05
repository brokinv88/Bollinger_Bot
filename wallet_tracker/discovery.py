"""Tìm ví mới: quét người mua sớm của token thắng lớn, tự thêm vào danh sách khi đủ điều kiện.

Cơ chế thêm ví:
  1. Mỗi người mua sớm -> ví 'candidate' (chưa theo dõi), early_hits +1 mỗi token.
  2. early_hits >= PROMOTE_MIN_HITS -> tự bật theo dõi:
       trễ trung vị < SNIPER_DELAY_S -> 'watch_only' (sniper: chỉ alert, không paper)
       ngược lại                     -> 'active'     (smart money: alert + paper)
  3. Ví discovery có >= DEMOTE_MIN_TRADES lệnh paper đóng mà tổng lỗ -> 'disabled'.
"""
from . import config, db, market, paper
from .clients import make_client


def discover_token(conn, chain, token, window_min=None, client=None):
    cfg = config.CHAINS[chain]
    token = config.norm(chain, token)
    if cfg["kind"] != "evm":
        raise NotImplementedError("Discovery cho Solana chưa hỗ trợ ở Phase 1 — thêm ví Solana bằng tay.")
    pair = market.token_pairs(chain, [token]).get(token)
    if not pair or not pair["created_ts"]:
        raise RuntimeError(f"Không tìm thấy pool của {token} trên DexScreener ({chain})")
    client = client or make_client(chain)
    window_s = (window_min or config.DISCOVERY_WINDOW_MIN) * 60
    buyers = client.early_buyers(token, pair["pair"], pair["created_ts"], window_s, config.DISCOVERY_MAX_LOGS)

    new_wallets, promoted = 0, []
    for wallet, delay in buyers.items():
        if db.add_wallet(conn, chain, wallet, status="candidate", source="discovery",
                         note=f"vào sớm {pair['symbol']}"):
            new_wallets += 1
        db.record_early_buy(conn, chain, token, wallet, delay)
        row = db.get_wallet(conn, chain, wallet)
        if row["status"] == "candidate" and row["early_hits"] >= config.PROMOTE_MIN_HITS:
            med = db.median_delay(conn, chain, wallet)
            status = "watch_only" if med is not None and med < config.SNIPER_DELAY_S else "active"
            db.set_status(conn, chain, wallet, status)
            promoted.append((wallet, status, row["early_hits"], med))
    db.mark_discovered(conn, chain, token)
    return {"symbol": pair["symbol"], "buyers": len(buyers), "new": new_wallets, "promoted": promoted}


def format_discovery(chain, res):
    lines = [f"🔎 Discovery {res['symbol']} ({chain}): {res['buyers']} ví mua sớm, {res['new']} ví mới"]
    for w, status, hits, med in res["promoted"]:
        tag = "🎯 sniper (chỉ alert)" if status == "watch_only" else "🧠 smart money (alert + paper)"
        lines.append(f"➕ {w} — {tag}, vào sớm {hits} token, trễ trung vị {med:.0f}s")
    return "\n".join(lines)


def auto_discover(conn):
    """Token mà ví theo dõi đã mua và sau đó tăng >= DISCOVERY_PUMP_X -> quét người mua sớm."""
    msgs = []
    active = set(config.active_chains())
    for t in db.pumped_tokens(conn, config.DISCOVERY_PUMP_X):
        if t["chain"] not in active or config.CHAINS[t["chain"]]["kind"] != "evm":
            continue
        try:
            msgs.append(format_discovery(t["chain"], discover_token(conn, t["chain"], t["token"])))
        except Exception as e:
            print(f"[discovery] {t['chain']} {t['token']}: {e}")
    return msgs


def demote_losers(conn):
    msgs = []
    for r in paper.wallet_stats(conn, "fixed"):
        if r["n"] < config.DEMOTE_MIN_TRADES or r["pnl"] >= 0:
            continue
        w = db.get_wallet(conn, r["chain"], r["wallet"])
        if not w or w["status"] == "disabled":
            continue
        if w["source"] == "discovery":
            db.set_status(conn, r["chain"], r["wallet"], "disabled")
            msgs.append(f"➖ Tắt ví {r['wallet']} ({r['chain']}): {r['n']} lệnh, PnL ${r['pnl']:+.2f}")
        else:
            msgs.append(f"⚠️ Ví nhập tay {r['wallet']} ({r['chain']}) đang lỗ: {r['n']} lệnh, PnL ${r['pnl']:+.2f}")
    return msgs
