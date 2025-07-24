import baostock as bs
import datetime
import pandas as pd
import pymysql
import numpy as np
import time
import os
from datetime import datetime, timedelta
from . import daily_job_baostock_5min

# 使用环境变量获得数据库。兼容开发模式可docker模式。
MYSQL_HOST = os.environ.get('MYSQL_HOST') if (os.environ.get('MYSQL_HOST') != None) else "127.0.0.1"
MYSQL_USER = os.environ.get('MYSQL_USER') if (os.environ.get('MYSQL_USER') != None) else "root"
MYSQL_PWD = os.environ.get('MYSQL_PWD') if (os.environ.get('MYSQL_PWD') != None) else "mysqldb"
MYSQL_DB = os.environ.get('MYSQL_DB') if (os.environ.get('MYSQL_DB') != None) else "stock_data"

def get_stock_data(code, start_date="2000-01-01 00:00:00", end_date=None, adjust="3"):
    # 如果未指定结束日期，默认使用当前日期
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    # 将起始日期和结束日期转换成字符串类型，按照baostock要求的格式进行格式化
    start_date_str = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
    end_date_str = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")


    
    # 根据股票代码添加市场前缀
    if code.startswith('6') or code.startswith('5'):
        stock_code = "sh." + code
    elif code.startswith('0') or code.startswith('3') or code.startswith('2'):
        stock_code = "sz." + code
    else:
        stock_code = code
    
    # 调用baostock的query_history_k_data_plus获取历史行情数据
    print(f"Querying {stock_code} from {start_date_str} to {end_date_str}")
    rs = bs.query_history_k_data_plus(stock_code,
        "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST",
        start_date=start_date_str, 
        end_date=end_date_str,
        frequency="d", 
        adjustflag=adjust)
    
    print('query_history_k_data_plus respond error_code:'+rs.error_code)
    print('query_history_k_data_plus respond  error_msg:'+rs.error_msg)
    
    # 获取查询结果
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    

    
    # 转换为DataFrame
    if data_list:
        data = pd.DataFrame(data_list, columns=rs.fields)
        
        # 转换数据类型
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'turn']
        for col in numeric_columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # 重命名列以匹配原有逻辑
        data = data.rename(columns={
            'date': '日期',
            'open': '开盘',
            'high': '最高',
            'low': '最低',
            'close': '收盘',
            'volume': '成交量',
            'turn': '换手率'
        })
        
        # 计算每天收盘价是否大于开盘价
        data["rise"] = data["收盘"] > data["开盘"]
        
        # 判断是否有连续五天都是收盘价是否大于开盘价，并在符合条件的那一天添加一个rise_continue为1的字段
        data["rise_continue"] = 0
        for i in range(4, len(data)):
            if all(data["rise"][i-4:i+1]):
                data.at[i, "rise_continue"] = 1
                
        # 添加symbol字段
        data["symbol"] = code
        
        # 选择需要的列
        data = data[["symbol", "开盘", "最高", "最低", "收盘", "成交量", "换手率", "rise", "rise_continue", "日期"]]
    else:
        # 如果没有数据，返回空DataFrame
        data = pd.DataFrame(columns=["symbol", "开盘", "最高", "最低", "收盘", "成交量", "换手率", "rise", "rise_continue", "日期"])
    
    print(data)
    return data

# 存储数据到mysql
def save_to_mysql(data, host=MYSQL_HOST, port=3306, user=MYSQL_USER, password=MYSQL_PWD, database=MYSQL_DB):
    # 建立数据库连接
    conn = pymysql.connect(host=host, port=port, user=user, password=password, database=database)
    
    # 将data中的date字段转换成datetime类型，并设置为索引
    data["date"] = pd.to_datetime(data["日期"])
    data.set_index(["symbol", "date"], inplace=True)
    
    # 将数据写入mysql数据库
    cursor = conn.cursor()
    #cursor.execute(create_table_sql)
    for index, row in data.iterrows():
        try: 
            sql = f"INSERT INTO stock_zh_a_daily(symbol, date, open, high, low, close, volume, turnover, rise_continue) VALUES ('{index[0]}', '{index[1]}', {row['开盘']}, {row['最高']}, {row['最低']}, {row['收盘']}, {row['成交量']}, {row['换手率']}, {row['rise_continue']})"
            cursor.execute(sql)
        except Exception as e: 
            print("INSERT INTO stock_zh_a_daily err %s", e)
            continue
    conn.commit()
    
    # 关闭数据库连接
    conn.close()

def stock_a(code):
    # print(code)
    # print(type(code))
    # 上证A股  # 深证A股
    # if code.startswith('600') or code.startswith('6006')  or code.startswith('6016') or code.startswith('601') or code.startswith('000') or code.startswith('001') or code.startswith('002') or code.startswith('300')  or code.startswith('400'):
    #     return True
    # else:
    #     return False
    if code.startswith('900') or code.startswith('200'):
        return False
    else:
        return True
# 过滤掉 st 股票。
def stock_a_filter_st(name):
    # print(code)
    # print(type(code))
    # 上证A股  # 深证A股
    if name.find("ST") == -1:
        return True
    else:
        return False

# 过滤价格，如果没有基本上是退市了。
def stock_a_filter_price(latest_price):
    # float 在 pandas 里面判断 空。
    if np.isnan(latest_price):
        return False
    else:
        return True
    
    
def stat_all():

    # 股票列表
    try:
        datas = daily_job_baostock_5min.get_stock_list()
        # 获取当前日期和时间
        now = datetime.now()
        start_time = now - timedelta(days=60)  # 获取60天前的日期
        # 将时间部分更改为23:59:59，即当天的最后一秒
        start_second = start_time.replace(hour=00, minute=00, second=00)
        end_second = now.replace(hour=23, minute=59, second=59)
        # 格式化为'2023-04-15 00:00:00'这种格式
        start_formatted_date = start_second.strftime('%Y-%m-%d %H:%M:%S')
        # 格式化为'2023-04-15 00:00:00'这种格式
        end_formatted_date = end_second.strftime('%Y-%m-%d %H:%M:%S')
        #for i in range(1):
        lg = bs.login()
        print('login respond error_code:'+lg.error_code)
        print('login respond  error_msg:'+lg.error_msg)
        
        for index, data in datas.iterrows():
            try:
                #time.sleep(1)
                print("start to update gain: " + str(data['code']))
                # if data.iat[i, 1].startswith('60') or data.iat[i, 1].startswith('688'):
                #     save_to_mysql(get_stock_data("sh" + data.iat[i, 1], start_formatted_date, end_formatted_date))
                # if data.iat[i, 1].startswith('00') or data.iat[i, 1].startswith('30'):
                #     save_to_mysql(get_stock_data("sz" + data.iat[i, 1], start_formatted_date, end_formatted_date))
                time.sleep(1)
                save_to_mysql(get_stock_data(data['code'], start_formatted_date, end_formatted_date))
                print("now is handle " + str(index), flush = True)
            except Exception as e:
                print(e)
        # 登出系统
        bs.logout()
    except Exception as e:
        print(e)
        

