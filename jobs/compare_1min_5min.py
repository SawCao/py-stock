#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import os
from datetime import datetime, timedelta
import pymysql
import csv

MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PWD = os.environ.get("MYSQL_PWD", "mysqldb")
MYSQL_DB = os.environ.get("MYSQL_DB", "stock_data")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))

def get_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PWD,
        database=MYSQL_DB,
        port=MYSQL_PORT,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )

def query_top_stocks(table_name, start_date, end_date, gain_type="Gain_1", threshold=0.03):
    end_exclusive = end_date + timedelta(days=1)
    
    sql = f"""
        SELECT 
            name, 
            SUBSTRING_INDEX(
                GROUP_CONCAT(COALESCE(NULLIF(rname, ''), name) ORDER BY day DESC SEPARATOR ','),
                ',',
                1
            ) AS rname,
            COUNT(*) AS count
        FROM {table_name}
        WHERE day >= %s AND day < %s
          AND {gain_type} > %s
        GROUP BY name
        ORDER BY count DESC, name ASC
        LIMIT 200
    """
    
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, [start_date.strftime("%Y-%m-%d"), end_exclusive.strftime("%Y-%m-%d"), threshold])
            return cursor.fetchall()

def main():
    now = datetime.now()
    # Frontend default is now - 10 days
    start_date = now - timedelta(days=10)
    end_date = now
    threshold = 0.03

    print(f"Querying data from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}...")

    # Query 5-minute table
    results_5min = query_top_stocks("stock_zh_a_minute_ol_4", start_date, end_date)
    dict_5min = {row["name"]: row for row in results_5min}
    
    # Query 1-minute table
    try:
        results_1min = query_top_stocks("stock_zh_a_minute_ol_1", start_date, end_date)
        dict_1min = {row["name"]: row for row in results_1min}
    except pymysql.err.ProgrammingError as e:
        if 1146 in e.args:
            print("1-minute table 'stock_zh_a_minute_ol_1' does not exist yet or is empty. Please wait for the backfill job to write some data.")
            return
        raise

    all_names = set(dict_5min.keys()).union(set(dict_1min.keys()))

    output_file = "comparison_result.csv"
    with open(output_file, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["代码", "名称", "5分钟表命中次数(Gain_1)", "1分钟表命中次数(Gain_1)", "差值(1分钟-5分钟)"])
        
        for name in sorted(all_names):
            rname = dict_5min.get(name, {}).get("rname") or dict_1min.get(name, {}).get("rname")
            count_5min = dict_5min.get(name, {}).get("count", 0)
            count_1min = dict_1min.get(name, {}).get("count", 0)
            diff = count_1min - count_5min
            writer.writerow([name, rname, count_5min, count_1min, diff])
            
    print(f"Comparison complete. Wrote {len(all_names)} rows to {output_file}.")

if __name__ == "__main__":
    main()
