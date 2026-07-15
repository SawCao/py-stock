import sys
import os
import pandas as pd

# Add path to import
sys.path.append('/app/jobs/new_job')

from turnover_rise_baostock_v3 import save_to_mysql

def test():
    print("Testing batch insertion...")
    data = pd.DataFrame([
        {'symbol': 'sh.999999', 'code': '999999', '日期': '2026-04-19', '开盘': 10.0, '最高': 11.0, '最低': 9.0, '收盘': 10.5, '成交量': 1000000, '换手率': 1.5, 'rise_continue': 1},
        {'symbol': 'sh.999999', 'code': '999999', '日期': '2026-04-18', '开盘': 10.0, '最高': 11.0, '最低': 9.0, '收盘': 10.5, '成交量': 1000000, '换手率': 1.5, 'rise_continue': 0}
    ])
    success, fail = save_to_mysql(data)
    print(f"Result -> Success: {success}, Fail: {fail}")
    if success == 2 and fail == 0:
        print("Batch insertion test passed!")
    else:
        print("Batch insertion test failed!")

if __name__ == "__main__":
    test()
