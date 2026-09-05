import sys
import argparse
from datetime import datetime, timezone
import config
from database import PortfolioDB

def log_trade():
    parser = argparse.ArgumentParser(description="Nhập lệnh tay vào hệ thống theo dõi")
    parser.add_argument("--account", choices=["volume", "marketcap"], default="volume", help="Chọn tài khoản (volume hoặc marketcap)")
    parser.add_argument("--strategy", choices=["base", "stratb"], default="base", help="Chọn chiến lược (base hoặc stratb)")
    parser.add_argument("--action", choices=["buy", "sell"], required=True, help="Hành động: buy hoặc sell")
    parser.add_argument("--symbol", required=True, help="Mã coin (ví dụ: BTCUSDT, SUIUSDT)")
    parser.add_argument("--price", type=float, required=True, help="Giá khớp thực tế")
    parser.add_argument("--cash", type=float, default=50.0, help="Số tiền vào lệnh (USD), mặc định 50$")
    parser.add_argument("--reason", default="Thủ công", help="Lý do thoát lệnh (khi sell)")
    
    args = parser.parse_args()
    
    suffix = "_stratb" if args.strategy == "stratb" else ""
    db_file = f"database_{args.account}{suffix}.db"
    db = PortfolioDB(db_file)
    today_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    symbol = args.symbol.upper()
    if not symbol.endswith("USDT"):
        symbol += "USDT"
        
    if args.action == "buy":
        qty = (args.cash * 0.99925) / args.price
        lvl = db.add_or_pyramid_position(symbol, qty, args.cash, args.price, today_str)
        print(f"\n✅ ĐÃ GHI NHẬN LỆNH MUA TAY:")
        print(f"• Tài khoản: {args.account.upper()} | Chiến lược: {args.strategy.upper()}")
        print(f"• DB: {db_file}")
        print(f"• Mã: {symbol} | Giá khớp: {args.price}$ | Vốn: {args.cash}$")
        print(f"• Trạng thái: Pyramid Tầng {lvl}/3")
        
    elif args.action == "sell":
        pnl_usd, pnl_pct, invested = db.close_position_db(symbol, args.price, today_str, args.reason)
        print(f"\n✅ ĐÃ GHI NHẬN LỆNH BÁN TAY:")
        print(f"• Tài khoản: {args.account.upper()} | Chiến lược: {args.strategy.upper()}")
        print(f"• DB: {db_file}")
        print(f"• Mã: {symbol} | Giá bán: {args.price}$")
        print(f"• Vốn ban đầu: {invested:.2f}$ | PnL: {pnl_pct:+.2f}% ({pnl_usd:+.2f}$)")
        print(f"• Lý do: {args.reason}")

if __name__ == "__main__":
    log_trade()
