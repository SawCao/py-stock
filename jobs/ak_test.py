import akshare as ak

stock_zh_a_minute_df = ak.stock_zh_a_minute(symbol='sh603231', period='1', adjust="qfq")
print(stock_zh_a_minute_df)