"""Test offline (không gọi mạng): python -m pytest wallet_tracker/test_wallet_tracker.py"""
import pytest

from wallet_tracker import config, db, discovery, market, monitor, paper, scoring, settings, telegram
from wallet_tracker.chains import evm

W1 = "0x" + "a" * 40
W2 = "0x" + "b" * 40
W3 = "0x" + "f" * 40
TOKEN = "0x" + "c" * 40
PAIR = "0x" + "d" * 40
NOW = 1_800_000_000


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(telegram, "send", out.append)
    return out


@pytest.fixture
def conn(tmp_path, monkeypatch, sent):
    monkeypatch.setattr(market, "token_security",
                        lambda c, t: {"honeypot": False, "buy_tax": 0, "sell_tax": 0, "creator": W3})
    return db.connect(str(tmp_path / "t.db"))


def set_price(monkeypatch, price, liq=200_000):
    monkeypatch.setattr(market, "token_pairs", lambda chain, toks: {
        t: {"price": price, "liquidity": liq, "symbol": "MEME", "pair": PAIR, "created_ts": NOW - 3600, "url": ""}
        for t in toks})


def swap(wallet, side, amount, tx):
    return {"wallet": wallet, "token": TOKEN, "side": side, "amount": amount, "tx": tx}


def test_buy_opens_books_and_mirror_sells_proportionally(conn, sent, monkeypatch):
    db.add_wallet(conn, "base", W1)
    m = monitor.Monitor(conn, clients={})
    set_price(monkeypatch, 1.0)
    sig = m.handle_swap("base", swap(W1, "buy", 1000, "0x1"), NOW)
    assert sig.kind == "buy" and len(paper.open_positions(conn)) == 2
    assert m.handle_swap("base", swap(W1, "buy", 1000, "0x1"), NOW) is None        # trùng tx
    assert m.handle_swap("base", swap(W1, "buy", 1000, "0x1b"), NOW).kind == "buy_more"
    set_price(monkeypatch, 1.5)
    sig = m.handle_swap("base", swap(W1, "sell", 1000, "0x2"), NOW + 60)            # bán 50% vị thế ví
    assert sig.kind == "sell_partial" and sig.sell_fraction == pytest.approx(0.5)
    mirror = paper.open_positions(conn, "mirror")[0]
    assert mirror["remaining_qty"] == pytest.approx(mirror["qty"] * 0.5)
    sig = m.handle_swap("base", swap(W1, "sell", 1000, "0x3"), NOW + 120)
    assert sig.kind == "sell_all" and paper.open_positions(conn, "mirror") == []
    s = paper.book_stats(conn)["mirror"]
    assert s["closed"] == 1 and s["pnl"] == pytest.approx(100 * (1.5 * 0.985 / 1.015 - 1))
    assert any("BÁN MỘT PHẦN" in t for t in sent) and any("Đóng paper" in t for t in sent)


def test_filters_block_low_liq_blacklist_labels_and_sniper(conn, sent, monkeypatch):
    db.add_wallet(conn, "base", W1)
    db.add_wallet(conn, "base", W2, status="watch_only")
    m = monitor.Monitor(conn, clients={})
    set_price(monkeypatch, 1.0, liq=50_000)
    assert "thanh khoản" in m.handle_swap("base", swap(W1, "buy", 1, "0x1"), NOW).reasons[0]
    set_price(monkeypatch, 1.0)
    m.handle_swap("base", swap(W2, "buy", 1, "0x2"), NOW)
    assert paper.open_positions(conn) == [] and "HỢP LƯU" in sent[1]
    db.blacklist_add(conn, "*", TOKEN, "scam")
    db.set_label(conn, "base", W1, "insider")
    sig = m.handle_swap("base", {**swap(W1, "buy", 1, "0x4"), "token": TOKEN}, NOW)
    assert any("blacklist" in r for r in sig.reasons) and any("insider" in r for r in sig.reasons)


def test_tp_ladder_trailing_sl_time_and_capital(conn):
    for i in range(12):
        paper.try_open(conn, "fixed", "base", f"t{i}", "X", W1, 1.0, NOW)
    assert len(paper.open_positions(conn, "fixed")) == 10          # 1000$ / 100$
    paper.update_prices(conn, "base", {"t0": 2.1, "t1": 0.7}, NOW + 3600)
    t0 = conn.execute("SELECT * FROM positions WHERE token='t0'").fetchone()
    assert t0["status"] == "open" and t0["remaining_qty"] == pytest.approx(t0["qty"] * 0.5) and t0["tp_level"] == 1
    assert conn.execute("SELECT status FROM positions WHERE token='t1'").fetchone()[0] == "closed"
    paper.update_prices(conn, "base", {"t0": 1.4}, NOW + 7200)       # -33% từ đỉnh 2.1 -> trailing
    assert conn.execute("SELECT reason FROM positions WHERE token='t0'").fetchone()[0].startswith("trailing")
    paper.update_prices(conn, "base", {"t2": 1.0}, NOW + 73 * 3600)
    reasons = {r[0] for r in conn.execute("SELECT reason FROM positions WHERE token IN ('t2','t3')")}
    assert reasons == {"hết thời gian", "không còn giá"}


def test_settings_override(conn):
    settings.set(conn, "MIN_LIQUIDITY_USD", 5000)
    assert settings.get(conn, "MIN_LIQUIDITY_USD") == 5000.0
    with pytest.raises(TypeError):
        settings.set(conn, "BLOCK_LABELS", "x")


def test_compute_metrics_and_labels():
    d = 86400
    trades = [
        {"ts": NOW - 20 * d, "token": "A", "side": "buy", "qty": 100, "usd": 100},
        {"ts": NOW - 19 * d, "token": "A", "side": "sell", "qty": 100, "usd": 300},
        {"ts": NOW - 3 * d, "token": "B", "side": "buy", "qty": 10, "usd": 100},
        {"ts": NOW - 2 * d, "token": "B", "side": "sell", "qty": 5, "usd": 25},
        {"ts": NOW - 2 * d, "token": "C", "side": "sell", "qty": 5, "usd": 999},   # không có giá vốn -> bỏ
    ]
    m = scoring.compute_metrics(trades, NOW)
    assert m["pnl_30d"] == pytest.approx(200 - 25) and m["winrate_30d"] == 0.5 and m["tokens_30d"] == 2
    assert m["pnl_7d"] == pytest.approx(-25) and m["winrate_7d"] == 0.0
    flips = [t for i in range(6) for t in (
        {"ts": NOW - d + i * 100, "token": f"F{i}", "side": "buy", "qty": 1, "usd": 10},
        {"ts": NOW - d + i * 100 + 5, "token": f"F{i}", "side": "sell", "qty": 1, "usd": 10})]
    m2 = scoring.compute_metrics(flips, NOW)
    assert scoring._flipper(m2, flips)[0] == "bot_flipper"


class FakeEvm:
    def __init__(self, buyers):
        self.buyers = buyers

    def early_buyers(self, *a):
        return self.buyers


class FakeProvider:
    name = "fake"

    def __init__(self, sources):
        self.sources = sources

    def funding_sources(self, chain, wallet):
        return self.sources.get(wallet, [])

    def trades(self, chain, wallet, days):
        return []


def test_discovery_promotes_and_tags_insider(conn, sent, monkeypatch):
    set_price(monkeypatch, 1.0)
    fake = FakeEvm({W1: 300, W2: 10, PAIR: 400})
    prov = FakeProvider({PAIR: [W3]})                                # PAIR (dùng như 1 ví) do creator nạp tiền
    r1 = discovery.discover_token(conn, "base", TOKEN, client=fake, provider=prov)
    assert r1["new"] == 3 and r1["promoted"] == []
    r2 = discovery.discover_token(conn, "base", "0x" + "e" * 40, client=fake, provider=prov)
    assert dict(r2["promoted"]) == {W1: "active", W2: "watch_only"}
    assert db.get_wallet(conn, "base", PAIR)["status"] == "candidate"      # insider bị chặn
    assert "insider" in db.get_labels(conn, "base", PAIR)
    assert any("->" in t for t in sent)


def test_telegram_add_command(conn):
    assert "Đã thêm" in telegram.handle_command(conn, f"/add base {W1} kol")
    assert db.get_wallet(conn, "base", W1)["status"] == "active"
    telegram.handle_command(conn, f"/remove base {W1}")
    assert db.get_wallet(conn, "base", W1)["status"] == "disabled"


def test_evm_wallet_swaps_filters_spam_and_quotes(monkeypatch):
    c = evm.EvmClient("base", config.CHAINS["base"])
    weth = config.CHAINS["base"]["quotes"][0]
    log = lambda token, frm, to, tx: {"address": token, "topics": [evm.TRANSFER, evm._topic(frm), evm._topic(to)],
                                     "data": hex(5 * 10 ** 18), "transactionHash": tx, "blockNumber": "0x10"}
    in_logs = [log(TOKEN, PAIR, W1, "0xbuy"), log(TOKEN, PAIR, W1, "0xspam"), log(weth, PAIR, W1, "0xbuy")]
    out_logs = [log(TOKEN, W1, PAIR, "0xsell")]
    monkeypatch.setattr(c, "get_logs", lambda f, t, address=None, topics=None: in_logs if topics[1] is None else out_logs)
    monkeypatch.setattr(c, "tx_from", lambda h: PAIR if h == "0xspam" else W1)
    monkeypatch.setattr(c, "decimals", lambda t: 18)
    got = sorted((s["side"], s["tx"], s["amount"]) for s in c.wallet_swaps([W1], 1, 20))
    assert got == [("buy", "0xbuy", 5.0), ("sell", "0xsell", 5.0)]
