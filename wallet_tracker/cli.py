"""CLI: python -m wallet_tracker <lệnh>"""
import argparse
import csv
import json

from . import config, db, discovery, paper, plugins, scoring, settings, telegram
from .monitor import Monitor, run_daily


def main(argv=None):
    ap = argparse.ArgumentParser(prog="wallet_tracker")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add", help="thêm/bật ví theo dõi")
    a.add_argument("chain", choices=list(config.CHAINS))
    a.add_argument("address")
    a.add_argument("--note", default="")
    a.add_argument("--sniper", action="store_true", help="chỉ alert, không paper")
    i = sub.add_parser("import", help="nhập ví từ CSV (cột: chain,address,note)")
    i.add_argument("file")
    r = sub.add_parser("remove", help="tắt ví")
    r.add_argument("chain", choices=list(config.CHAINS))
    r.add_argument("address")
    l = sub.add_parser("list", help="liệt kê ví")
    l.add_argument("--all", action="store_true", help="gồm cả candidate/disabled")
    d = sub.add_parser("discover", help="quét người mua sớm của 1 token (EVM)")
    d.add_argument("chain", choices=list(config.CHAINS))
    d.add_argument("token")
    d.add_argument("--minutes", type=int, default=config.DISCOVERY_WINDOW_MIN)
    sub.add_parser("monitor", help="chạy theo dõi liên tục")
    sub.add_parser("once", help="chạy 1 vòng theo dõi")
    sub.add_parser("daily", help="auto-discovery + tắt ví lỗ + báo cáo")
    sub.add_parser("report", help="thống kê paper trade")
    sc = sub.add_parser("score", help="chấm điểm ví (1 ví hoặc các ví đến hạn)")
    sc.add_argument("chain", nargs="?", choices=list(config.CHAINS))
    sc.add_argument("address", nargs="?")
    b = sub.add_parser("blacklist", help="thêm/xóa token blacklist")
    b.add_argument("action", choices=["add", "remove", "list"])
    b.add_argument("chain", nargs="?", help="chain hoặc * cho mọi chain")
    b.add_argument("token", nargs="?")
    b.add_argument("--reason", default="")
    st = sub.add_parser("set", help="xem/sửa tham số (giá trị dạng JSON)")
    st.add_argument("key", nargs="?")
    st.add_argument("value", nargs="?")
    args = ap.parse_args(argv)
    conn = db.connect()
    plugins.load()

    if args.cmd == "add":
        new = db.add_wallet(conn, args.chain, args.address, status="watch_only" if args.sniper else "active",
                            note=args.note)
        print("Đã thêm" if new else "Đã cập nhật/bật lại", args.chain, args.address)
    elif args.cmd == "import":
        n = 0
        with open(args.file, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("chain") in config.CHAINS and row.get("address"):
                    n += db.add_wallet(conn, row["chain"], row["address"], note=row.get("note", ""))
        print(f"Đã thêm {n} ví mới")
    elif args.cmd == "remove":
        print("Đã tắt" if db.set_status(conn, args.chain, args.address, "disabled") else "Không tìm thấy ví")
    elif args.cmd == "list":
        rows = db.list_wallets(conn, statuses=None if args.all else ("active", "watch_only"))
        for w in rows:
            print(f"{w['chain']:9} {w['address']:46} {w['status']:10} {w['source']:9} hits={w['early_hits']} {w['note']}")
        print(f"Tổng: {len(rows)} ví | chain đang chạy: {config.active_chains()}")
    elif args.cmd == "discover":
        msg = discovery.format_discovery(args.chain, discovery.discover_token(conn, args.chain, args.token,
                                                                             args.minutes))
        telegram.send(msg)
    elif args.cmd == "monitor":
        Monitor(conn).run_forever()
    elif args.cmd == "once":
        Monitor(conn).run_once()
    elif args.cmd == "daily":
        run_daily(conn)
    elif args.cmd == "score":
        if args.address:
            m = scoring.score_wallet(conn, args.chain, config.norm(args.chain, args.address))
            print({k: v for k, v in m.items() if not k.startswith("_")},
                  db.get_labels(conn, args.chain, config.norm(args.chain, args.address)))
        else:
            print(f"Đã chấm {len(scoring.score_due(conn))} ví; tự thêm: {discovery.promote_scored(conn)}")
    elif args.cmd == "blacklist":
        if args.action == "add":
            db.blacklist_add(conn, args.chain, args.token, args.reason)
        elif args.action == "remove":
            db.blacklist_remove(conn, args.chain, args.token)
        for r in conn.execute("SELECT * FROM blacklist"):
            print(r["chain"], r["token"], r["reason"])
    elif args.cmd == "set":
        if args.key and args.value is not None:
            settings.set(conn, args.key, json.loads(args.value))
        for k, v in settings.all(conn).items():
            if not args.key or k == args.key:
                print(f"{k} = {json.dumps(v, ensure_ascii=False)}")
    elif args.cmd == "report":
        print(telegram.format_stats(conn))
        for r in paper.wallet_stats(conn):
            print(f"{r['chain']:9} {r['wallet']:46} lệnh={r['n']} win={r['winrate']:.0%} PnL=${r['pnl']:+.2f}")


if __name__ == "__main__":
    main()
