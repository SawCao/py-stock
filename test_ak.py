import akshare as ak
try:
    df = ak.stock_zh_a_hist_min_em(symbol="600000", start_date="2026-05-10 09:00:00", end_date="2026-05-20 15:00:00", period="1", adjust="qfq")
    print(df.head())
    print(df.columns)
except Exception as e:
    print(f"Error: {e}")
