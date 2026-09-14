#!/usr/bin/env python3
"""Chuẩn bị dữ liệu DefiLlama cho crypto early-discovery scan.

Trả về dữ liệu fees + mcap/listedAt từ public API của DefiLlama, tính sẵn các chỉ số
của skill (A1/A2, % doanh thu đời trong 7d, MC÷day) và xuất digest cho LLM đọc.

Lưu ý (2026-09): DefiLlama đã paywall cột "revenue" — public API chỉ còn fees.
Take rate / doanh thu phải ước lượng từ methodolody text trong digest hoặc ghi rõ
dùng phí làm proxy.

Usage:
    python3 crypto_data.py [--top N] [--out-dir reports/crypto]
"""
import argparse
import json
import urllib.request
from datetime import datetime, timezone

FEES_URL = "https://api.llama.fi/overview/fees?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true"
PROTOCOLS_URL = "https://api.llama.fi/protocols"
UA = {"User-Agent": "crypto-early-discovery-scan/1.0"}


def fetch(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except Exception as e:
        return getattr(e, "code", 0), b""


def days_old(listed_at):
    if not listed_at:
        return None
    age = (datetime.now(timezone.utc).timestamp() - listed_at) / 86400
    return max(0.0, age)


def _short(v, n=300):
    if v is None:
        return None
    if isinstance(v, str):
        return v[:n]
    return json.dumps(v, ensure_ascii=False)[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=40)
    ap.add_argument("--out-dir", default="reports/crypto")
    args = ap.parse_args()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    fs, fraw = fetch(FEES_URL)
    ps, praw = fetch(PROTOCOLS_URL)

    sources = {
        "fees_overview": {"url": FEES_URL, "http": fs},
        "protocols": {"url": PROTOCOLS_URL, "http": ps},
    }

    fees_data, protos_data = {}, []
    if fs == 200:
        fees_data = json.loads(fraw)
    if ps == 200:
        protos_data = json.loads(praw)

    pid = {p.get("id"): p for p in protos_data}

    rows = []
    for f in fees_data.get("protocols", []):
        p = pid.get(f.get("defillamaId")) or {}
        fee24h = f.get("total24h")
        fee7d = f.get("total7d")
        fee30d = f.get("total30d")
        fee_cum = f.get("totalAllTime")
        chg1m = f.get("change_1m")
        listed_at = p.get("listedAt") or f.get("listedAt")
        mcap = p.get("mcap")
        rows.append({
            "name": f.get("name"),
            "slug": f.get("slug"),
            "symbol": p.get("symbol"),
            "category": f.get("category"),
            "chains": f.get("chains"),
            "fee24h": fee24h,
            "fee7d": fee7d,
            "fee30d": fee30d,
            "feeCumulative": fee_cum,
            "change1m": chg1m,
            "ageDays": days_old(listed_at),
            "listedAt": listed_at,
            "mcap": mcap,
            "mcDivFeeDay": (mcap / fee24h) if (mcap and fee24h) else None,
            "pctLifeIn7d": (fee7d / fee_cum * 100) if (fee7d and fee_cum) else None,
            "methodology": _short(f.get("methodology")),
        })

    def has(x, k):
        v = x.get(k)
        return v is not None and v > 0

    # Kênh A1: protocol < 90 ngày trong top 20 fee24h
    by_day = sorted([r for r in rows if has(r, "fee24h")], key=lambda r: -r["fee24h"])
    top20_names = {r["name"] for r in by_day[:20]}
    a1 = [r for r in by_day if (r.get("ageDays") is not None and r["ageDays"] < 90
                                 and r["name"] in top20_names)]

    # Kênh A2: change_1m > 50 và fee30d > $250K (mọi độ tuổi)
    a2 = [r for r in rows if (r.get("change1m") is not None and r["change1m"] > 50
                               and r.get("fee30d") is not None and r["fee30d"] > 250_000)]
    a2.sort(key=lambda r: -r["fee30d"])

    top = by_day[: args.top]

    def fmt_usd(v):
        if v is None:
            return "-"
        if v >= 1e6:
            return f"${v/1e6:.2f}M"
        if v >= 1e3:
            return f"${v/1e3:.1f}K"
        return f"${v:.0f}"

    def fmt_pct(v):
        return "-" if v is None else f"{v:.1f}%"

    def fmt_age(v):
        return "-" if v is None else f"{v:.0f}d"

    def fmt_x(v):
        return "-" if v is None else f"{v:.0f}x"

    lines = []
    lines.append(f"# DefiLlama data — {today}")
    lines.append(f"fetched_at={datetime.now(timezone.utc).isoformat()}")
    lines.append(f"sources={json.dumps(sources)}")
    lines.append("Ghi chú: public API không trả 'revenue' (đã paywall). Cột doanh thu dùng "
                 "fee làm proxy; take rate thật phải ước lượng từ 'methodology' trong JSON.")
    lines.append("")

    for title, items in [("## A1 — trẻ <90d trong top-20 fee24h", a1),
                         ("## A2 — change_1m > 50% & fee30d > $250K (mọi độ tuổi)", a2),
                         (f"## Top {args.top} theo fee24h", top)]:
        lines.append(title)
        lines.append("| protocol | chains | cat | fee24h | fee7d | fee30d | cum | age | mcap | mc/fee24h | %cum trong 7d | chg1m |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in items:
            lines.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                r["name"], ",".join(r["chains"] or ["-"])[:20] or "-", r["category"],
                fmt_usd(r["fee24h"]), fmt_usd(r["fee7d"]), fmt_usd(r["fee30d"]),
                fmt_usd(r["feeCumulative"]), fmt_age(r["ageDays"]),
                fmt_usd(r["mcap"]), fmt_x(r["mcDivFeeDay"]),
                fmt_pct(r["pctLifeIn7d"]), fmt_pct(r["change1m"] if r.get("change1m") is not None else None)))
        lines.append("")

    digest_md = "\n".join(lines)
    print(digest_md)

    import os
    out_dir = args.out_dir
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, f"_data_{today}")
    with open(f"{base}.md", "w") as fh:
        fh.write(digest_md)
    with open(f"{base}.json", "w") as fh:
        json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(),
                   "sources": sources,
                   "a1": [r for r in a1],
                   "a2": [r for r in a2],
                   "top": top}, fh, indent=1, ensure_ascii=False, default=str)

    print(f"\nWrote: {base}.md / {base}.json")


if __name__ == "__main__":
    main()