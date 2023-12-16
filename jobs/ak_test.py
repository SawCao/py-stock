import akshare as ak

# stock_zh_a_minute_df = ak.stock_zh_a_minute(symbol='sh600791', period='1', adjust="qfq")
# print(stock_zh_a_minute_df)

# import akshare as ak

# 注意：该接口返回的数据只有最近一个交易日的有开盘价，其他日期开盘价为 0
stock_zh_a_hist_min_em_df = ak.stock_zh_a_hist_min_em(symbol="000001", period='1', adjust='')
print(stock_zh_a_hist_min_em_df)