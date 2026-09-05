"""Paper trader futures theo kế hoạch futures_trading_plan.md (vốn $2,000).

Chỉ xử lý nến H4 ĐÃ ĐÓNG tại móc 00/04/08/12/16/20 UTC — không nhìn nến đang hình thành.
Cùng engine cho live (--scan) và replay lịch sử (--replay) → kết quả khớp backtest.

Quy tắc từ kế hoạch (futures_trading_plan.md):
  - risk 0.75% equity/lệnh (Donchian), 0.60% (Keltner); leverage 3x; margin tối đa 40%.
  - tối đa 6 vị thế song song; 1 vị thế/symbol (chiến lược đến trước chiếm slot).
  - SL 2*ATR ngay khi vào; TP/trailing/BE đúng logic chiến lược; funding mỗi 8h; taker fee 0.05% x2.
  - đóng cửa nhận lệnh mới khi lỗ -5%/ngày, -10%/tuần (bỏ bằng --force khi đã rõ lý do).
"""
import argparse
import json
import os
import time
import numpy as np
import pandas as pd

# Cấu hình lấy từ config.__dict__ để có thể chạy độc lập (không import config) hoặc
# như một cấu phần (import qua auto_trade.py) với giá trị từ FUTURES_* trong config.py.
try:
    import config
    _CFG = config.__dict__
except Exception:
    _CFG = {}

from research_futures_framework import (
    fetch_klines, fetch_funding, add_indicators, merge_funding,
    TAKER_FEE, CORE_SYMBOLS,
)

def _cfg(key, default):
    return _CFG.get(key, default)

STATE_FILE = _cfg("FUTURES_STATE_FILE", "paper_state.json")
TRADES_CSV = _cfg("FUTURES_TRADES_CSV", "paper_trades.csv")
EQUITY_CSV = _cfg("FUTURES_EQUITY_CSV", "paper_equity.csv")
REPLAY_TRADES = "paper_trades_replay.csv"
UNIVERSE_CSV = "backtest_futures_universe.csv"

EQUITY0 = _cfg("FUTURES_START_EQUITY", 2000.0)
LEV = _cfg("FUTURES_LEVERAGE", 3.0)
MAX_POS = _cfg("FUTURES_MAX_POS", 6)
MAX_STRAT = {"DON": 3, "KELT": 3}
MAX_MARGIN_PCT = _cfg("FUTURES_MAX_MARGIN_PCT", 0.40)
DAILY_LOSS = _cfg("FUTURES_DAILY_LOSS", -0.05)
WEEKLY_LOSS = _cfg("FUTURES_WEEKLY_LOSS", -0.10)
MAX_T4 = 2
H4 = 4 * 3600 * 1000
FUND_TS = 8 * 3600 * 1000

DON = dict(risk=_cfg("FUTURES_RISK_DON", 0.0075), sl=2.0, tp=7.0, trail=4.0, be=2.0, dc=55, fdmax=0.0005, adx=20)
KELT = dict(risk=_cfg("FUTURES_RISK_KELT", 0.0060), mult=1.5, sl=2.0, tp=6.0, trail=3.5, be=2.0, fdmax=0.0006, adx=18)
STRATS = {"DON": DON, "KELT": KELT}

WARMUP = 130


def notify(msg):
    """Gửi Telegram nếu có token, ngược lại in preview."""
    try:
        import notifier
        notifier.send_telegram_alert(msg)
    except Exception:
        print("[TELEGRAM PREVIEW]:")
        print(msg)
        print("-" * 50)


def tier_map():
    return {"T1": "T1 - ổn định", "T2": "T2 - cân bằng", "T3": "T3 - biến động mạnh",
            "T4": "T4 - rất mạnh (size nhỏ)"}


def load_universe():
    if not os.path.exists(UNIVERSE_CSV):
        return {t: [s for s in CORE_SYMBOLS] for t in ("T1", "T2", "T3", "T4")}
    df = pd.read_csv(UNIVERSE_CSV)
    out = {}
    for t, label in tier_map().items():
        out[t] = list(df.loc[df["tier"] == label, "symbol"])
    out["T1"] = [s for s in out["T1"] if s.isalnum() and s != "BT C"] or CORE_SYMBOLS
    return out


def top_universe(only_t12=False):
    uni = load_universe()
    syms = [s for s in uni["T1"] + uni["T2"] + uni["T3"]]
    if not only_t12:
        syms += uni["T4"][:MAX_T4]
    seen, out = set(), []
    for s in syms:
        if s not in seen and s.isalnum():
            seen.add(s); out.append(s)
    return out


def default_state():
    return dict(equity=EQUITY0, peak=EQUITY0, day_start_eq=EQUITY0, week_start_eq=EQUITY0,
                positions=[], cursor=None, last_ts=None, n_trades=0)


def load_state():
    if not os.path.exists(STATE_FILE):
        return default_state()
    with open(STATE_FILE) as f:
        st = json.load(f)
    for k, v in default_state().items():
        st.setdefault(k, v)
    st["peak"] = max(st["equity"], st.get("peak", st["equity"]))
    return st


def save_state(st):
    with open(STATE_FILE, "w") as f:
        json.dump(st, f, indent=1)


def ensure_logs(replay=False):
    trades = REPLAY_TRADES if replay else TRADES_CSV
    if not os.path.exists(trades):
        pd.DataFrame(columns=["strategy", "symbol", "direction", "entry_time", "exit_time",
                              "entry_px", "exit_px", "reason", "atr_pct", "notional",
                              "gross_usd", "funding_usd", "fee_usd", "net_usd", "equity_after"]
                     ).to_csv(trades, index=False)
    if not replay and not os.path.exists(EQUITY_CSV):
        pd.DataFrame(columns=["ts", "equity", "n_pos", "margin_pct", "note"]).to_csv(EQUITY_CSV, index=False)


class PaperLot:
    def __init__(self, st, symbols, replay=False, force=False):
        self.st = st
        self.tiers = {}
        uni = load_universe()
        for t, syms in uni.items():
            for s in syms:
                self.tiers[s] = t
        self.replay = replay
        self.force = force
        self.t4_open = 0
        self.log = []
        for p in st["positions"]:
            if self.tiers.get(p["symbol"]) == "T4":
                self.t4_open += 1
        ensure_logs(replay)

    def equity(self):
        return self.st["equity"]

    def margin_used(self):
        return sum(p["margin"] for p in self.st["positions"])

    def margin_pct(self):
        return self.margin_used() / self.equity() * 100 if self.equity() > 0 else 0.0

    def frozen(self, ts):
        if self.force:
            return False
        if self.st["equity"] < self.st["day_start_eq"] * (1 + DAILY_LOSS):
            self.log.append(f"FREEZE_DAY@{ts}: equity {self.equity():.0f} < day start {self.st['day_start_eq']:.0f} (±{-DAILY_LOSS*100:.0f}%)")
            return True
        if self.st["equity"] < self.st["week_start_eq"] * (1 + WEEKLY_LOSS):
            self.log.append(f"FREEZE_WEEK@{ts}: equity {self.equity():.0f} < week start {self.st['week_start_eq']:.0f} (±{-WEEKLY_LOSS*100:.0f}%)")
            return True
        return False

    def snapshot(self, ts, note=""):
        if not self.replay:
            pd.DataFrame([[ts, self.equity(), len(self.st["positions"]),
                           round(self.margin_pct(), 1), note]],
                         columns=["ts", "equity", "n_pos", "margin_pct", "note"]).to_csv(
                EQUITY_CSV, mode="a", header=False, index=False)

    # --------------------------------------------- entry logic (giống backtest)
    def entry_pair(self, df, i, strat):
        c = float(df["close"].iloc[i])
        fr = float(df["funding_rate"].fillna(0).iloc[i])
        atr = float(df["atr"].iloc[i])
        if np.isnan(atr) or atr <= 0:
            return 0, None
        if strat == "DON":
            a50 = df["atr_sma50"].iloc[i]
            if pd.isna(a50) or float(df["atr_pct"].iloc[i]) <= a50:
                return 0, None
            adx = df["adx14"].iloc[i]
            if pd.isna(adx) or adx < DON["adx"]:
                return 0, None
            hi = df["dc_high55"].iloc[i]; lo = df["dc_low55"].iloc[i]
            if c > hi and c > df["ema50"].iloc[i] and fr <= DON["fdmax"]:
                return 1, atr
            if c < lo and c < df["ema50"].iloc[i] and fr >= -DON["fdmax"]:
                return -1, atr
            return 0, None
        adx = df["adx14"].iloc[i]
        if pd.isna(adx) or adx < KELT["adx"]:
            return 0, None
        if c > df["k_up"].iloc[i] and fr <= KELT["fdmax"]:
            return 1, atr
        if c < df["k_lo"].iloc[i] and fr >= -KELT["fdmax"]:
            return -1, atr
        return 0, None

    def open_position(self, ts, strat, symbol, df, i, direction, atr_entry):
        cfg = STRATS[strat]
        entry = float(df["close"].iloc[i])
        sl_frac = 2.0 * atr_entry / entry
        notional = self.equity() * cfg["risk"] / sl_frac if sl_frac > 0 else 0
        margin = notional / LEV
        if notional <= 0 or margin <= 0:
            return
        if margin + self.margin_used() > MAX_MARGIN_PCT * self.equity():
            self.log.append(f"SKIP_MARGIN@{ts}: {strat} {symbol} → margin {self.margin_pct()+(margin/self.equity())*100:.0f}% > 40%")
            return
        n_strat = sum(1 for p in self.st["positions"] if p["strategy"] == strat)
        if n_strat >= MAX_STRAT[strat]:
            self.log.append(f"SKIP_MAXPOS@{ts}: {strat} {symbol} hết slot ({MAX_STRAT[strat]})")
            return
        if len(self.st["positions"]) >= MAX_POS:
            self.log.append(f"SKIP_MAXPOS@{ts}: {strat} {symbol} đủ {MAX_POS} vị thế")
            return
        if self.tiers.get(symbol) == "T4" and self.t4_open >= MAX_T4:
            self.log.append(f"SKIP_T4@{ts}: {strat} {symbol} tối đa {MAX_T4} T4")
            return
        if self.frozen(ts):
            return
        pos = dict(strategy=strat, symbol=symbol, direction=direction,
                   entry_time=ts, entry_px=entry, atr=atr_entry,
                   trail=entry - direction * cfg["sl"] * atr_entry,
                   tp=entry + direction * cfg["tp"] * atr_entry,
                   be_done=False, notional=notional, margin=margin, fund=0.0, last_i=i)
        self.st["positions"].append(pos)
        if self.tiers.get(symbol) == "T4":
            self.t4_open += 1
        self.log.append(f"OPEN@{ts} {strat} {symbol} {'L'+str(int(direction*100))}: @{entry:.4f} notional ${notional:,.0f} margin ${margin:,.0f} ATR {atr_entry/entry*100:.2f}%")

    # ------------------------------------------------------------- 8h funding
    def charge_funding(self, pos, df, i, ts):
        if ts % FUND_TS != 0:
            return
        fr = float(df["funding_rate"].fillna(0).iloc[i])
        pos["fund"] += -pos["direction"] * fr * pos["notional"]

    # ------------------------------------------------------------- exit/close
    def manage_exit(self, pos, df, i, ts):
        cfg = STRATS[pos["strategy"]]
        c, hi, lo = float(df["close"].iloc[i]), float(df["high"].iloc[i]), float(df["low"].iloc[i])
        if not pos["be_done"] and abs(c - pos["entry_px"]) >= cfg["be"] * pos["atr"]:
            pos["trail"] = pos["entry_px"]
            pos["be_done"] = True
        extreme = hi if pos["direction"] == 1 else lo
        if pos["direction"] == 1:
            pos["trail"] = max(pos["trail"], extreme - cfg["trail"] * pos["atr"])
        else:
            pos["trail"] = min(pos["trail"], extreme + cfg["trail"] * pos["atr"])
        hit_tp = (pos["direction"] == 1 and hi >= pos["tp"]) or (pos["direction"] == -1 and lo <= pos["tp"])
        hit_trail = (pos["direction"] == 1 and lo <= pos["trail"]) or (pos["direction"] == -1 and hi >= pos["trail"])
        if not (hit_tp or hit_trail):
            return
        exit_px = pos["tp"] if hit_tp else pos["trail"]
        gross = pos["direction"] * (exit_px - pos["entry_px"]) / pos["entry_px"]
        gross_usd = gross * pos["notional"]
        fee = 2 * TAKER_FEE * pos["notional"]
        net = gross_usd - fee + pos["fund"]
        self.st["equity"] += net
        self.st["peak"] = max(self.st["peak"], self.st["equity"])
        self.st["n_trades"] += 1
        rec = dict(strategy=pos["strategy"], symbol=pos["symbol"], direction=pos["direction"],
                   entry_time=pos["entry_time"], exit_time=ts, entry_px=pos["entry_px"],
                   exit_px=exit_px, reason="TP" if hit_tp else "TRAIL",
                   atr_pct=round(pos["atr"] / pos["entry_px"] * 100, 3), notional=round(pos["notional"], 2),
                   gross_usd=round(gross_usd, 2), funding_usd=round(pos["fund"], 2),
                   fee_usd=round(fee, 2), net_usd=round(net, 2), equity_after=round(self.st["equity"], 2))
        out = REPLAY_TRADES if self.replay else TRADES_CSV
        pd.DataFrame([rec]).to_csv(out, mode="a", header=False, index=False)
        self.st["positions"].remove(pos)
        if self.tiers.get(pos["symbol"]) == "T4":
            self.t4_open -= 1
        self.log.append(f"CLOSE@{ts} {pos['strategy']} {pos['symbol']}: @{exit_px:.4f} net ${net:+.2f} → equity ${self.equity():,.2f}")

    # ------------------------------------------------- synthesizer data
    def prepare(self, symbol, start_ms, end_ms):
        df = fetch_klines(symbol, "4h", int(start_ms), int(end_ms))
        if len(df) < WARMUP + 10:
            return None
        fund = fetch_funding(symbol, int(start_ms), int(end_ms))
        df = merge_funding(df, fund, uptime_col="open_time")
        df = add_indicators(df)
        df["atr_sma50"] = df["atr_pct"].rolling(50).mean()
        df["k_mid"] = df["close"].ewm(span=20, adjust=False).mean()
        df["k_up"] = df["k_mid"] + df["atr"] * KELT["mult"]
        df["k_lo"] = df["k_mid"] - df["atr"] * KELT["mult"]
        return df

    def step_candle(self, dfs, sym, i, ts):
        df = dfs[sym]
        for pos in [p for p in self.st["positions"] if p["symbol"] == sym]:
            if i > pos["last_i"]:
                pos["last_i"] = i
                self.charge_funding(pos, df, i, ts)
                self.manage_exit(pos, df, i, ts)
        if not any(p["symbol"] == sym for p in self.st["positions"]):
            for strat in ("DON", "KELT"):
                if any(p["symbol"] == sym for p in self.st["positions"]):
                    continue
                direction, atr_entry = self.entry_pair(df, i, strat)
                if direction != 0:
                    self.open_position(ts, strat, sym, df, i, direction, atr_entry)


def run_live(symbols, horizon_days=75, fresh=False):
    """Chạy scan một lần (nến H4 đã đóng). Trả về text tóm tắt dạng Markdown."""
    end = int(time.time() * 1000)
    end = end - (end % H4)
    start = end - horizon_days * 24 * 3600 * 1000
    print(f"Fetch {len(symbols)} symbols, nến H4 khép tới móc {pd.Timestamp(end, unit='ms', tz='UTC')}", flush=True)
    st = load_state()
    dfs, ok = {}, 0
    for sym in symbols:
        try:
            lot = PaperLot(st, [sym])
            d = lot.prepare(sym, start, end)
            if d is not None:
                dfs[sym] = d; ok += 1
        except Exception as e:
            print(f"  [warn] {sym}: {e}", flush=True)
        time.sleep(0.15)
    print(f"OK {ok}/{len(symbols)}", flush=True)
    if not dfs:
        print("Không có dữ liệu.")
        return None
    cursor = st.get("cursor") or start
    if fresh and st.get("cursor") is None:
        cursor = end
    lot = PaperLot(st, list(dfs))
    times = sorted({int(t) for sym in dfs for t in dfs[sym]["open_time"].tolist() if cursor <= t < end})
    for ts in times:
        for sym in list(dfs):
            arr = dfs[sym]["open_time"].to_numpy()
            hits = np.where((arr == ts))[0]
            if len(hits):
                lot.step_candle(dfs, sym, int(hits[0]), ts)
        if ts % (24 * 3600 * 1000) == 0:
            lot.snapshot(ts, "day")
            st["day_start_eq"] = st["equity"]
    st["cursor"] = end
    st["last_ts"] = end
    save_state(st)
    lot.snapshot(end, "scan")
    ts_label = pd.Timestamp(end, unit="ms", tz="UTC").strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"📈 *FUTURES ÁO* | Scan `{ts_label}` | Mode `{_cfg('MODE', 'PAPER')}`",
             "=" * 28,
             f"Equity: *${st['equity']:,.2f}* ({(st['equity']/EQUITY0-1)*100:+.2f}%)  | Peak ${st['peak']:,.2f}",
             f"Vị thế mở: {len(st['positions'])}/{MAX_POS}  | Margin {lot.margin_pct():.0f}% (trần {MAX_MARGIN_PCT*100:.0f}%)",
             f"Lệnh đã đóng: {st['n_trades']}  | Nến xử lý: {len(times)}"]
    for p in st["positions"]:
        side = "🟢 LONG" if p["direction"] == 1 else "🔴 SHORT"
        lines.append(f"  • {p['strategy']} `{p['symbol']}` {side} @ {p['entry_px']:.4f} | notional ${p['notional']:,.0f}")
    for e in lot.log[-8:]:
        if e.startswith(("OPEN@", "CLOSE@")):
            lines.append("  " + e.replace("@", " "))
    return "\n".join(lines)


def scan_futures(notify_tg=True):
    """Cấu phần cho auto_trade.py: chạy scan futures giấy + gửi Telegram.
    Trả về text tóm tắt (để auto_trade có thể gộp vào báo cáo tổng)."""
    if not _cfg("ENABLE_FUTURES_AUTO_TRADE", True):
        print("ENABLE_FUTURES_AUTO_TRADE = False -> bỏ qua futures paper.")
        return None
    symbols = top_universe()
    text = run_live(symbols, fresh=False)
    if text and notify_tg:
        notify(text)
    return text


def run_replay(symbols, months=24, allow_t4=True):
    print(f"REPLAY {len(symbols)} symbols × {months} tháng (validation vs backtest)", flush=True)
    st = default_state()
    lot = PaperLot(st, symbols, replay=True, force=True)
    dfs = {}
    for sym in symbols:
        tag = f"futures_cache/{sym}_{int(months)}m_off0"
        if not os.path.exists(f"{tag}.4h.csv"):
            from research_futures_strategy import download_all as dl
            dl(sym, months, refresh=True)
        df = pd.read_csv(f"{tag}.4h.csv")
        fund = pd.DataFrame()
        try:
            fund = pd.read_csv(f"{tag}.funding.csv")
        except Exception:
            pass
        df = merge_funding(df, fund, uptime_col="open_time")
        df = add_indicators(df)
        df["atr_sma50"] = df["atr_pct"].rolling(50).mean()
        df["k_mid"] = df["close"].ewm(span=20, adjust=False).mean()
        df["k_up"] = df["k_mid"] + df["atr"] * KELT["mult"]
        df["k_lo"] = df["k_mid"] - df["atr"] * KELT["mult"]
        dfs[sym] = df
    start = int(min(df["open_time"].iloc[WARMUP] for df in dfs.values()))
    end = int(max(df["open_time"].iloc[-1] for df in dfs.values()))
    times = sorted({int(t) for sym in dfs for t in dfs[sym]["open_time"].tolist() if start <= t <= end})
    for k, ts in enumerate(times):
        for sym in dfs:
            arr = dfs[sym]["open_time"].to_numpy()
            hits = np.where(arr == ts)[0]
            if len(hits):
                lot.step_candle(dfs, sym, int(hits[0]), ts)
    eq = st["equity"]
    print(f"\nEquity cuối: ${eq:,.0f}  ({(eq/EQUITY0-1)*100:+.1f}%)   peak ${st['peak']:,.0f}")
    print(f"Lệnh đóng: {st['n_trades']}   max margin {lot.margin_pct():.0f}%")
    df = pd.read_csv(REPLAY_TRADES)
    if len(df):
        w = df[df["net_usd"] > 0]; l = df[df["net_usd"] <= 0]
        gp = w["net_usd"].sum(); gl = abs(l["net_usd"].sum())
        pf = gp / gl if gl > 0 else 99
        print(f"WR {len(w)/len(df)*100:.0f}%  PF {pf:.2f}  avg win ${w['net_usd'].mean():+.0f}  avg loss ${l['net_usd'].mean():+.0f}")
        print(df.groupby("strategy")[["net_usd"]].sum().round(0).to_string())
    lot.snapshot(end, "replay-end")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", action="store_true", help="chạy 1 lần scan live (nến H4 đã đóng)")
    ap.add_argument("--replay", action="store_true", help="replay lịch sử từ cache để kiểm chứng")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--months", type=float, default=24)
    ap.add_argument("--nosub", action="store_true", help="chỉ T1+T2+T3 (bỏ T4)")
    ap.add_argument("--force", action="store_true", help="bỏ khoá ngày/tuần")
    ap.add_argument("--fresh", action="store_true", help="bắt đầu paper từ móc nến hiện tại (không backfill)")
    ap.add_argument("--notify", action="store_true", help="gửi Telegram sau khi scan (dùng cho cron)")
    a = ap.parse_args()

    if a.reset:
        for f in (STATE_FILE, TRADES_CSV, EQUITY_CSV, REPLAY_TRADES):
            if os.path.exists(f):
                os.remove(f)
        print("Reset state + logs.")
        return

    if a.status:
        st = load_state()
        mu = sum(p["margin"] for p in st["positions"])
        mp = mu / st["equity"] * 100 if st["equity"] > 0 else 0
        print(f"equity ${st['equity']:,.2f}  peak ${st['peak']:,.2f}  cursor {st['cursor']}  lệnh {st['n_trades']}")
        print(f"n_pos {len(st['positions'])}  margin ${mu:,.0f} = {mp:.0f}% equity  (trần 40%)")
        for p in st["positions"]:
            side = 'LONG' if p['direction'] == 1 else 'SHORT'
            print(f"  {p['strategy']} {p['symbol']} {side} @{p['entry_px']:.4f} trail {p['trail']:.4f} tp {p['tp']:.4f} notional ${p['notional']:,.0f}")
        return

    symbols = CORE_SYMBOLS if a.replay else top_universe(only_t12=a.nosub)
    if a.replay:
        run_replay(symbols, months=a.months)
    else:
        text = scan_futures(notify_tg=a.notify)
        if text:
            print("\n" + text)


if __name__ == "__main__":
    main()