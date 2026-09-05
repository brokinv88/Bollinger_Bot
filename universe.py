import requests
import pandas as pd

def get_binance_listed_usdt_symbols():
    """Lấy toàn bộ các cặp giao dịch USDT đang active trên Binance"""
    url = "https://api.binance.com/api/v3/exchangeInfo"
    resp = requests.get(url, timeout=10).json()
    symbols = set()
    for s in resp['symbols']:
        if s['status'] == 'TRADING' and s['quoteAsset'] == 'USDT':
            symbols.add(s['symbol'])
    return symbols

def get_top_100_volume_symbols():
    """Lấy Top 100 theo 24h Trading Volume trên Binance"""
    url = "https://api.binance.com/api/v3/ticker/24hr"
    resp = requests.get(url, timeout=10).json()
    usdt_pairs = []
    exclude = ['USDCUSDT', 'FDUSDUSDT', 'TUSDUSDT', 'BUSDUSDT', 'EURUSDT', 'AEURUSDT', 'DAIUSDT', 'WBTCUSDT', 'WBETHUSDT', 'USDEUSDT']
    for item in resp:
        sym = item['symbol']
        if sym.endswith('USDT') and sym not in exclude:
            quote_vol = float(item['quoteVolume'])
            usdt_pairs.append({'symbol': sym, 'volume': quote_vol})
    df = pd.DataFrame(usdt_pairs).sort_values(by='volume', ascending=False).reset_index(drop=True)
    return df.head(100)['symbol'].tolist()

def get_top_100_marketcap_symbols():
    """Lấy Top 100 theo Vốn hóa thị trường (Market Cap) niêm yết trên Binance"""
    binance_symbols = get_binance_listed_usdt_symbols()
    exclude = ['USDTUSDT', 'USDCUSDT', 'FDUSDUSDT', 'TUSDUSDT', 'BUSDUSDT', 'EURUSDT', 'AEURUSDT', 'DAIUSDT', 'WBTCUSDT', 'WBETHUSDT', 'USDEUSDT']
    
    # Lấy dữ liệu MarketCap từ CoinGecko API (miễn phí, chuẩn xác)
    url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=250&page=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        resp = requests.get(url, headers=headers, timeout=10).json()
        top_mc_symbols = []
        for coin in resp:
            sym = coin['symbol'].upper() + 'USDT'
            if sym in binance_symbols and sym not in exclude:
                top_mc_symbols.append(sym)
                if len(top_mc_symbols) >= 100:
                    break
        return top_mc_symbols
    except Exception as e:
        print(f"CoinGecko API fallback to CoinCap/Binance: {e}")
        # Fallback to Top Volume if external API rate limited
        return get_top_100_volume_symbols()
