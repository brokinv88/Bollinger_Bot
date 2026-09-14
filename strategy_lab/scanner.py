"""Read-only Binance screener for the frozen research rules in SPEC.md.

Run from the repository root: python -m strategy_lab.scanner --limit 100
No authenticated API endpoints, order submission, or messaging are implemented.
"""

from __future__ import annotations

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_UP
import json
import math
from pathlib import Path
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from .signals import features


INTERVAL_MS = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
FIXED_COHORT = {
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT",
    "LINKUSDT", "LTCUSDT", "BCHUSDT", "DOTUSDT", "UNIUSDT", "SOLUSDT",
}
# Explicit exclusion list, reviewed by the user rather than inferred from returns.
STABLE_OR_PEGGED = {
    "USDT", "USDC", "FDUSD", "TUSD", "USDP", "BUSD", "DAI", "USDD", "USDE",
    "USD1", "USD0", "USDG", "USDJ", "USDS", "USDX", "USDF", "PYUSD", "RLUSD",
    "FRAX", "LUSD", "SUSD", "UST", "USTC", "EUR", "EURI", "AEUR", "EURC",
    "BRL", "TRY", "GBP", "AUD", "BIDR", "IDRT", "VAI", "XAUT", "PAXG",
    "WBTC", "WBETH", "WSTETH", "STETH", "BETH", "BTCB", "CBETH", "CBBTC",
}
LEVERAGED_BASES = {
    "BTCUP", "BTCDOWN", "ETHUP", "ETHDOWN", "BNBUP", "BNBDOWN", "ADAUP",
    "ADADOWN", "DOTUP", "DOTDOWN", "LINKUP", "LINKDOWN", "XRPUP", "XRPDOWN",
    "TRXUP", "TRXDOWN", "EOSUP", "EOSDOWN", "LTCUP", "LTCDOWN", "UNIUP",
    "UNIDOWN", "SUSHIUP", "SUSHIDOWN", "FILUP", "FILDOWN", "AAVEUP", "AAVEDOWN",
    "YFIUP", "YFIDOWN", "SXPUP", "SXPDOWN", "XTZUP", "XTZDOWN",
}
DEFAULT_ACCOUNT = {
    "spot_equity": 3000.0, "spot_peak_equity": 3000.0,
    "futures_equity": 1000.0, "futures_peak_equity": 1000.0,
    "reserve": 1000.0, "positions": [],
}


def utc_iso(ms: int | float) -> str:
    return datetime.fromtimestamp(float(ms) / 1000, timezone.utc).isoformat(timespec="seconds")


def finite(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


class InsufficientHistory(ValueError):
    """A new instrument does not yet have enough fully closed candles."""


class PublicBinance:
    """Public GET endpoints only, with one shared request pacing clock."""

    def __init__(self, minimum_request_gap: float = 0.12):
        self.lock = threading.Lock()
        self.last_request = 0.0
        self.minimum_request_gap = minimum_request_gap
        self.rate_limited = threading.Event()

    def get(self, market: str, endpoint: str, **params: Any) -> Any:
        if market not in {"spot", "futures"}:
            raise ValueError("Unsupported market")
        allowed = {"time", "exchangeInfo", "ticker/24hr", "klines"}
        if endpoint not in allowed:
            raise ValueError("Only read-only public market endpoints are permitted")
        host = "https://api.binance.com/api/v3" if market == "spot" else "https://fapi.binance.com/fapi/v1"
        url = f"{host}/{endpoint}"
        if params:
            url += "?" + urlencode(params)
        for attempt in range(3):
            with self.lock:
                if self.rate_limited.is_set():
                    raise RuntimeError("Binance rate limit encountered; remaining requests cancelled")
                pause = self.minimum_request_gap - (time.monotonic() - self.last_request)
                if pause > 0:
                    time.sleep(pause)
                self.last_request = time.monotonic()
            try:
                request = Request(url, headers={"User-Agent": "strategy-lab-readonly/1.0"})
                with urlopen(request, timeout=25) as response:
                    return json.load(response)
            except HTTPError as exc:
                if exc.code in {418, 429}:
                    # Do not hammer Binance after a rate limit or temporary ban.
                    self.rate_limited.set()
                    raise RuntimeError(f"Binance HTTP {exc.code}; stop and retry later") from exc
                if exc.code < 500 or attempt == 2:
                    raise RuntimeError(f"Binance public {market}/{endpoint}: HTTP {exc.code}") from exc
            except (URLError, TimeoutError, OSError) as exc:
                if attempt == 2:
                    raise RuntimeError(f"Binance public {market}/{endpoint}: {exc}") from exc
            time.sleep(0.5 * (attempt + 1))
        raise RuntimeError("Unreachable request state")

    def bars(self, market: str, symbol: str, interval: str, limit: int, asof_ms: int) -> pd.DataFrame:
        raw = self.get(market, "klines", symbol=symbol, interval=interval, limit=min(limit + 1, 1000), endTime=asof_ms)
        return closed_bars(raw, interval, asof_ms, keep=limit)


def closed_bars(raw: list, interval: str, asof_ms: int, keep: int | None = None) -> pd.DataFrame:
    """Reject stale/gapped series; strictly remove the current incomplete candle."""
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"No {interval} candle data")
    records = []
    duration = INTERVAL_MS[interval]
    for row in raw:
        if not isinstance(row, list) or len(row) < 8:
            raise ValueError("Malformed Binance kline")
        records.append({"open_time": int(row[0]), "open": float(row[1]), "high": float(row[2]),
                        "low": float(row[3]), "close": float(row[4]), "volume": float(row[5]), "quote_vol": float(row[7]),
                        "close_time": int(row[6])})
    bars = pd.DataFrame(records)
    bars = bars.loc[bars.close_time < asof_ms].sort_values("open_time").reset_index(drop=True)
    if keep:
        bars = bars.tail(keep).reset_index(drop=True)
    if bars.empty:
        raise InsufficientHistory(f"No fully closed {interval} candles")
    if bars.open_time.duplicated().any():
        raise ValueError(f"Duplicate {interval} candles")
    expected_open = (asof_ms // duration - 1) * duration
    if int(bars.iloc[-1].open_time) != expected_open:
        raise ValueError(f"Stale {interval} candles: expected {utc_iso(expected_open)}")
    if len(bars) > 1 and not bars.open_time.diff().iloc[1:].eq(duration).all():
        raise ValueError(f"Missing {interval} candles")
    if not (bars.close_time == bars.open_time + duration - 1).all():
        raise ValueError(f"Invalid {interval} candle close times")
    values = bars[["open", "high", "low", "close", "quote_vol"]]
    if not all(math.isfinite(float(v)) for v in values.to_numpy().ravel()):
        raise ValueError("Nonfinite market data")
    if (bars[["open", "high", "low", "close"]] <= 0).any().any() or (bars.quote_vol < 0).any():
        raise ValueError("Invalid market prices or volume")
    if ((bars.high < bars[["open", "close", "low"]].max(axis=1)) |
            (bars.low > bars[["open", "close", "high"]].min(axis=1))).any():
        raise ValueError("Invalid OHLC range")
    return bars


def pick_universe(exchange: dict, tickers: list, market: str, limit: int) -> list[dict]:
    """Today's liquid cohort; deliberately makes no historical-selection claim."""
    ticker_by_symbol = {row["symbol"]: row for row in tickers if isinstance(row, dict) and "symbol" in row}
    chosen = []
    for item in exchange.get("symbols", []):
        symbol, base = item.get("symbol", ""), item.get("baseAsset", "")
        if item.get("status") != "TRADING" or item.get("quoteAsset") != "USDT":
            continue
        if base in STABLE_OR_PEGGED or base in LEVERAGED_BASES or base.endswith(("BULL", "BEAR")):
            continue
        if market == "spot" and item.get("isSpotTradingAllowed") is not True:
            continue
        if market == "futures" and (item.get("contractType") != "PERPETUAL" or item.get("marginAsset") != "USDT"):
            continue
        volume = finite(ticker_by_symbol.get(symbol, {}).get("quoteVolume"), 0.0)
        if volume is None or volume <= 0:
            continue
        chosen.append({**item, "quote_volume_24h": volume})
    chosen.sort(key=lambda row: (-row["quote_volume_24h"], row["symbol"]))
    return chosen[:limit]


def load_account(path: Path | None) -> dict:
    account = json.loads(json.dumps(DEFAULT_ACCOUNT))
    if path is not None:
        supplied = json.loads(path.read_text())
        if not isinstance(supplied, dict):
            raise ValueError("Account JSON must be an object")
        required = {"spot_equity", "spot_peak_equity", "futures_equity", "futures_peak_equity", "reserve", "positions"}
        if not required.issubset(supplied):
            raise ValueError(f"Account JSON requires {sorted(required)}")
        account.update(supplied)
    for market in ("spot", "futures"):
        equity, peak = finite(account[f"{market}_equity"]), finite(account[f"{market}_peak_equity"])
        if equity is None or peak is None or equity <= 0 or peak < equity:
            raise ValueError(f"Invalid {market} equity/peak")
        account[f"{market}_equity"], account[f"{market}_peak_equity"] = equity, peak
    if finite(account["reserve"]) is None or float(account["reserve"]) < 0:
        raise ValueError("Invalid reserve")
    if not isinstance(account["positions"], list):
        raise ValueError("positions must be a list")
    for position in account["positions"]:
        if not isinstance(position, dict):
            raise ValueError("Every position must be an object")
        if position.get("market") not in {"spot", "futures"} or position.get("side") not in {"long", "short"}:
            raise ValueError("Every position needs market and side")
        if not isinstance(position.get("symbol"), str) or not position["symbol"]:
            raise ValueError("Every position needs a symbol")
        if position["market"] == "spot" and position["side"] != "long":
            raise ValueError("Spot sleeve is long only")
        for field in ("initial_risk_usdt", "notional_usdt"):
            value = finite(position.get(field))
            if value is None or value < 0:
                raise ValueError(f"Position {field} must be a nonnegative number")
            position[field] = value
    account["state_supplied"] = path is not None
    return account


def load_narratives(path: Path | None) -> dict[str, list[str]]:
    if path is None:
        return {}
    raw = json.loads(path.read_text())
    mapping = raw.get("symbols", raw)
    if not isinstance(mapping, dict):
        raise ValueError("Narrative JSON requires a symbols object")
    result = {}
    for symbol, tags in mapping.items():
        if not isinstance(symbol, str) or not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            raise ValueError("Narratives must map symbol strings to lists of text tags")
        result[symbol.upper()] = sorted({t.strip() for t in tags if t.strip()})
    return result


def decimal_lcm(steps: list[Decimal]) -> Decimal:
    steps = [step for step in steps if step > 0]
    if not steps:
        raise ValueError("No valid quantity step in exchange filters")
    places = max(max(0, -step.as_tuple().exponent) for step in steps)
    scale = Decimal(10) ** places
    units = [int(step * scale) for step in steps]
    return Decimal(math.lcm(*units)) / scale


def live_quantity(quantity: float, reference_price: float, filters: list[dict]) -> dict:
    """Round down to the intersection of current lot filters, enforcing minima."""
    lots = [row for row in filters if row.get("filterType") in {"LOT_SIZE", "MARKET_LOT_SIZE"}]
    steps = [Decimal(str(row.get("stepSize", "0"))) for row in lots]
    step = decimal_lcm(steps)
    qty = (Decimal(str(max(0.0, quantity))) / step).to_integral_value(rounding=ROUND_DOWN) * step
    min_qty = max([Decimal(str(row.get("minQty", "0"))) for row in lots] + [Decimal(0)])
    max_qtys = [Decimal(str(row.get("maxQty", "0"))) for row in lots if Decimal(str(row.get("maxQty", "0"))) > 0]
    if max_qtys and qty > min(max_qtys):
        qty = (min(max_qtys) / step).to_integral_value(rounding=ROUND_DOWN) * step
    minimum_notional = Decimal(0)
    maximum_notionals = []
    for row in filters:
        if row.get("filterType") == "MIN_NOTIONAL":
            minimum_notional = max(minimum_notional, Decimal(str(row.get("minNotional", row.get("notional", "0")))))
        if row.get("filterType") == "NOTIONAL":
            minimum_notional = max(minimum_notional, Decimal(str(row.get("minNotional", "0"))))
            maximum = Decimal(str(row.get("maxNotional", "0")))
            if maximum > 0:
                maximum_notionals.append(maximum)
    price = Decimal(str(reference_price))
    if maximum_notionals and qty * price > min(maximum_notionals):
        qty = (min(maximum_notionals) / price / step).to_integral_value(rounding=ROUND_DOWN) * step
    ok = qty > 0 and qty >= min_qty and qty * price >= minimum_notional
    return {"quantity": float(qty) if ok else 0.0, "quantity_text": format(qty, "f") if ok else "0",
            "quantity_step": str(step), "min_notional": float(minimum_notional),
            "size_status": "HYPOTHETICAL_ONLY" if ok else "BELOW_EXCHANGE_MINIMUM"}


def reference_size(row: dict, metadata: dict, account: dict, narratives: dict) -> dict:
    """Informational sizing only: actual next open and account balances are unknown."""
    market = row["market"]
    equity = account[f"{market}_equity"]
    drawdown = 1 - equity / account[f"{market}_peak_equity"]
    risk_fraction = 20 / 3000 if market == "spot" else 12.5 / 1000
    reduction = 0.5 if drawdown >= 0.08 - 1e-12 else 1.0
    positions = [p for p in account["positions"] if p["market"] == market]
    risk_used = sum(p["initial_risk_usdt"] for p in positions)
    total_equity = account["spot_equity"] + account["futures_equity"] + float(account["reserve"])
    side = "long" if row.get("signal", 0) >= 0 else "short"
    tags = set(narratives.get(row["symbol"], []))
    # Shared tags OR the same asset across sleeves count as correlated exposures.
    correlated = [p for p in account["positions"] if p["side"] == side and
                  (p["symbol"] == row["symbol"] or tags.intersection(narratives.get(p["symbol"], [])))]
    correlated_risk = sum(p["initial_risk_usdt"] for p in correlated)
    group_available = max(0.0, total_equity * 0.0075 - correlated_risk)
    risk_available = min(max(0.0, equity * 0.02 * reduction - risk_used), group_available)
    risk_budget = equity * risk_fraction * reduction
    notional_used = sum(p["notional_usdt"] for p in positions)
    cap = min(equity * 0.25 * reduction, max(0.0, equity - notional_used)) if market == "spot" else min(equity * reduction, max(0.0, 2 * equity - notional_used))
    blocked = ""
    if drawdown >= 0.12 - 1e-12 or account.get(f"{market}_halted", False):
        blocked = "DRAWDOWN_FREEZE"
    elif len(positions) >= (4 if market == "spot" else 2):
        blocked = "POSITION_LIMIT"
    elif any(p["symbol"] == row["symbol"] for p in positions):
        blocked = "ALREADY_OPEN_NO_PYRAMIDING"
    elif risk_available + 1e-8 < risk_budget or risk_budget <= 0 or cap <= 0:
        blocked = "NO_RISK_OR_CAPITAL_CAPACITY"
    result = {"sleeve_equity_usdt": equity, "sleeve_drawdown_pct": drawdown * 100,
              "risk_budget_usdt": risk_budget, "available_sleeve_risk_usdt": risk_available,
              "account_state": "USER_SUPPLIED_UNVERIFIED" if account["state_supplied"] else "DEFAULT_EMPTY_HYPOTHETICAL",
              "quantity": 0.0, "quantity_text": "0", "size_status": blocked or "NO_SIGNAL",
              "reference_entry": None, "reference_stop": None, "reference_target": None,
              "reference_notional_usdt": 0.0, "reference_margin_usdt": 0.0,
              "estimated_initial_risk_usdt": 0.0}
    if blocked or not row.get("signal"):
        return result
    close, atr = finite(row.get("close")), finite(row.get("atr"))
    if close is None or atr is None or close <= 0 or atr <= 0:
        result["size_status"] = "INVALID_REFERENCE_PRICE_OR_ATR"
        return result
    direction = 1 if row["signal"] > 0 else -1
    fee, slip = (0.001, 0.0005) if market == "spot" else (0.0005, 0.0003)
    entry = close * (1 + direction * slip)
    stop = entry - direction * 2 * atr
    target = entry + direction * 6 * atr
    if stop <= 0 or target <= 0:
        result["size_status"] = "INVALID_REFERENCE_STOP_OR_TARGET"
        return result
    # Round stop away from entry; this is conservative for the risk estimate.
    ticks = [Decimal(str(f["tickSize"])) for f in metadata.get("filters", [])
             if f.get("filterType") == "PRICE_FILTER" and finite(f.get("tickSize"), 0) > 0]
    if ticks:
        tick = max(ticks)
        rounding = ROUND_DOWN if direction > 0 else ROUND_UP
        stop = float((Decimal(str(stop)) / tick).to_integral_value(rounding=rounding) * tick)
        target_rounding = ROUND_DOWN if direction > 0 else ROUND_UP
        target = float((Decimal(str(target)) / tick).to_integral_value(rounding=target_rounding) * tick)
    if stop <= 0 or target <= 0:
        result["size_status"] = "INVALID_ROUNDED_STOP_OR_TARGET"
        return result
    stop_fill = stop * (1 - direction * slip)
    loss_per_unit = direction * (entry - stop_fill) + fee * (entry + stop_fill)
    # Reserve entry fee inside both spot cash and notional capacity.
    quantity = min(risk_budget / loss_per_unit, cap / (entry * (1 + fee)))
    rounded = live_quantity(quantity, entry, metadata.get("filters", []))
    qty = rounded["quantity"]
    result.update(rounded)
    result.update({"reference_entry": entry, "reference_stop": stop, "reference_target": target,
                   "reference_notional_usdt": qty * entry,
                   "reference_margin_usdt": qty * entry if market == "spot" else qty * entry / 3,
                   "estimated_initial_risk_usdt": qty * loss_per_unit})
    return result


def scan_symbol(client: PublicBinance, metadata: dict, market: str, asof_ms: int,
                btc_daily: pd.DataFrame | None, narratives: dict) -> dict:
    symbol = metadata["symbol"]
    row = {"market": market, "symbol": symbol, "base_asset": metadata["baseAsset"],
           "setup": "SPOT_D1_H4_BREAKOUT" if market == "spot" else "FUTURES_H4_H1_PULLBACK",
           "validation_status": "EXPANDED_UNVALIDATED", "in_fixed_research_cohort": symbol in FIXED_COHORT,
           "narratives": narratives.get(symbol, []), "quote_volume_24h": metadata["quote_volume_24h"],
           "asof_utc": utc_iso(asof_ms), "status": "DATA_ERROR", "signal": 0, "eligible": False}
    try:
        interval = "4h" if market == "spot" else "1h"
        execution = client.bars(market, symbol, interval, 240, asof_ms)
        higher = client.bars(market, symbol, "1d" if market == "spot" else "4h", 999, asof_ms)
        daily = higher if market == "spot" else client.bars(market, symbol, "1d", 40, asof_ms)
        if len(execution) < 200 or len(higher) < 200 or len(daily) < 30:
            row.update(status="INSUFFICIENT_HISTORY", reason="Need 200 execution/HTF and 30 daily closed candles")
            return row
        enriched = features(execution, market, higher_bars=higher, daily_bars=daily,
                            btc_daily=btc_daily, symbol=symbol)
        latest = enriched.iloc[-1]
        next_open = int(execution.iloc[-1].close_time) + 1
        age_seconds = max(0.0, (asof_ms - next_open) / 1000)
        signal = int(latest["signal"])
        eligible = bool(latest.get("eligible", False)) and (market == "spot" or int(latest.get("trend", 0)) != 0)
        status = "EXPIRED_SIGNAL" if signal and age_seconds > 60 else "SETUP" if signal else "WATCH" if eligible else "FILTERED_OUT"
        row.update({"status": status, "signal": signal, "side": "long" if signal > 0 or (eligible and int(latest.get("trend",0))>0) else "short" if signal < 0 or (eligible and int(latest.get("trend",0))<0) else "none",
                    "eligible": eligible, "signal_candle_open_utc": utc_iso(int(execution.iloc[-1].open_time)),
                    "signal_candle_close_utc": utc_iso(next_open - 1), "model_next_open_utc": utc_iso(next_open),
                    "signal_age_seconds": age_seconds, "execution_interval": interval,
                    "close": float(execution.iloc[-1].close), "atr": finite(latest.get("atr")),
                    "daily_liquidity": finite(latest.get("daily_liquidity")),
                    "htf_close": finite(latest.get("htf_close")), "htf_ema50": finite(latest.get("htf_ema50")),
                    "htf_ema200": finite(latest.get("htf_ema200")), "trend": int(latest.get("trend", 0)),
                    "daily_roc20": finite(latest.get("daily_roc20")), "btc_roc20": finite(latest.get("btc_roc20")),
                    "reason": "Historical latest-close signal; model entry time passed, do not chase" if status == "EXPIRED_SIGNAL" else
                    "Signal at latest closed candle; recompute size using actual fill, verify price and positions" if status == "SETUP" else
                    "Filters pass; no trigger on latest closed candle" if status == "WATCH" else
                    "Trend / relative-strength / confirmed liquidity filter not met"})
    except InsufficientHistory as exc:
        row.update(status="INSUFFICIENT_HISTORY", signal=0, eligible=False, reason=str(exc))
    except Exception as exc:
        row.update(status="DATA_ERROR", signal=0, eligible=False, reason=f"{type(exc).__name__}: {exc}")
    return row


def assign_capacity(rows: list[dict], metadata_by_key: dict, account: dict, narratives: dict) -> list[dict]:
    """Reserve risk for SETUP rows in priority order; never reserve expired signals."""
    simulated = json.loads(json.dumps(account))
    for row in rows:
        if row["status"] in {"DATA_ERROR", "INSUFFICIENT_HISTORY"}:
            row.update(quantity=0.0, quantity_text="0", size_status="NO_VALID_DATA", capacity_reserved=False)
            continue
        sizing = reference_size(row, metadata_by_key[(row["market"], row["symbol"])], simulated, narratives)
        row.update(sizing)
        reserve = (row["status"] == "SETUP" and sizing["quantity"] > 0)
        row["capacity_reserved"] = reserve
        if reserve:
            simulated["positions"].append({"market": row["market"], "symbol": row["symbol"],
                                          "side": row["side"], "initial_risk_usdt": row["estimated_initial_risk_usdt"],
                                          "notional_usdt": row["reference_notional_usdt"]})
        elif row["status"] == "EXPIRED_SIGNAL" and row["size_status"] == "HYPOTHETICAL_ONLY":
            row["size_status"] = "EXPIRED_REFERENCE_DO_NOT_ENTER"
    return rows


def write_reports(output: Path, report: dict) -> None:
    output.mkdir(parents=True, exist_ok=True)
    rows = report["rows"]
    (output / "scan.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with (output / "scan.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns or ["market", "symbol", "status"])
        writer.writeheader()
        writer.writerows({k: ";".join(v) if isinstance(v, list) else v for k, v in row.items()} for row in rows)
    valid = [r for r in rows if r["status"] in {"WATCH", "SETUP", "EXPIRED_SIGNAL"}]
    for market in ("spot", "futures"):
        symbols = [f"BINANCE:{r['symbol']}{'.P' if market == 'futures' else ''}" for r in valid if r["market"] == market]
        (output / f"tradingview_{market}.txt").write_text(",".join(symbols) + ("\n" if symbols else ""))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    lines = ["# Danh sách Binance hằng ngày — chỉ đọc", "", f"Thời điểm quét: **{report['generated_at_utc']}** (UTC).", "",
             "**EXPANDED_UNVALIDATED**: danh sách top thanh khoản hiện tại chưa được kiểm chứng lịch sử như một danh mục. "
             "Kết quả nghiên cứu trên 12 coin cố định không chứng minh lợi thế của top 100 hoặc narrative.", "",
             "**Kiểm định setup:** " + "; ".join(f"{market} = {entry.get('status','NOT_EVALUATED')} ({', '.join(entry.get('failed_checks',[])) or 'xem báo cáo'})" for market,entry in report.get("setup_validation",{}).items()) + ". Xem báo cáo backtest trước khi đánh giá tín hiệu.", "",
             "SETUP chỉ có nghĩa là nến đã đóng tạo tín hiệu; không có lệnh được gửi. EXPIRED_SIGNAL là tín hiệu có thời điểm "
             "vào theo mô hình đã qua hơn 60 giây: không dùng bảng này để đuổi giá. WATCH là đạt bộ lọc nhưng chưa có trigger.", "",
             f"Trạng thái dữ liệu: **{report['run_status']}**. Số lượng: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) + ".", "",
             "Giá vào/stop/target và khối lượng chỉ là ví dụ tính từ giá đóng nến, gồm giả định phí/trượt giá; phải tính lại tại giá "
             "khớp thực tế. Các tín hiệu hết hạn không được giữ chỗ rủi ro. Thứ tự ưu tiên: median doanh số ngày đã xác nhận, rồi symbol.", "",
             "Tài khoản: " + ("đã đọc file trạng thái do người dùng cung cấp; chưa đối chiếu Binance." if report["account"]["state_supplied"] else
                              "chưa cung cấp trạng thái; mặc định giả định spot 3.000, futures 1.000, dự phòng 1.000 USDT và không có vị thế. Khối lượng chỉ minh họa."), "",
             "## Coin đạt bộ lọc", "", "| Thị trường | Coin | Trạng thái | Hướng | Median ngày (USDT) | Giờ vào mô hình UTC | Khối lượng tham khảo | Trạng thái size |",
             "|---|---|---|---|---:|---|---:|---|"]
    for row in valid:
        liquidity = row.get("daily_liquidity") or 0
        lines.append(f"| {row['market']} | {row['symbol']} | {row['status']} | {row['side']} | {liquidity:,.0f} | "
                     f"{row.get('model_next_open_utc', '')} | {row.get('quantity_text', '0')} | {row.get('size_status', '')} |")
    if not valid:
        lines.append("| — | Không có coin đạt bộ lọc | — | — | — | — | — | — |")
    problems = report.get("errors", []) + [f"{r['market']} {r['symbol']}: {r.get('reason', '')}" for r in rows if r["status"] == "DATA_ERROR"]
    if problems:
        lines.extend(["", "## Lỗi dữ liệu — không đưa ra tín hiệu cho các mục này", ""] + [f"- {p}" for p in problems])
    lines.extend(["", "## Cách đọc", "", "- FILTERED_OUT: chưa đạt bộ lọc xu hướng, sức mạnh hoặc thanh khoản; xem đầy đủ trong CSV/JSON.",
                  "- INSUFFICIENT_HISTORY: chưa đủ dữ liệu; token mới không được lách điều kiện lịch sử.",
                  "- Giữ chỗ rủi ro chỉ là mô phỏng trên các SETUP trong lần quét này, không biết các thay đổi tài khoản sau thời điểm nhập.",
                  "- Narrative là nhãn nhập thủ công, không phải dữ liệu đang thịnh hành. Không có bộ lọc market cap vì Binance không cung cấp market cap trong các endpoint này.",
                  "- Tổng khối lượng futures dùng 3× để minh họa ký quỹ. Funding chưa biết trong tương lai không được tính vào ngân sách stop; quản lý riêng khi giữ vị thế.",
                  "- Quét ngày có thể bỏ lỡ trigger H1/H4; dùng Pine alerts khi nến đóng để theo dõi giữa các lần quét.",
                  "- Tệp tradingview_spot.txt / tradingview_futures.txt gồm coin đạt bộ lọc để nhập vào watchlist; tính năng nhập tùy gói TradingView.", ""])
    (output / "scan_vi.md").write_text("\n".join(lines))


def run_scan(args: argparse.Namespace, client: PublicBinance | None = None) -> dict:
    client = client or PublicBinance()
    account = load_account(args.account)
    narratives = load_narratives(args.narratives)
    markets = ["spot", "futures"] if args.market == "both" else [args.market]
    rows, errors, metadata_by_key, clocks, universes = [], [], {}, {}, {}
    btc_daily = None
    for market in markets:
        try:
            server_ms = int(client.get(market, "time")["serverTime"])
            local_ms = int(time.time() * 1000)
            if abs(server_ms - local_ms) > 30_000:
                raise ValueError("Server/local clock mismatch >30 sec; refusing potentially stale signals")
            # Freeze to the server time for each market; no partially completed bar can enter.
            clocks[market] = {"server_utc": utc_iso(server_ms), "offset_ms": server_ms - local_ms}
            exchange = client.get(market, "exchangeInfo")
            tickers = client.get(market, "ticker/24hr")
            universe = pick_universe(exchange, tickers, market, args.limit)
            if not universe:
                raise ValueError("No eligible live instruments from exchangeInfo + 24h ticker")
            universes[market] = [r["symbol"] for r in universe]
            if market == "spot":
                btc_daily = client.bars("spot", "BTCUSDT", "1d", 999, server_ms)
                if len(btc_daily) < 200:
                    raise ValueError("Insufficient BTC daily history")
            for item in universe:
                metadata_by_key[(market, item["symbol"])] = item
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {pool.submit(scan_symbol, client, item, market, server_ms, btc_daily if market == "spot" else None, narratives): item
                           for item in universe}
                for pending in as_completed(futures):
                    rows.append(pending.result())
            print(f"Scanned {market}: {len(universe)} instruments", flush=True)
        except Exception as exc:
            errors.append(f"{market}: {type(exc).__name__}: {exc}")
    result_path=Path(__file__).resolve().parent/'reports'/'metrics.json'
    setup_validation={}
    if result_path.exists():
        try:
            setup_validation=json.loads(result_path.read_text()).get('acceptance',{})
        except (OSError,ValueError):
            setup_validation={}
    for row in rows:
        row['setup_backtest_status']=setup_validation.get(row['market'],{}).get('status','NOT_EVALUATED')
        row['setup_failed_checks']=setup_validation.get(row['market'],{}).get('failed_checks',[])
    # A request batch can cross the next candle boundary. Signals stale at report creation
    # are downgraded, never promoted, and do not reserve capacity.
    finish_ms = int(time.time() * 1000)
    for row in rows:
        if row.get("model_next_open_utc"):
            entry_ms = int(datetime.fromisoformat(row["model_next_open_utc"]).timestamp() * 1000)
            row["signal_age_seconds"] = max(row["signal_age_seconds"], (finish_ms - entry_ms) / 1000)
            if row["status"] == "SETUP" and row["signal_age_seconds"] > 60:
                row["status"] = "EXPIRED_SIGNAL"
                row["reason"] = "Signal entry time expired while scan ran; do not chase"
            duration = INTERVAL_MS[row["execution_interval"]]
            if finish_ms // duration > entry_ms // duration:
                row.update(status="DATA_ERROR", signal=0, eligible=False,
                           reason="Scan crossed the next execution close; rerun for latest closed candle")
    rows.sort(key=lambda r: (-(r.get("daily_liquidity") or 0), r["symbol"], r["market"]))
    rows = assign_capacity(rows, metadata_by_key, account, narratives)
    data_errors = sum(r["status"] == "DATA_ERROR" for r in rows)
    run_status = "FAILED" if not rows else "PARTIAL" if errors or data_errors else "OK"
    return {"generated_at_utc": utc_iso(finish_ms), "run_status": run_status,
            "research_status": "EXPANDED_UNVALIDATED", "setup_validation": setup_validation, "specification": "strategy_lab/SPEC.md v1 2026-09-06",
            "universe_rule": f"Current top {args.limit} eligible USDT instruments by rolling24h quote volume per market; then closed prior-day median30 liquidity and frozen setup filters",
            "no_market_cap_filter": True, "narratives_source": str(args.narratives) if args.narratives else None,
            "server_clocks": clocks, "universes": universes, "account": account, "errors": errors, "rows": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--market", choices=("both", "spot", "futures"), default="both")
    parser.add_argument("--limit", type=int, default=100, help="Top liquid instruments per market, 1–200")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent symbol requests, 1–8; shared pacing remains enforced")
    parser.add_argument("--output-dir", type=Path, default=Path("strategy_lab/reports/daily") / datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ"))
    parser.add_argument("--account", type=Path, help="User supplied sleeve equity, peaks and open positions JSON")
    parser.add_argument("--narratives", type=Path, help="User supplied symbol-to-tags JSON; no auto trending claims")
    args = parser.parse_args()
    if not 1 <= args.limit <= 200 or not 1 <= args.workers <= 8:
        parser.error("--limit must be 1–200 and --workers 1–8")
    try:
        report = run_scan(args)
        write_reports(args.output_dir, report)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Scanner error: {exc}\n")
    print(json.dumps({"run_status": report["run_status"], "rows": len(report["rows"]),
                      "errors": report["errors"], "report": str(args.output_dir / "scan_vi.md")}, ensure_ascii=False), flush=True)
    return 0 if report["run_status"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())
