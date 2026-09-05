"""publish_dashboard.py — regenerate + commit + push dashboard GitHub Pages sau mỗi scan.

Chạy sau mỗi móc scan H4 futures (paper + bridge) để GitHub Pages phản ánh dữ liệu mới nhất.
Chỉ đưa các file lưu được vào commit (không đụng research/untracked khác).
"""
import subprocess
import sys

TRACKED = [
    "dashboard.html", "index.html",
    "paper_state.json", "paper_trades.csv", "paper_equity.csv",
    "bridge_state.json", "bridge_trades.csv", "bridge_equity.csv", "bridge_orders.jsonl",
]


def run(cmd, check=True):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and p.returncode != 0:
        print(f"[publish] FAILED: {cmd}\n{p.stdout}\n{p.stderr}", flush=True)
        sys.exit(1)
    return p


PY = f'"{sys.executable}"'


def main():
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    run(f"{PY} generate_dashboard.py", check=True)
    run("cp dashboard.html index.html")
    # Stage chỉ những file tồn tại + đã track (an toàn, bỏ qua research/backtest đang dở)
    existing = [f for f in TRACKED if os.path.exists(f)]
    run("git add " + " ".join(existing))
    p = run("git diff --cached --quiet", check=False)
    if p.returncode == 0:
        print("[publish] Không có thay đổi — bỏ qua.", flush=True)
        return
    run("git commit -m 'Update dashboard after futures scan [skip ci]'")
    run("git pull --rebase origin main", check=False)
    run("git push origin main")
    print("[publish] OK — đã push dashboard.", flush=True)


if __name__ == "__main__":
    main()