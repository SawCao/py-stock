import baostock as bs
import datetime
import pandas as pd
import pymysql
import numpy as np
import time
import os
from datetime import datetime, timedelta
import daily_job_baostock_5min

# 使用环境变量获得数据库。兼容开发模式可docker模式。
MYSQL_HOST = os.environ.get('MYSQL_HOST') if (os.environ.get('MYSQL_HOST') != None) else "127.0.0.1"
MYSQL_USER = os.environ.get('MYSQL_USER') if (os.environ.get('MYSQL_USER') != None) else "root"
MYSQL_PWD = os.environ.get('MYSQL_PWD') if (os.environ.get('MYSQL_PWD') != None) else "mysqldb"
MYSQL_DB = os.environ.get('MYSQL_DB') if (os.environ.get('MYSQL_DB') != None) else "stock_data"

import pymysql

def save_df_to_mysql(df,
                     host=MYSQL_HOST, port=3306,
                     user=MYSQL_USER, password=MYSQL_PWD, database=MYSQL_DB):
    if df is None or df.empty:
        print("DataFrame is empty, skip saving.")
        return

    conn = pymysql.connect(host=host, port=port, user=user, password=password,
                           database=database, charset="utf8mb4", autocommit=False)
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO stock_industry
                    (code, code_name, industry, industry_classification)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    code_name = VALUES(code_name),
                    industry  = VALUES(industry),
                    industry_classification = VALUES(industry_classification)
            """
            # 注意列名是否与 df 完全一致
            rows = list(
                df[["code", "code_name", "industry", "industryClassification"]]
                .itertuples(index=False, name=None)
            )
            cursor.executemany(sql, rows)
        conn.commit()
        print(f"Inserted/updated {len(rows)} rows.")
    except Exception as e:
        conn.rollback()
        print("save_df_to_mysql error:", e)
    finally:
        conn.close()

    
def stat_all():

    # 股票列表
    try:

        lg = bs.login()
        print('login respond error_code:'+lg.error_code)
        print('login respond  error_msg:'+lg.error_msg)
        
        rs = bs.query_stock_industry()
        print('query_stock_industry respond error_code:'+rs.error_code)
        print('query_stock_industry respond  error_msg:'+rs.error_msg)
        save_df_to_mysql(rs.get_data())
        # 登出系统
        bs.logout()
    except Exception as e:
        print(e)
        
stat_all()
