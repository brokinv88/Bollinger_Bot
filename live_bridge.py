"""live_bridge.py — bản copy-to-live của futures_paper, mặc định chạy DRY-RUN (KHÔNG RỦI RO).

Hai chế độ:
  DRY_RUN (mặc định):
    - Chạy ĐÚNG engine futures_paper (cùng logic SL/TP/trailing/BE, cùng universe 47 mã,
      cùng khung giờ scan H4 05 0,4,8,12,16,20 + monitor 30 phút).
    - State/trades/equity lưu RIÊNG sang *_bridge.* để so sánh với bot giấy (paper_*).
    - Mỗi quyết định lệnh được "log" dưới dạng order chuẩn Binance vào bridge_orders.jsonl
      (vd: STOP_MARKET reduceOnly stopPrice=...) — KHÔNG gọi API thật, KHÔNG cần API key.
  REAL:
    - Chỉ bật khi sẵn sàng: đặt FUTURES_BRIDGE_REAL=True + nhập key.
    - CẢNH BÁO: trước khi live phải có lệnh stop ở sàn ngay khi mở lệnh.

Chạy:
  python live_bridge.py --scan --notify
  python live_bridge.py --monitor
  python live_bridge.py --status
  python live_bridge.py --reset
"""
import argparse
import json
import os
import time

import futures_paper as fp

REAL = bool(os.environ.get("FUTURES_BRIDGE_REAL", "").strip())

BRIDGE_STATE = "bridge_state.json"
BRIDGE_TRADES = "bridge_trades.csv"
BRIDGE_EQUITY = "bridge_equity.csv"
BRIDGE_ORDERS = "bridge_orders.jsonl"

# Định tuyến engine futures_paper sang bộ file riêng của bridge (không đụng bot giấy).
fp.STATE_FILE = BRIDGE_STATE
fp.TRADES_CSV = BRIDGE_TRADES
fp.EQUITY_CSV = BRIDGE_EQUITY


def _order_log(verb, order):
    """Ghi 1 order (DRY_RUN: chỉ log JSON; REAL: chưa cài, sẽ gọi Binance tại đây)."""
    rec = {"ts_ms": int(time.time() * 1000), "verb": verb, "mode": "REAL" if REAL else "DRY_RUN",
           "order": order}
    with open(BRIDGE_ORDERS, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if not REAL:
        print(f"[BRIDGE DRY-RUN] {verb} {order.get('symbol')} "
              f"{order.get('type')} side={order.get('side')} stopPrice={order.get('stopPrice')}")


def _closes_at(verb, pos, exit_px, reason):
    order = {"symbol": pos["symbol"], "side": "SELL" if pos["direction"] == 1 else "BUY",
             "type": "MARKET", "reduceOnly": True, "reason": reason,
             "qty": round(pos["notional"] / pos["entry_px"], 8),
             "price_hint": round(exit_px, 4)}
    _order_log(verb, order)


def _stops_for(pos):
    return {"symbol": pos["symbol"], "side": "SELL" if pos["direction"] == 1 else "BUY",
            "type": "STOP_MARKET", "timeInForce": "GTE_GTC", "reduceOnly": True,
            "stopPrice": round(pos["trail"], 4),
            "qty": round(pos["notional"] / pos["entry_px"], 8)}


def _position_key(pos):
    return (pos["symbol"], pos["entry_time"])


def _positions_snapshot():
    st = fp.load_state()
    return {_position_key(p): dict(p) for p in st.get("positions", [])}, st


def _log_orders_between(before, after):
    """So sánh trước/sau một lần chạy → ghi would-be order chuẩn Binance."""
    # Lệnh mở mới: đặt STOP_MARKET (lớp bảo vệ ở sàn) ngay khi mở
    for key, pos in after.items():
        if key not in before:
            _order_log("PLACE", _stops_for(pos))
    # Trail/BE đổi: cập nhật lại stopPrice của lệnh stop đang treo
    for key, pos in after.items():
        if key in before and before[key]["trail"] != pos["trail"]:
            _order_log("UPDATE", _stops_for(pos))
    # Vị thế đóng: hủy stop treo + market close (reduceOnly)
    for key, pos in before.items():
        if key not in after:
            _closes_at("CANCEL+CLOSE", pos, pos.get("exit_px", pos["trail"]), pos["reason"])


def run_scan(notify_tg=True):
    if not fp._cfg("ENABLE_FUTURES_AUTO_TRADE", True):
        print("ENABLE_FUTURES_AUTO_TRADE = False -> bỏ qua live_bridge.")
        return None
    before, _ = _positions_snapshot()
    mon = fp.monitor_stops(notify_tg=False)
    symbols = fp.top_universe()
    text = fp.run_live(symbols, fresh=False)
    if mon:
        text = (mon + "\n\n" + text) if text else mon
    after, st = _positions_snapshot()
    _log_orders_between(before, after)
    if text and notify_tg:
        fp.notify(text)
    return text


def run_monitor(notify_tg=True):
    before, _ = _positions_snapshot()
    text = fp.monitor_stops(notify_tg=False)
    after, st = _positions_snapshot()
    _log_orders_between(before, after)
    if text and notify_tg:
        fp.notify(text)
    return text


def status():
    st = fp.load_state()
    mu = sum(p["margin"] for p in st["positions"])
    mp = mu / st["equity"] * 100 if st["equity"] > 0 else 0
    print(f"[{('REAL' if REAL else 'DRY_RUN')}] equity ${st['equity']:,.2f}  peak ${st['peak']:,.2f}  "
          f"cursor {st['cursor']}  lệnh {st['n_trades']}")
    print(f"n_pos {len(st['positions'])}  margin ${mu:,.0f} = {mp:.0f}% equity (trần 40%)")
    for p in st["positions"]:
        side = 'LONG' if p['direction'] == 1 else 'SHORT'
        print(f"  {p['strategy']} {p['symbol']} {side} @{p['entry_px']:.4f} trail {p['trail']:.4f} "
              f"tp {p['tp']:.4f} notional ${p['notional']:,.0f}")
    if os.path.exists(BRIDGE_ORDERS):
        print(f"bridge_orders.jsonl: {sum(1 for _ in open(BRIDGE_ORDERS))} lệnh đã log")


def seed_from_paper():
    """Copy trạng thái bot giấy hiện tại sang bridge để so sánh công bằng từ cùng điểm."""
    import shutil
    paper_state = fp._cfg("FUTURES_STATE_FILE", "paper_state.json")
    paper_trades = fp._cfg("FUTURES_TRADES_CSV", "paper_trades.csv")
    paper_equity = fp._cfg("FUTURES_EQUITY_CSV", "paper_equity.csv")
    if not os.path.exists(paper_state):
        print("Chưa có paper state — chạy futures_paper --scan trước.")
        return
    if os.path.exists(BRIDGE_STATE):
        print("bridge_state đã tồn tại — không seed lại (xóa trước nếu muốn).")
        return
    shutil.copy(paper_state, BRIDGE_STATE)
    if os.path.exists(paper_trades):
        shutil.copy(paper_trades, BRIDGE_TRADES)
    if os.path.exists(paper_equity):
        shutil.copy(paper_equity, BRIDGE_EQUITY)
    print("Seeded bridge từ paper state (điểm xuất phát giống hệt).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--monitor", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--seed", action="store_true", help="seed từ paper state (chạy 1 lần)")
    ap.add_argument("--notify", action="store_true")
    a = ap.parse_args()

    if a.seed:
        seed_from_paper()
        return
    if a.reset:
        for f in (BRIDGE_STATE, BRIDGE_TRADES, BRIDGE_EQUITY, BRIDGE_ORDERS):
            if os.path.exists(f):
                os.remove(f)
        print("Reset live_bridge state + logs.")
        return
    if a.status:
        status()
        return
    if a.monitor:
        text = run_monitor(notify_tg=a.notify)
        print(text or "Không có vị thế nào xuyên SL realtime.")
        return
    text = run_scan(notify_tg=a.notify)
    if text:
        print("\n" + text)


if __name__ == "__main__":
    main()