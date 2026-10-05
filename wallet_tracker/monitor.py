"""Vòng lặp theo dõi: adapter trả swap -> dựng Signal -> lọc -> lưu -> phát sự kiện 'signal'.
Paper, alert... là subscriber (xem plugins.py), monitor không cần biết."""
import time
import traceback

from . import config, db, discovery, events, filters, market, paper, plugins, scoring, settings, telegram
from .chains import make_client
from .models import Signal

WATCHED = ("active", "watch_only")
DAILY_EVERY_S = 6 * 3600
SNAPSHOT_EVERY_S = 3600


def run_daily(conn):
    """Chấm điểm ví -> tự thêm ứng viên đạt chuẩn -> auto-discovery -> tắt ví lỗ -> báo cáo."""
    scoring.score_due(conn)
    discovery.promote_scored(conn)
    msgs = discovery.auto_discover(conn) + discovery.demote_losers(conn) + [telegram.format_stats(conn)]
    telegram.send("\n\n".join(msgs))


def build_signal(conn, chain, s, now):
    """Swap thô -> Signal (loại lệnh, tỷ lệ bán, giá, hợp lưu, nhãn ví, kết quả lọc)."""
    delta = s["amount"] if s["side"] == "buy" else -s["amount"]
    before = db.update_holding(conn, chain, s["wallet"], s["token"], delta)
    if s["side"] == "buy":
        kind, fraction = ("buy_more" if before > 0 else "buy"), 0.0
    else:
        fraction = min(1.0, s["amount"] / before) if before > 0 else 1.0
        kind = "sell_all" if fraction >= 0.95 else "sell_partial"
    pair = market.token_pairs(chain, [s["token"]]).get(s["token"])
    w = db.get_wallet(conn, chain, s["wallet"])
    sig = Signal(chain=chain, wallet=s["wallet"], token=s["token"], side=s["side"], kind=kind, amount=s["amount"],
                 tx=s["tx"], ts=int(now), pair=pair, sell_fraction=fraction,
                 symbol=pair["symbol"] if pair else "?", price=pair["price"] if pair else None,
                 liquidity=pair["liquidity"] if pair else None,
                 wallet_status=w["status"] if w else "", wallet_note=w["note"] if w else "",
                 labels=db.get_labels(conn, chain, s["wallet"]))
    if s["side"] == "buy":
        if pair:
            db.upsert_token(conn, chain, s["token"], sig.symbol, sig.price, int(now))
        since = int(now) - settings.get(conn, "CONFLUENCE_WINDOW_S")
        sig.confluence = len(db.distinct_buyers(conn, chain, s["token"], since))
        filters.run(conn, sig)
    else:
        sig.passed = True
    return sig


class Monitor:
    def __init__(self, conn, clients=None):
        plugins.load()
        self.conn = conn
        self.clients = clients if clients is not None else {c: make_client(c) for c in config.active_chains()}

    def poll_chain(self, chain):
        wallets = [w["address"] for w in db.list_wallets(self.conn, chain, WATCHED)]
        for s in self.clients[chain].poll(self.conn, wallets):
            self.handle_swap(chain, s)

    def handle_swap(self, chain, s, now=None):
        now = now or time.time()
        if not db.insert_trade(self.conn, chain, s["wallet"], s["token"], s["side"], s["amount"], s["tx"], int(now)):
            return None
        sig = build_signal(self.conn, chain, s, now)
        if sig.price:
            self.conn.execute("UPDATE trades SET price=? WHERE chain=? AND tx=? AND wallet=? AND token=? AND side=?",
                              (sig.price, chain, s["tx"], s["wallet"], s["token"], s["side"]))
        sig.id = db.save_signal(self.conn, sig)
        events.emit("signal", conn=self.conn, sig=sig)
        db.update_signal_actions(self.conn, sig)
        return sig

    def update_positions(self, now=None):
        now = now or time.time()
        for chain in {p["chain"] for p in paper.open_positions(self.conn)}:
            tokens = [p["token"] for p in paper.open_positions(self.conn, chain=chain)]
            prices = {t: v["price"] for t, v in market.token_pairs(chain, tokens).items()}
            for t, p in prices.items():
                db.update_token_price(self.conn, chain, t, p)
            paper.update_prices(self.conn, chain, prices, now)

    def _every(self, key, interval, fn):
        last = float(db.get_cursor(self.conn, key) or 0)
        if time.time() - last >= interval:
            db.set_cursor(self.conn, key, time.time())
            try:
                fn(self.conn)
            except Exception as e:
                print(f"[{key}] lỗi: {e}")
                traceback.print_exc()

    def run_once(self):
        for chain in self.clients:
            try:
                self.poll_chain(chain)
            except Exception as e:
                print(f"[{chain}] lỗi: {e}")
                traceback.print_exc()
        try:
            self.update_positions()
        except Exception as e:
            print(f"[positions] lỗi: {e}")
        telegram.poll_commands(self.conn)
        self._every("last_snapshot", SNAPSHOT_EVERY_S, paper.snapshot)
        self._every("last_daily", DAILY_EVERY_S, run_daily)

    def run_forever(self, stop=None):
        print(f"Wallet tracker chạy: chains={list(self.clients)}, poll {config.POLL_INTERVAL_S}s.")
        while not (stop and stop.is_set()):
            start = time.time()
            self.run_once()
            time.sleep(max(1, config.POLL_INTERVAL_S - (time.time() - start)))
