#!/usr/local/bin/python3
# -*- coding: utf-8 -*-


import re
import common
import sys
import time
import pandas as pd
import numpy as np
from sqlalchemy.types import NVARCHAR
from sqlalchemy import inspect
import datetime
import akshare as ak

import logging
import concurrent.futures

# 600开头的股票是上证A股，属于大盘股
# 600开头的股票是上证A股，属于大盘股，其中6006开头的股票是最早上市的股票，
# 6016开头的股票为大盘蓝筹股；900开头的股票是上证B股；
# 000开头的股票是深证A股，001、002开头的股票也都属于深证A股，
# 其中002开头的股票是深证A股中小企业股票；
# 200开头的股票是深证B股；
# 300开头的股票是创业板股票；400开头的股票是三板市场股票。
# 中国股市主要分为主板、中小板、创业板和科创板四个板块。其中，上海证券交易所和深圳证券交易所都设有主板，深圳证券交易所独有中小板和创业板，上海证券交易所独有科创板1。
# 沪市主板股票代码以600、601、603、605开头，深市主板股票代码以000开头。深市中小板股票代码以002开头，深市创业板股票代码以300开头，沪市科创板股票代码以688开头1。
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



def insert_minute(code, name):
    try:
        start_time = time.time()
        
        data = ak.stock_zh_a_minute(symbol=code)[(-240 + 2)*15:]
        data = data.reset_index(drop=True)
        data['name'] = code[2:]
        data['rname'] = name
        data.columns = ['day', 'open', 'high', 'low', 'close', 'volume', 'name', "rname"]
        intervals = [5, 6, 7, 8, 9, 10, 15, 20, 30, 60]
        for interval in intervals:
            interval_col = f"Gain_{interval}"
            data[interval_col] = 0.0

            data[['high', 'low']] = data[['high', 'low']].astype(float)

            high = data['high'].rolling(interval).max()
            low = data['low'].rolling(interval).min()
            data[interval_col] = (high - low) / low
            #print("data[interval_col][interval-1:]", data[interval_col][interval-1:])
            #print("data.at[interval-1:, interval_col]", data.at[interval-1:, interval_col])
            data.loc[data.index[:interval - 1], interval_col] = 0
            data.loc[data.index[interval-1]:, interval_col] = data[interval_col][interval-1:].to_numpy()
        print("data.iloc[0]:", data.iloc[0])
        if (data.filter(regex="^Gain_").sum(axis=1) == 0).all():
            print("All Gain_ columns are 0, not inserting into database")
        else:
            common.insert_db(data, "stock_zh_a_minute_ol_2", False, "`name`,`day`")
        time.sleep(2)
        print("Time taken: {:.2f} seconds".format(time.time() - start_time))
        # Delete records that are older than 30 days

    except Exception as e:
        print("exception:", e)
        logging.exception(e)
        
def insert_minute_wrapper(code, name):
    print("start to update gain: " + str(code))
    if code.startswith('60') or code.startswith('688'):
        insert_minute("sh" + code, name)
    if code.startswith('00') or code.startswith('30'):
        insert_minute("sz" + code, name)
####### 3.pdf 方法。宏观经济数据
# 接口全部有错误。只专注股票数据。
def stat_all(tmp_datetime):

    datetime_str = (tmp_datetime).strftime("%Y-%m-%d")
    datetime_int = (tmp_datetime).strftime("%Y%m%d")
    print("datetime_str:", datetime_str)
    print("datetime_int:", datetime_int)
    
    # 股票列表
    try:
        #common.insert(del_sql)
        data = ak.stock_zh_a_spot_em()
        # print(data.index)
        # 解决ESP 小数问题。
        # data["esp"] = data["esp"].round(2)  # 数据保留2位小数
        data.columns = ['index', 'code', 'name', 'latest_price', 'quote_change', 'ups_downs', 'volume', 'turnover',
                        'amplitude', 'high', 'low', 'open', 'closed', 'quantity_ratio', 'turnover_rate', 'pe_dynamic',
                        'pb','t1','t2','t3','t4','t5','t6']

        data = data.loc[data["code"].apply(stock_a)].loc[data["name"].apply(stock_a_filter_st)].loc[
            data["latest_price"].apply(stock_a_filter_price)]
        data['date'] = datetime_int  # 修改时间成为int类型。

        #for i in range(1):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            for i in range(data.shape[0]):
                code = data.iat[i, 1]
                name = data.iat[i, 2]
                executor.submit(insert_minute_wrapper, code, name)
                # 删除老数据。
        del_sql = " DELETE FROM `stock_zh_ah_name_new_3` where `date` = '%s' " % datetime_int
        common.insert(del_sql)
        
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=40)).strftime("%Y-%m-%d")
        delete_query = f"DELETE FROM stock_zh_a_minute_ol_2 WHERE day < '{cutoff_date}'"
        common.select(delete_query)
        
        data.set_index('code', inplace=True)
        data.drop('index', axis=1, inplace=True)
        # 删除index，然后和原始数据合并。
        common.insert_db(data, "stock_zh_ah_name_new_3", True, "`date`,`code`")
    except Exception as e:
        logging.exception(e)


    # 分时数据
    # try:

    #     data = ak.stock_zh_a_minute(symbol="sh600519")
    #     # print(data.index)
    #     # 解决ESP 小数问题。
    #     # data["esp"] = data["esp"].round(2)  # 数据保留2位小数
    #     data.columns = ['day', 'open', 'high', 'low', 'close', 'volume']
    #     data = data.loc[data["code"].apply(stock_a)].loc[data["name"].apply(stock_a_filter_st)].loc[
    #         data["latest_price"].apply(stock_a_filter_price)]
    #     print(data)
    #     data['date'] = datetime_int  # 修改时间成为int类型。

    #     # 删除老数据。
    #     del_sql = " DELETE FROM `stock_zh_ah_name` where `date` = '%s' " % datetime_int
    #     common.insert(del_sql)

    #     data.set_index('code', inplace=True)
    #     data.drop('index', axis=1, inplace=True)
    #     print(data)
    #     # 删除index，然后和原始数据合并。
    #     common.insert_db(data, "stock_zh_ah_name", True, "`date`,`code`")
    # except Exception as e:
    #     print("error :", e)

    # 龙虎榜-个股上榜统计
    # 接口: stock_sina_lhb_ggtj
    #
    # 目标地址: http://vip.stock.finance.sina.com.cn/q/go.php/vLHBData/kind/ggtj/index.phtml
    #
    # 描述: 获取新浪财经-龙虎榜-个股上榜统计
    #

    # try:
    #     stock_sina_lhb_ggtj = ak.stock_sina_lhb_ggtj(recent_day="5")
    #     print(stock_sina_lhb_ggtj)

    #     stock_sina_lhb_ggtj.columns = ['code', 'name', 'ranking_times', 'sum_buy', 'sum_sell', 'net_amount', 'buy_seat',
    #                                    'sell_seat']

    #     stock_sina_lhb_ggtj = stock_sina_lhb_ggtj.loc[stock_sina_lhb_ggtj["code"].apply(stock_a)].loc[
    #         stock_sina_lhb_ggtj["name"].apply(stock_a_filter_st)]

    #     stock_sina_lhb_ggtj.set_index('code', inplace=True)
    #     # data_sina_lhb.drop('index', axis=1, inplace=True)
    #     # 删除老数据。
    #     stock_sina_lhb_ggtj['date'] = datetime_int  # 修改时间成为int类型。

    #     # 删除老数据。
    #     del_sql = " DELETE FROM `stock_sina_lhb_ggtj` where `date` = '%s' " % datetime_int
    #     common.insert(del_sql)

    #     common.insert_db(stock_sina_lhb_ggtj, "stock_sina_lhb_ggtj", True, "`date`,`code`")

    # except Exception as e:
    #     print("error :", e)


    # 每日统计
    # 接口: stock_dzjy_mrtj
    #
    # 目标地址: http://data.eastmoney.com/dzjy/dzjy_mrtj.aspx
    #
    # 描述: 获取东方财富网-数据中心-大宗交易-每日统计

    # try:

    #     print("################ tmp_datetime : " + datetime_str)

    #     stock_dzjy_mrtj = ak.stock_dzjy_mrtj(start_date=datetime_str, end_date=datetime_str)
    #     print(stock_dzjy_mrtj)

    #     stock_dzjy_mrtj.columns = ['index', 'trade_date', 'code', 'name', 'quote_change', 'close_price', 'average_price',
    #                                'overflow_rate', 'trade_number', 'sum_volume', 'sum_turnover',
    #                                'turnover_market_rate']

    #     stock_dzjy_mrtj.set_index('code', inplace=True)
    #     # data_sina_lhb.drop('index', axis=1, inplace=True)
    #     # 删除老数据。
    #     stock_dzjy_mrtj['date'] = datetime_int  # 修改时间成为int类型。
    #     stock_dzjy_mrtj.drop('trade_date', axis=1, inplace=True)
    #     stock_dzjy_mrtj.drop('index', axis=1, inplace=True)

    #     # 数据保留2位小数
    #     try:
    #         stock_dzjy_mrtj = stock_dzjy_mrtj.loc[stock_dzjy_mrtj["code"].apply(stock_a)].loc[
    #             stock_dzjy_mrtj["name"].apply(stock_a_filter_st)]

    #         stock_dzjy_mrtj["average_price"] = stock_dzjy_mrtj["average_price"].round(2)
    #         stock_dzjy_mrtj["overflow_rate"] = stock_dzjy_mrtj["overflow_rate"].round(4)
    #         stock_dzjy_mrtj["turnover_market_rate"] = stock_dzjy_mrtj["turnover_market_rate"].round(6)
    #     except Exception as e:
    #         print("round error :", e)

    #     # 删除老数据。
    #     del_sql = " DELETE FROM `stock_dzjy_mrtj` where `date` = '%s' " % datetime_int
    #     common.insert(del_sql)

    #     print(stock_dzjy_mrtj)

    #     common.insert_db(stock_dzjy_mrtj, "stock_dzjy_mrtj", True, "`date`,`code`")

    # except Exception as e:
    #     print("error :", e)

# main函数入口
if __name__ == '__main__':
    # 执行数据初始化。
    # 使用方法传递。
    tmp_datetime = common.run_with_args(stat_all)
