"""Test offline (không gọi mạng): python -m pytest wallet_tracker/test_wallet_tracker.py"""
import pytest

from wallet_tracker import config, db, discovery, market, monitor, paper, telegram
from wallet_tracker.chains import evm

W1 = "0x" + "a" * 40
W2 = "0x" + "b" * 40
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
    monkeypatch.setattr(market, "token_security", lambda c, t: {"honeypot": False, "buy_tax": 0, "sell_tax": 0})
    return db.connect(str(tmp_path / "t.db"))


def set_price(monkeypatch, price, liq=200_000):
    monkeypatch.setattr(market, "token_pairs", lambda chain, toks: {
        t: {"price": price, "liquidity": liq, "symbol": "MEME", "pair": PAIR, "created_ts": NOW - 3600, "url": ""}
        for t in toks})


def test_buy_opens_both_books_and_mirror_sell_closes(conn, sent, monkeypatch):
    db.add_wallet(conn, "base", W1)
    m = monitor.Monitor(conn, clients={})
    set_price(monkeypatch, 1.0)
    m.handle_swap("base", {"wallet": W1, "token": TOKEN, "side": "buy", "amount": 1, "tx": "0x1"}, NOW)
    assert len(paper.open_positions(conn)) == 2
    m.handle_swap("base", {"wallet": W1, "token": TOKEN, "side": "buy", "amount": 1, "tx": "0x1"}, NOW)  # trùng tx
    assert len(sent) == 1
    set_price(monkeypatch, 1.5)
    m.handle_swap("base", {"wallet": W1, "token": TOKEN, "side": "sell", "amount": 1, "tx": "0x2"}, NOW + 60)
    assert [p["book"] for p in paper.open_positions(conn)] == ["fixed"]
    s = paper.book_stats(conn)["mirror"]
    assert s["closed"] == 1 and s["pnl"] == pytest.approx(100 * (1.5 * 0.985 / 1.015 - 1))


def test_low_liquidity_and_sniper_do_not_paper(conn, sent, monkeypatch):
    db.add_wallet(conn, "base", W1)
    db.add_wallet(conn, "base", W2, status="watch_only")
    m = monitor.Monitor(conn, clients={})
    set_price(monkeypatch, 1.0, liq=50_000)
    m.handle_swap("base", {"wallet": W1, "token": TOKEN, "side": "buy", "amount": 1, "tx": "0x1"}, NOW)
    set_price(monkeypatch, 1.0)
    m.handle_swap("base", {"wallet": W2, "token": TOKEN, "side": "buy", "amount": 1, "tx": "0x2"}, NOW)
    assert paper.open_positions(conn) == []
    assert "HỢP LƯU" in sent[1]


def test_tp_sl_time_and_capital_limit(conn):
    for i in range(12):
        paper.try_open(conn, "fixed", "base", f"t{i}", "X", W1, 1.0, NOW)
    assert len(paper.open_positions(conn, "fixed")) == 10          # 1000$ / 100$
    closed = paper.update_prices(conn, "base", {"t0": 2.1, "t1": 0.7, "t2": 1.0}, NOW + 73 * 3600)
    reasons = sorted(c["reason"] for c in closed)
    assert reasons.count("TP") == 1 and reasons.count("SL") == 1 and "không còn giá" in reasons


class FakeEvm:
    def __init__(self, buyers):
        self.buyers = buyers

    def early_buyers(self, *a):
        return self.buyers


def test_discovery_promotes_after_two_hits(conn, monkeypatch):
    set_price(monkeypatch, 1.0)
    fake = FakeEvm({W1: 300, W2: 10})
    r1 = discovery.discover_token(conn, "base", TOKEN, client=fake)
    assert r1["new"] == 2 and r1["promoted"] == []
    r2 = discovery.discover_token(conn, "base", "0x" + "e" * 40, client=fake)
    status = {w: s for w, s, *_ in r2["promoted"]}
    assert status == {W1: "active", W2: "watch_only"}


def test_telegram_add_command(conn):
    assert "Đã thêm" in telegram.handle_command(conn, f"/add base {W1} kol")
    assert db.get_wallet(conn, "base", W1)["status"] == "active"
    telegram.handle_command(conn, f"/remove base {W1}")
    assert db.get_wallet(conn, "base", W1)["status"] == "disabled"


def test_evm_wallet_swaps_filters_spam_and_quotes(monkeypatch):
    c = evm.EvmClient("base", config.CHAINS["base"])
    weth = config.CHAINS["base"]["quotes"][0]
    log = lambda token, frm, to, tx: {"address": token, "topics": [evm.TRANSFER, evm._topic(frm), evm._topic(to)],
                                     "data": hex(5), "transactionHash": tx, "blockNumber": "0x10"}
    in_logs = [log(TOKEN, PAIR, W1, "0xbuy"), log(TOKEN, PAIR, W1, "0xspam"), log(weth, PAIR, W1, "0xbuy")]
    out_logs = [log(TOKEN, W1, PAIR, "0xsell")]
    monkeypatch.setattr(c, "get_logs", lambda f, t, address=None, topics=None: in_logs if topics[1] is None else out_logs)
    monkeypatch.setattr(c, "tx_from", lambda h: PAIR if h == "0xspam" else W1)
    got = sorted((s["side"], s["tx"]) for s in c.wallet_swaps([W1], 1, 20))
    assert got == [("buy", "0xbuy"), ("sell", "0xsell")]
