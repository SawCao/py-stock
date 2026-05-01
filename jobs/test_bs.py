import baostock as bs
import pandas as pd

def check_stock():
    lg = bs.login()
    print('login respond error_code:'+lg.error_code)
    print('login respond  error_msg:'+lg.error_msg)

    # test 300001
    rs = bs.query_history_k_data_plus("sz.300001",
        "date,code,open,high,low,close,volume,amount,adjustflag",
        start_date='2026-04-11', end_date='2026-04-21',
        frequency="d", adjustflag="3")
    print('query_history_k_data_plus respond error_code:'+rs.error_code)
    print('query_history_k_data_plus respond  error_msg:'+rs.error_msg)

    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    result = pd.DataFrame(data_list, columns=rs.fields)
    print("300001 data:")
    print(result)
    
    # test 600000 (浦发银行) as baseline
    rs = bs.query_history_k_data_plus("sh.600000",
        "date,code,open,high,low,close,volume,amount,adjustflag",
        start_date='2026-04-11', end_date='2026-04-21',
        frequency="d", adjustflag="3")
    
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    result = pd.DataFrame(data_list, columns=rs.fields)
    print("600000 data:")
    print(result)

    bs.logout()

if __name__ == '__main__':
    check_stock()