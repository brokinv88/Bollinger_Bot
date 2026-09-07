"""Paper runner: forward test C1 trên top20 với $1000 ảo.

Nguyên tắc forward test (không lookahead, không backfill):
- Tài khoản chỉ giao dịch các tín hiệu có entry_time >= THỜI ĐIỂM BẮT ĐẦU paper.
- Mỗi cặp chỉ xét TÍN HIỆU MỚI NHẤT (nến đóng gần nhất) — không mở lại mọi breakout
  lịch sử. Nếu đang có vị thế cùng hướng trên cặp thì bỏ qua (không double down).
- Vào tại open nến kế sau tín hiệu, exit theo SL/TP/timeout như engine backtest C1.

Luồng:
1. Nạp account (state JSON).
2. Đóng vị thế đang mở theo giá hiện tại + engine exit.
3. Quét tín hiệu C1 mới, mở vị thế mới.
4. Ghi nhật ký + snapshot equity.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

from .. import data as data_mod
from .. import engine, indicators as ind, strategies
from . import paper_account as acc
from . import paper_config as cfg

START_MS = int(pd.Timestamp("2023-07-01", tz="UTC").value // 1_000_000)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _close_position(acct: acc.PaperAccount, pos: acc.Position, df: pd.DataFrame) -> dict | None:
    """Đóng vị thế nếu SL/TP/timeout đạt trong dữ liệu hiện tại. Trả trade record hoặc None."""
    entry_ts = pd.Timestamp(pos.entry_time)
    if entry_ts.tzinfo is None:
        entry_ts = entry_ts.tz_localize("UTC")
    after = df[df.index >= entry_ts]
    if not len(after):
        return None
    direction = pos.direction
    stop = pos.stop
    target = pos.target
    max_bars = 20  # time_stop_bars C1
    exit_price = None
    reason = "TIMEOUT"
    exit_ts = None
    for j, (ts, row) in enumerate(after.iterrows()):
        hi, lo, cl = float(row["high"]), float(row["low"]), float(row["close"])
        if j >= max_bars:
            exit_price, reason, exit_ts = cl, "TIMEOUT", ts
            break
        if direction == 1:
            if lo <= stop:
                exit_price, reason, exit_ts = stop, "SL", ts
                break
            if hi >= target:
                exit_price, reason, exit_ts = target, "TP", ts
                break
        else:
            if hi >= stop:
                exit_price, reason, exit_ts = stop, "SL", ts
                break
            if lo <= target:
                exit_price, reason, exit_ts = target, "TP", ts
                break
        exit_price, exit_ts = cl, ts
    if exit_ts is None:
        return None
    risk_price = abs(pos.entry - pos.stop) if pos.entry != pos.stop else 1e-9
    r_mult = direction * (exit_price - pos.entry) / risk_price - cfg.COST_PCT * 2.0
    gross_pnl = direction * (exit_price - pos.entry) * pos.qty - cfg.COST_PCT * pos.qty * pos.entry * 2.0
    trade = {
        "symbol": pos.symbol,
        "direction": pos.direction,
        "entry_time": pos.entry_time,
        "exit_time": exit_ts.isoformat(),
        "entry": pos.entry,
        "exit": float(exit_price),
        "stop": pos.stop,
        "target": pos.target,
        "qty": pos.qty,
        "reason": reason,
        "pnl_usd": round(gross_pnl, 2),
        "r": round(r_mult, 4),
        "entry_equity": pos.entry_equity,
    }
    acct.closed_trades += 1
    acct.realized_pnl += gross_pnl
    acct.cash += gross_pnl
    new_equity = acct.cash
    acct.equity_high_water = max(acct.equity_high_water, new_equity)
    acc.append_equity_point(exit_ts.isoformat(), new_equity)
    return trade


def _paper_start(acct: acc.PaperAccount) -> pd.Timestamp:
    """Thời điểm bắt đầu forward test = lúc tạo account (không backfill lịch sử)."""
    if acct.created_at:
        ts = pd.Timestamp(acct.created_at)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        return ts
    start = pd.Timestamp(_now_ms(), unit="ms", tz="UTC")
    acct.created_at = start.isoformat()
    return start


def _open_new_positions(acct: acc.PaperAccount, now_ms: int) -> tuple[list, int]:
    """Project tín hiệu C1 mới xuất hiện KỂ TỪ LUẦN CHẠY TRƯỚC (forward, không backfill).

    - last_seen_signal[symbol] = entry_time ISO của tín hiệu đã xử lý trước đó.
    - Lần chạy đầu (chưa có marker): chỉ GHI NHẬN tín hiệu hiện tại, KHÔNG mở lệnh
      (thời điểm bắt đầu forward test; không replay lịch sử).
    - Các lần sau: mở mọi tín hiệu mới có entry_time > marker, nhưng chỉ trong
      MAX_SIGNAL_AGE_H (chống backfill khi hệ nghỉ lâu).
    Trả về (danh sách vị thế đã mở, số cặp fetch dữ liệu thành công).
    """
    paper_start = _paper_start(acct)
    opened = []
    active_syms = {p.symbol for p in acct.positions}
    fetched = 0

    for symbol in cfg.get_universe():
        try:
            df = data_mod.fetch_ohlcv(symbol, cfg.TF, START_MS, now_ms)
        except Exception as e:  # noqa: BLE001
            print(f"  [paper] skip {symbol}: {e}", file=sys.stderr)
            continue
        fetched += 1
        if len(df) < 250:
            continue
        sigs = strategies.gen_c1(df)
        if not len(sigs):
            continue
        sigs = sigs.copy()
        sigs["ets"] = pd.to_datetime(sigs["entry_time"], utc=True)
        sigs = sigs[sigs["ets"] <= pd.Timestamp(now_ms, unit="ms", tz="UTC")]
        if not len(sigs):
            continue

        prev_seen = acct.last_seen_signal.get(symbol)
        if prev_seen is None:
            # lần đầu: ghi nhận tín hiệu mới nhất, không mở
            acct.last_seen_signal[symbol] = sigs["entry_time"].iloc[-1]
            continue

        # Tín hiệu MỚI hơn marker
        prev_ts = pd.Timestamp(prev_seen)
        new = sigs[sigs["ets"] > prev_ts]
        # Cập nhật marker lên tín hiệu mới nhất đã thấy (kể cả đã để trễ — không mở backfill)
        acct.last_seen_signal[symbol] = sigs["entry_time"].iloc[-1]
        if not len(new):
            continue

        # GUARD chống backfill: chỉ mở tín hiệu "tươi" xuất hiện trong MAX_SIGNAL_AGE_H.
        # Nếu hệ nghỉ lâu (máy tắt / Actions trễ), tín hiệu cũ đã được đánh marker ở trên
        # nhưng KHÔNG mở lệnh — nếu không, hàng tuần lịch sử sẽ bị replay thành "lệnh mới".
        cutoff = pd.Timestamp(now_ms, unit="ms", tz="UTC") - pd.Timedelta(hours=cfg.MAX_SIGNAL_AGE_H)
        new = new[new["ets"] >= cutoff]
        if not len(new):
            continue

        # Mở TẤT CẢ tín hiệu mới (forward), tránh trùng nếu đang có vị thế cùng hướng
        for _, latest in new.iterrows():
            if symbol in active_syms and any(
                p.symbol == symbol and p.direction == int(latest["direction"]) for p in acct.positions
            ):
                continue
            if any(p.symbol == symbol and p.entry_time == latest["entry_time"] for p in acct.positions):
                continue
            entry_ts = latest["ets"]
            idx = df.index.get_indexer([entry_ts], method="pad")[0]
            if idx < 0 or idx >= len(df):
                continue
            entry = float(df["open"].iloc[idx])
            stop = float(latest["stop"])
            target = float(latest["target"])
            risk_price = abs(entry - stop)
            qty = acct.size_for(risk_price)
            if qty <= 0:
                continue
            pos = acc.Position(
                symbol=symbol,
                direction=int(latest["direction"]),
                entry=entry,
                stop=stop,
                target=target,
                qty=qty,
                entry_time=latest["entry_time"],
                signal_time=latest["signal_time"],
                entry_equity=acct.equity(),
            )
            if acct.open_position(pos):
                opened.append(pos)
                active_syms.add(symbol)
    return opened, fetched


def run() -> None:
    now_ms = _now_ms()
    acct = acc.load()

    # Đóng vị thế đang mở theo dữ liệu mới nhất
    closed_records = []
    data_cache = {}
    open_remaining = []
    fetched = 0
    for pos in acct.positions:
        sym = pos.symbol
        if sym not in data_cache:
            try:
                data_cache[sym] = data_mod.fetch_ohlcv(sym, cfg.TF, START_MS, now_ms)
                fetched += 1
            except Exception as e:  # noqa: BLE001
                print(f"  skip {sym}: {e}", file=sys.stderr)
                data_cache[sym] = None
        df = data_cache[sym]
        if df is None:
            open_remaining.append(pos)
            continue
        rec = _close_position(acct, pos, df)
        if rec is not None:
            closed_records.append(rec)
            acc.append_journal(rec)
        else:
            open_remaining.append(pos)
    acct.positions = open_remaining

    # Mở vị thế mới (forward test)
    new_positions, fetched_open = _open_new_positions(acct, now_ms)
    fetched += fetched_open

    # Đánh dấu lần quét CÓ DỮ LIỆU thành công — chỉ khi thật sự lấy được dữ liệu
    # (tránh trường hợp Actions bị Binance geo-block 451 vẫn đánh dấu sai khiến
    # local bỏ qua móc đó mà không trade).
    if fetched > 0:
        acct.last_good_scan = pd.Timestamp(now_ms, unit="ms", tz="UTC").isoformat()

    eq = acct.equity()
    if new_positions:
        acc.append_equity_point(pd.Timestamp(now_ms, unit="ms", tz="UTC").isoformat(), eq)

    acc.save(acct)

    print("=== PAPER C1 — $1000 %s ===" % pd.Timestamp(now_ms, unit="ms", tz="UTC"))
    print(f"  paper start: {acct.created_at}")
    print(f"  equity: ${eq:.2f}  cash: ${acct.cash:.2f}  high-water: ${acct.equity_high_water:.2f}")
    print(f"  realized PnL: ${acct.realized_pnl:.2f}  closed trades: {acct.closed_trades}")
    print(f"  drawdown: {100*(acct.equity_high_water-eq)/acct.equity_high_water:.2f}%")
    print(f"  open positions: {len(acct.positions)}")
    if closed_records:
        print("\n  Closed this run:")
        for r in closed_records:
            print(f"    {r['symbol']:12s} {'L' if r['direction']==1 else 'S'} {r['reason']:7s} "
                  f"R={r['r']:+.3f} ${r['pnl_usd']:.2f}")
    if new_positions:
        print("\n  Opened this run:")
        for r in new_positions:
            notional = r.qty * r.entry
            print(f"    {r.symbol:12s} {'L' if r.direction==1 else 'S'} "
                  f"qty={r.qty:.6g} entry={r.entry:.6g} stop={r.stop:.6g} notional=${notional:,.0f}")


if __name__ == "__main__":
    run()
