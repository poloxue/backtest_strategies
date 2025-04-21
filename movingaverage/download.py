import findata.data_ccxt as data_ccxt


data = data_ccxt.download(
    symbol="BTC/USDT", start_date="2020-01-01", end_date="2025-04-18", interval="1m"
)
data.to_csv("btcusdt-1m.csv")
