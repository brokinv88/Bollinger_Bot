"""Vòng lặp theo dõi ví: phát hiện lệnh mua/bán mới -> lọc token -> alert + paper trade."""
import time
import traceback

from . import config, db, discovery, market, paper, telegram
from .clients import make_client

WATCHED = ("active", "watch_only")
DAILY_EVERY_S = 6 * 3600


def run_daily(conn):
    """Auto-discovery + tắt ví lỗ + báo cáo. Gửi 1 tin Telegram tổng hợp."""
    msgs = discovery.auto_discover(conn) + discovery.demote_losers(conn) + [telegram.format_stats(conn)]
    telegram.send("\n\n".join(msgs))


def short(a):
    return f"{a[:6]}…{a[-4:]}"


class Monitor:
    def __init__(self, conn, clients=None):
        self.conn = conn
        self.clients = clients if clients is not None else {c: make_client(c) for c in config.active_chains()}

    # --- phát hiện swap ---
    def poll_chain(self, chain):
        client = self.clients[chain]
        wallets = [w["address"] for w in db.list_wallets(self.conn, chain, WATCHED)]
        if not wallets:
            return
        if config.CHAINS[chain]["kind"] == "evm":
            head = client.block_number()
            key = f"block:{chain}"
            cur = db.get_cursor(self.conn, key)
            if cur is None:                      # lần đầu: chỉ đặt mốc, không quét lịch sử
                db.set_cursor(self.conn, key, head)
                return
            if head <= int(cur):
                return
            swaps = client.wallet_swaps(wallets, int(cur) + 1, head)
            db.set_cursor(self.conn, key, head)
        else:
            swaps = []
            for w in wallets:
                key = f"sig:{chain}:{w}"
                s, newest = client.wallet_swaps(w, db.get_cursor(self.conn, key))
                if newest:
                    db.set_cursor(self.conn, key, newest)
                swaps += s
        for s in swaps:
            self.handle_swap(chain, s)

    def handle_swap(self, chain, s, now=None):
        now = now or time.time()
        if not db.insert_trade(self.conn, chain, s["wallet"], s["token"], s["side"], s["amount"], s["tx"], int(now)):
            return
        pair = market.token_pairs(chain, [s["token"]]).get(s["token"])
        price = pair["price"] if pair else None
        if s["side"] == "sell":
            if not price:          # không có giá -> để update_positions xử lý (time-stop)
                return
            closed = paper.on_source_sell(self.conn, chain, s["token"], s["wallet"], price, now)
            for c in closed:
                telegram.send(self.format_close(c, f"ví {short(s['wallet'])} bán"))
            return
        self.handle_buy(chain, s, pair, now)

    def handle_buy(self, chain, s, pair, now):
        wallet = db.get_wallet(self.conn, chain, s["wallet"])
        symbol = pair["symbol"] if pair else "?"
        if pair:
            db.upsert_token(self.conn, chain, s["token"], symbol, pair["price"], int(now))
        buyers = db.distinct_buyers(self.conn, chain, s["token"], int(now) - config.CONFLUENCE_WINDOW_S)
        ok, reasons = market.check_token(chain, s["token"], pair)

        is_sniper = wallet["status"] == "watch_only"
        tag = "🎯 SNIPER" if is_sniper else "🧠 SMART MONEY"
        lines = [f"🟢 {tag} MUA {symbol} ({chain})",
                 f"Ví: {wallet['address']}" + (f" — {wallet['note']}" if wallet["note"] else ""),
                 f"Token: {s['token']}"]
        if pair:
            lines.append(f"Giá ${pair['price']:.8g} | Thanh khoản ${pair['liquidity']:,.0f}")
            age_h = (now - pair["created_ts"]) / 3600 if pair["created_ts"] else None
            if age_h is not None:
                lines.append(f"Tuổi pool: {age_h:.1f}h")
        if len(buyers) >= 2:
            lines.append(f"🔥 HỢP LƯU: {len(buyers)} ví theo dõi cùng mua trong {config.CONFLUENCE_WINDOW_S // 60} phút")
        if not ok:
            lines.append("⛔ Không paper: " + "; ".join(reasons))
        elif is_sniper:
            lines.append("ℹ️ Sniper: chỉ alert, không paper (không thể vào kịp)")
        else:
            for book in config.BOOKS:
                pid, why = paper.try_open(self.conn, book, chain, s["token"], symbol, s["wallet"], pair["price"], now)
                lines.append(f"📝 Paper {book}: " + (f"mở ${config.PAPER_SIZE_USD:.0f}" if pid else why))
        if pair and pair.get("url"):
            lines.append(pair["url"])
        telegram.send("\n".join(lines))

    # --- cập nhật lệnh paper ---
    def update_positions(self, now=None):
        now = now or time.time()
        for chain in {p["chain"] for p in paper.open_positions(self.conn)}:
            tokens = [p["token"] for p in paper.open_positions(self.conn, chain=chain)]
            prices = {t: v["price"] for t, v in market.token_pairs(chain, tokens).items()}
            for t, p in prices.items():
                db.update_token_price(self.conn, chain, t, p)
            for c in paper.update_prices(self.conn, chain, prices, now):
                telegram.send(self.format_close(c, c["reason"]))

    @staticmethod
    def format_close(c, why):
        icon = "✅" if c["pnl_usd"] > 0 else "❌"
        return (f"{icon} Đóng paper [{c['book']}] {c['symbol']} ({c['chain']}) — {why}\n"
                f"PnL ${c['pnl_usd']:+.2f} ({c['pnl_usd'] / c['size_usd']:+.0%})")

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
        last = float(db.get_cursor(self.conn, "last_daily") or 0)
        if time.time() - last >= DAILY_EVERY_S:
            db.set_cursor(self.conn, "last_daily", time.time())
            try:
                run_daily(self.conn)
            except Exception as e:
                print(f"[daily] lỗi: {e}")

    def run_forever(self):
        print(f"Wallet tracker chạy: chains={list(self.clients)}, poll {config.POLL_INTERVAL_S}s. Ctrl+C để dừng.")
        while True:
            start = time.time()
            self.run_once()
            time.sleep(max(1, config.POLL_INTERVAL_S - (time.time() - start)))
