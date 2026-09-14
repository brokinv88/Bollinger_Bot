#!/usr/bin/env python3
"""Gộp các báo cáo crypto_scan_*.html theo ngày thành 1 dashboard HTML.

Đọc tất cả `reports/crypto/crypto_scan_YYYY-MM-DD.html`, loại bỏ trùng CSS
(dùng style block của report mới nhất), bọc từng ngày thành section riêng, dựng
`index.html` với: tab theo ngày (mặc định ngày mới nhất), xem tất cả, phím mũi tên,
swipe trên mobile, nút prev/next.

Usage:
    python3 crypto_report_index.py [--dir reports/crypto] [--out index.html]
"""
import argparse
import glob
import html
import os
import re
from datetime import datetime

WEEKDAYS = {0: "T2", 1: "T3", 2: "T4", 3: "T5", 4: "T6", 5: "T7", 6: "CN"}

DASH_CSS = """
.dash-top{position:sticky;top:0;z-index:50;background:rgba(11,17,25,.85);
  backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);
  border-bottom:1px solid #242f3d}
.dash-in{max-width:1120px;margin:0 auto;padding:12px 20px}
.dash-head{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.dash-logo{width:34px;height:34px;border-radius:10px;flex:0 0 34px;
  background:linear-gradient(135deg,#58a6ff,#bc8cff);display:flex;align-items:center;justify-content:center;
  font-size:16px;color:#0b1119;font-weight:800}
.dash-title{font-size:16px;font-weight:700;color:#fff;letter-spacing:.2px}
.dash-sub{font-size:12px;color:#8b98a5}
.dash-actions{margin-left:auto;display:flex;gap:8px;align-items:center}
.dbtn{border:1px solid #2a3745;background:#141c26;color:#c9d4de;border-radius:8px;
  padding:5px 11px;font-size:12px;cursor:pointer;transition:.15s}
.dbtn:hover{border-color:#58a6ff;color:#fff}
.dbtn.on{background:linear-gradient(135deg,#58a6ff,#bc8cff);color:#0b1119;border-color:transparent;font-weight:700}
.tabs{display:flex;gap:6px;overflow-x:auto;padding:10px 0 8px;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{flex:0 0 auto;border:1px solid #2a3745;background:#121a24;color:#aab6c2;border-radius:20px;
  padding:5px 13px;font-size:12.5px;cursor:pointer;font-variant-numeric:tabular-nums;transition:.15s;white-space:nowrap}
.tab:hover{border-color:#58a6ff;color:#fff}
.tab.active{background:linear-gradient(135deg,#58a6ff,#bc8cff);color:#0b1119;border-color:transparent;font-weight:700}
.day{display:none}
.day.show{display:block;animation:fadein .25s ease}
@keyframes fadein{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.dash-nav{display:flex;justify-content:center;gap:8px;margin:26px 0 4px}
.dbtn-nav{min-width:96px}
.dash-count{position:absolute;right:14px;top:10px;font-size:11px;color:#5b6775}
.empty{padding:80px 20px;text-align:center;color:#8b98a5;font-size:15px}
body{background:radial-gradient(1100px 560px at 18% -8%,rgba(88,166,255,.10),transparent 58%),
  radial-gradient(900px 500px at 92% -4%,rgba(188,140,255,.09),transparent 55%),#0b1119}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background-image:linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px),
  linear-gradient(90deg,rgba(255,255,255,.018) 1px,transparent 1px);
  background-size:44px 44px}
.wrap{position:relative;z-index:1}
.dash-foot{margin-top:34px}
@media(max-width:640px){.dash-in{padding:10px 14px}.dash-head{gap:10px}}
"""

DASH_JS = """
const YES=()=>1;
const days=[...document.querySelectorAll('.day')].map(s=>s.id);
let cur=days.length-1, mode='day';
const sec=id=>document.getElementById(id);
const tabEl=d=>document.querySelector(`.tab[data-d="${d}"]`);
function setCur(i){if(i<0||i>=days.length)return;sec(days[cur]).classList.remove('show');
  tabEl(days[cur])&&tabEl(days[cur]).classList.remove('active');
  cur=i;render();}
function render(){days.forEach(d=>sec(d).classList.toggle('show',mode==='all'||d===days[cur]));
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',mode==='day'&&t.dataset.d===days[cur]));
  document.querySelector('.dcount')&&(document.querySelector('.dcount').textContent=
    mode==='all'?`${days.length} ngày`:`${cur+1}/${days.length}`);}
function setMode(m){mode=m;document.getElementById('btnAll').classList.toggle('on',m==='all');
  document.getElementById('btnToday').classList.toggle('on',m==='day');render();
  if(m==='all')window.scrollTo({top:0,behavior:'smooth'});else{sec(days[cur])&&sec(days[cur]).scrollIntoView({block:'start',behavior:'smooth'});}}
document.addEventListener('keydown',e=>{if(mode!=='day')return;
  if(e.key==='ArrowLeft')setCur(cur-1);if(e.key==='ArrowRight')setCur(cur+1);});
let txs,txe;document.addEventListener('touchstart',e=>txs=e.touches[0].clientX);
document.addEventListener('touchend',e=>{if(mode!=='day')return;txe=e.changedTouches[0].clientX;const dx=txe-txs;
  if(Math.abs(dx)>60){dx<0?setCur(cur+1):setCur(cur-1);}});
render();
document.getElementById('btnToday').addEventListener('click',()=>setMode('day'));
document.getElementById('btnAll').addEventListener('click',()=>setMode('all'));
document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>{setMode('day');setCur(days.indexOf(t.dataset.d));}));
"""


def extract_wrap(body: str):
    m = re.search(r'<div class="wrap">(.*)</div>\s*</body>', body, re.S)
    return m.group(1).strip() if m else None


def extract_style(body: str):
    m = re.search(r'<style>(.*?)</style>', body, re.S)
    return m.group(1).strip() if m else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="reports/crypto")
    ap.add_argument("--out", default="index.html")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.dir, "crypto_scan_*.html")))
    if not files:
        print("Khong co report nao de gop.")
        return 1

    entries, base_css = [], ""
    for fp in files:
        m = re.search(r"crypto_scan_(\d{4}-\d{2}-\d{2})\.html$", fp)
        if not m:
            continue
        date = m.group(1)
        with open(fp, encoding="utf-8") as fh:
            body = fh.read()
        wrap = extract_wrap(body)
        if wrap is None:
            print(f"skip (khong tim thay .wrap): {fp}")
            continue
        base_css = extract_style(body)  # giữ css của report mới nhất
        dt = datetime.strptime(date, "%Y-%m-%d")
        label = f"{dt.day:02d}/{dt.month:02d} · {WEEKDAYS[dt.weekday()]}"
        entries.append({"date": date, "label": label, "wrap": wrap})

    if not entries:
        print("Khong gop duoc report nao.")
        return 1

    entries.sort(key=lambda e: e["date"])
    tabs = "\n".join(
        f'<button class="tab{"" if e["date"] != entries[-1]["date"] else " active"}" data-d="{e["date"]}">{html.escape(e["label"])}</button>'
        for e in entries
    )
    days = "\n".join(
        f'<section id="{e["date"]}" class="day{"" if e["date"] != entries[-1]["date"] else " show"}">{e["wrap"]}</section>'
        for e in entries
    )

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    first, last = entries[0]["date"], entries[-1]["date"]

    doc = f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Early Discovery — Dashboard {first} → {last}</title>
<style>
{base_css}
{DASH_CSS}
</style>
</head>
<body>
<div class="dash-top">
  <div class="dash-in">
    <div class="dash-head">
      <div class="dash-logo">ED</div>
      <div>
        <div class="dash-title">Early Discovery — Dashboard</div>
        <div class="dash-sub">Báo cáo quét thị trường crypto theo ngày · {len(entries)} báo cáo</div>
      </div>
      <div class="dash-actions">
        <button class="dbtn" id="btnToday" title="Xem từng ngày">Ngày</button>
        <button class="dbtn" id="btnAll" title="Xem tất cả các ngày liên tiếp">Tất cả</button>
      </div>
    </div>
    <nav class="tabs" id="tabs">{tabs}</nav>
  </div>
</div>
<div class="wrap">
  <div class="dcount" style="position:static;margin:16px 0 -8px"></div>
</div>
{days}
<div class="wrap dash-foot">
  <div class="foot">
    Tổng hợp dữ liệu, không phải lời khuyên đầu tư.<br/>
    Dashboard tạo tự động bởi crypto_report_index.py · cập nhật {now} ·
    phím &#8592;/&#8594; hoặc vuốt để đổi ngày
  </div>
</div>
<script>
{DASH_JS}
</script>
</body>
</html>
"""
    out = os.path.join(args.dir, args.out)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"OK: {out} — {len(entries)} ngày ({first} → {last}), css={len(base_css)} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())