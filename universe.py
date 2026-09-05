import ccxt
import requests
import pandas as pd

HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_binance_exchange():
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    return exchange

def get_top_100_volume_symbols():
    try:
        ex = get_binance_exchange()
        tickers = ex.fetch_tickers()
        usdt_pairs = []
        exclude = ['USDC/USDT', 'FDUSD/USDT', 'TUSD/USDT', 'BUSD/USDT', 'EUR/USDT', 'DAI/USDT', 'WBTC/USDT', 'WBETH/USDT']
        
        for symbol, data in tickers.items():
            if symbol.endswith('/USDT') and symbol not in exclude:
                vol = data.get('quoteVolume') or 0.0
                binance_sym = symbol.replace('/', '')
                usdt_pairs.append({'symbol': binance_sym, 'volume': vol})
                
        df = pd.DataFrame(usdt_pairs).sort_values(by='volume', ascending=False).reset_index(drop=True)
        return df.head(100)['symbol'].tolist()
    except Exception as e:
        print(f"CCXT Volume fetch error: {e}, using public mirror...")
        # Fallback public mirror
        url = "https://data-api.binance.vision/api/v3/ticker/24hr"
        resp = requests.get(url, headers=HEADERS, timeout=10).json()
        if isinstance(resp, list):
            usdt_pairs = []
            for item in resp:
                sym = item.get('symbol', '')
                if sym.endswith('USDT'):
                    usdt_pairs.append({'symbol': sym, 'volume': float(item.get('quoteVolume', 0))})
            df = pd.DataFrame(usdt_pairs).sort_values(by='volume', ascending=False).reset_index(drop=True)
            return df.head(100)['symbol'].tolist()
        return []

def get_top_100_marketcap_symbols():
    exclude = ['USDTUSDT', 'USDCUSDT', 'FDUSDUSDT', 'TUSDUSDT', 'BUSDUSDT', 'EURUSDT', 'DAIUSDT', 'WBTCUSDT']
    try:
        # Lấy danh sách từ CoinGecko
        url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=200&page=1"
        resp = requests.get(url, headers=HEADERS, timeout=10).json()
        top_mc_symbols = []
        if isinstance(resp, list):
            for coin in resp:
                sym = coin.get('symbol', '').upper() + 'USDT'
                if sym not in exclude:
                    top_mc_symbols.append(sym)
                    if len(top_mc_symbols) >= 100:
                        break
            return top_mc_symbols
    except Exception as e:
        print(f"CoinGecko fetch error: {e}")
        
    return get_top_100_volume_symbols()
