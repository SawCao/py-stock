#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
"""
A股分钟级数据收集与波动率计算系统
每日18点定时任务，收集全市场A股分钟级数据并计算多周期波动率指标
"""

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
import baostock as bs
import logging
import concurrent.futures
from typing import List, Tuple, Optional
import warnings

# 忽略警告
warnings.filterwarnings('ignore')

# 配置日志
def setup_logging():
    """配置日志系统"""
    # 确保日志目录存在
    import os
    os.makedirs('logs', exist_ok=True)
    
    logger = logging.getLogger('stock_minute_data')
    logger.setLevel(logging.DEBUG)
    
    # 清除现有处理器
    logger.handlers.clear()
    
    # 文件处理器
    file_handler = logging.FileHandler(f'logs/stock_minute_{datetime.datetime.now().strftime("%Y%m%d")}.log')
    file_handler.setLevel(logging.DEBUG)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 设置格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# 配置参数
CONFIG = {
    'MAX_WORKERS': 2,  # 并发线程数
    'RETRY_TIMES': 3,  # 重试次数
    'RETRY_DELAY': 2,  # 重试延迟(秒)
    'CLEANUP_DAYS': 100,  # 数据保留天数
    'BATCH_SIZE': 100,  # 批处理大小
    'TIMEOUT': 30,  # 请求超时时间(秒)
}

# 股票代码正则表达式
STOCK_PATTERNS = {
    'sh_a': re.compile(r'^6(0|8|9)\d{4}$'),  # 上证A股
    'sz_a': re.compile(r'^(0|3)\d{5}$'),     # 深证A股
    'b_share': re.compile(r'^(900|200)\d{3}$'),  # B股
    'bj_a': re.compile(r'bj'),  # bj A股
    'st': re.compile(r'st', re.IGNORECASE),  # ST股票
}

# 计算周期配置
INTERVALS = [5, 10, 15, 20, 30, 60]

def is_valid_a_share(code: str) -> bool:
    """判断是否为有效A股代码"""
    if not code or not isinstance(code, str):
        return False
    return not (STOCK_PATTERNS['b_share'].match(code) or STOCK_PATTERNS['bj_a'].match(code) or STOCK_PATTERNS['st'].match(code))

def is_not_st_stock(name: str) -> bool:
    """过滤ST股票"""
    return isinstance(name, str) and "ST" not in name.upper()

def has_valid_price(price: float) -> bool:
    """检查价格是否有效"""
    return pd.notna(price) and price > 0

def retry_on_exception(max_retries: int = CONFIG['RETRY_TIMES'], delay: int = CONFIG['RETRY_DELAY']):
    """重试装饰器"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"Function {func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    logger.warning(f"Function {func.__name__} failed on attempt {attempt + 1}, retrying in {delay}s...")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

@retry_on_exception()
def fetch_minute_data(code: str, name: str) -> Optional[pd.DataFrame]:
    """获取单只股票分钟级数据"""
    time.sleep(1)
    start_time = time.time()
    current_date = datetime.datetime.now()
    start_date_str = (current_date - datetime.timedelta(days=6)).strftime("%Y-%m-%d")
    # 只取当前这一天
    # start_date_str = current_date.strftime("%Y-%m-%d")
    end_date_str = current_date.strftime("%Y-%m-%d")
    try:
        # 获取5分钟K线数据
        rs = bs.query_history_k_data_plus(
            code,
            "time,open,high,low,close,volume",
            start_date=start_date_str,
            end_date=end_date_str,
            frequency="5",
            adjustflag="3"
        )
        
        if rs.error_code != '0':
            logger.warning(f"No data for {code} - {name}: {rs.error_msg}")
            return None
            
        data = rs.get_data()
        if data.empty:
            logger.warning(f"No data for {code} - {name}")
            return None

        # 数据预处理
        data = data.rename(columns={'time': 'day'})
        data['day'] = pd.to_datetime(data['day'], format='%Y%m%d%H%M%S%f')
        
        required_cols = ['day', 'open', 'close', 'high', 'low', 'volume']
        if not all(col in data.columns for col in required_cols):
            logger.warning(f"Missing required columns for {code}, available: {data.columns.tolist()}")
            return None
            
        data = data[required_cols]
        
        # 添加股票代码和名称
        data['name'] = code.split('.')[1]
        data['rname'] = name
        
        # 确保数值类型正确
        numeric_cols = ['open', 'close', 'high', 'low', 'volume']
        for col in numeric_cols:
            data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # 检查是否有NaN值
        if data[numeric_cols].isnull().any().any():
            logger.warning(f"NaN values found in {code}, dropping rows with NaN")
            data = data.dropna(subset=numeric_cols)
            
        return data
            
    except Exception as e:
        logger.error(f"Error fetching data for {code}: {e}")
        raise

def calculate_gain_indicators(data: pd.DataFrame) -> pd.DataFrame:
    """计算Gain指标"""
    if data is None or data.empty:
        return data
        
    # 计算各个周期的Gain指标
    for interval in INTERVALS:
        col_name = f"Gain_{interval}"
        
        # 计算滚动最高和最低
        high_max = data['high'].rolling(window=interval, min_periods=interval).max()
        low_min = data['low'].rolling(window=interval, min_periods=interval).min()
        
        # 计算Gain值
        gain = np.where(low_min > 0, (high_max - low_min) / low_min, 0)
        data[col_name] = gain
        
    return data

def calculate_additional_indicators(code: str, current_date: datetime.datetime) -> dict:
    """计算额外的指标：包括连续涨跌、换手率、成交量增量等"""
    try:
        # 获取历史日线数据用于计算
        end_date_str = current_date.strftime("%Y%m%d")
        start_date_str = (current_date - datetime.timedelta(days=30)).strftime("%Y%m%d")
        
        # 使用akshare获取日线数据
        hist_data = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                     start_date=start_date_str, 
                                     end_date=end_date_str, 
                                     adjust="")
        
        if hist_data.empty or len(hist_data) < 10:
            return {
                'price_change_5d': 0.0,
                'volume_ratio_10d': 0.0,
                'consecutive_up_5d': False,
                'high_turnover_10d': False,
                'high_turnover_5d': False,
                'volume_increase_5d_pct': 0.0,
                'volume_increase_10d_pct': 0.0
            }
        
        # 重命名列以便使用
        hist_data.columns = ['date', 'name', 'open', 'close', 'high', 'low', 'volume', 'amount', 
                           'amplitude', 'quote_change', 'ups_downs', 'turnover']
        
        # 确保数据按日期排序
        hist_data = hist_data.sort_values('date')
        
        # 计算连续5个交易日涨跌幅
        price_change_5d = 0.0
        if len(hist_data) >= 5:
            # 计算最近5个交易日的累计涨跌幅
            recent_5d = hist_data.tail(5)
            if len(recent_5d) >= 2:
                start_price = recent_5d.iloc[0]['close']
                end_price = recent_5d.iloc[-1]['close']
                if start_price > 0:
                    price_change_5d = (end_price - start_price) / start_price
        
        # 计算10个交易日区间成交量/今日流通量的比值
        volume_ratio_10d = 0.0
        if len(hist_data) >= 10:
            # 获取最近10个交易日的成交量总和
            recent_10d = hist_data.tail(10)
            total_10d_volume = recent_10d['volume'].sum()
            
            # 获取今日成交量作为流通量的近似
            today_volume = recent_10d.iloc[-1]['volume']
            if today_volume > 0:
                volume_ratio_10d = total_10d_volume / today_volume
        
        # 1. 检查最近5个交易日每日涨跌幅是否都>0
        consecutive_up_5d = False
        if len(hist_data) >= 5:
            recent_5d = hist_data.tail(5)
            # 使用quote_change列（涨跌幅百分比）
            if 'quote_change' in recent_5d.columns:
                consecutive_up_5d = all(recent_5d['quote_change'] > 0)
        
        # 2. 检查最近10个交易日每日换手率是否都>0.15
        high_turnover_10d = False
        if len(hist_data) >= 10:
            recent_10d = hist_data.tail(10)
            if 'turnover' in recent_10d.columns:
                high_turnover_10d = all(recent_10d['turnover'] > 0.15)
        
        # 3. 检查最近5个交易日每日换手率是否都>0.15
        high_turnover_5d = False
        if len(hist_data) >= 5:
            recent_5d = hist_data.tail(5)
            if 'turnover' in recent_5d.columns:
                high_turnover_5d = all(recent_5d['turnover'] > 0.15)
        
        # 4. 计算相对5个交易日前的成交量增量百分比
        volume_increase_5d_pct = 0.0
        if len(hist_data) >= 6:  # 需要6天数据来计算5天前的对比
            recent_6d = hist_data.tail(6)
            current_volume = recent_6d.iloc[-1]['volume']
            prev_5d_volume = recent_6d.iloc[0]['volume']
            if prev_5d_volume > 0:
                volume_increase_5d_pct = ((current_volume - prev_5d_volume) / prev_5d_volume) * 100
        
        # 5. 计算相对10个交易日前的成交量增量百分比
        volume_increase_10d_pct = 0.0
        if len(hist_data) >= 11:  # 需要11天数据来计算10天前的对比
            recent_11d = hist_data.tail(11)
            current_volume = recent_11d.iloc[-1]['volume']
            prev_10d_volume = recent_11d.iloc[0]['volume']
            if prev_10d_volume > 0:
                volume_increase_10d_pct = ((current_volume - prev_10d_volume) / prev_10d_volume) * 100
        
        return {
            'price_change_5d': round(price_change_5d, 4),
            'volume_ratio_10d': round(volume_ratio_10d, 4),
            'consecutive_up_5d': consecutive_up_5d,
            'high_turnover_10d': high_turnover_10d,
            'high_turnover_5d': high_turnover_5d,
            'volume_increase_5d_pct': round(volume_increase_5d_pct, 4),
            'volume_increase_10d_pct': round(volume_increase_10d_pct, 4)
        }
        
    except Exception as e:
        logger.error(f"Error calculating additional indicators for {code}: {e}")
        return {
            'price_change_5d': 0.0,
            'volume_ratio_10d': 0.0,
            'consecutive_up_5d': False,
            'high_turnover_10d': False,
            'high_turnover_5d': False,
            'volume_increase_5d_pct': 0.0,
            'volume_increase_10d_pct': 0.0
        }

def should_insert_data(data: pd.DataFrame) -> bool:
    """判断是否应该插入数据"""
    if data is None or data.empty:
        return False
        
    # 检查是否有非零的Gain值
    gain_cols = [f"Gain_{i}" for i in INTERVALS]
    return not (data[gain_cols].sum(axis=1) == 0).all()

@retry_on_exception()
def process_single_stock(code: str, name: str) -> bool:
    """处理单只股票数据"""
    try:
        logger.info(f"Processing {code} - {name}")
        
        # 获取数据
        data = fetch_minute_data(code, name)
        if data is None:
            return False
            
        # 计算指标
        data = calculate_gain_indicators(data)
        
        # 计算额外的指标
        # current_date = datetime.datetime.now()
        # additional_indicators = calculate_additional_indicators(code, current_date)
        
        # 添加新指标到数据中
        # data['price_change_5d'] = additional_indicators['price_change_5d']
        # data['volume_ratio_10d'] = additional_indicators['volume_ratio_10d']
        # data['consecutive_up_5d'] = additional_indicators['consecutive_up_5d']
        # data['high_turnover_10d'] = additional_indicators['high_turnover_10d']
        # data['high_turnover_5d'] = additional_indicators['high_turnover_5d']
        # data['volume_increase_5d_pct'] = additional_indicators['volume_increase_5d_pct']
        # data['volume_increase_10d_pct'] = additional_indicators['volume_increase_10d_pct']
        
        # 检查是否应该插入
        if not should_insert_data(data):
            logger.debug(f"Skipping {code} - all Gain values are zero")
            return True
            
        # 插入数据库
        common.insert_db(data, "stock_zh_a_minute_ol_4", False, "`name`,`day`")
        
        logger.info(f"Successfully processed {code} - {name} with new indicators")
        return True
        
    except Exception as e:
        logger.error(f"Failed to process {code} - {name}: {e}")
        return False

def get_stock_list() -> pd.DataFrame:
    """获取股票列表"""
    try:
        logger.info("Fetching stock list...")
        data = ak.stock_zh_a_spot()
        
        if data.empty:
            raise ValueError("Empty stock list received")
            
        # 标准化列名
        # 'trade' in stock_zh_a_spot corresponds to 'latest_price'
        data = data.rename(columns={'代码': 'code'})
        data = data.rename(columns={'名称': 'name'})
        data = data.rename(columns={'昨收': 'latest_price'})
        
        # 应用过滤条件
        mask = (
            data['code'].apply(is_valid_a_share) &
            data['name'].apply(is_not_st_stock) &
            data['latest_price'].apply(has_valid_price)
        )
        
        filtered_data = data[mask].copy()
        
        # 格式化股票代码以适应baostock
        filtered_data['code'] = filtered_data['code'].apply(lambda x: f"{x[:2]}.{x[2:]}")
        
        logger.info(f"Filtered {len(filtered_data)} stocks from {len(data)} total")
        
        return filtered_data
        
    except Exception as e:
        logger.error(f"Error fetching stock list: {e}")
        raise

def cleanup_old_data(days: int = CONFIG['CLEANUP_DAYS']):
    """清理过期数据"""
    try:
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
        delete_query = f"DELETE FROM stock_zh_a_minute_ol_4 WHERE day < '{cutoff_date}'"
        
        result = common.select(delete_query)
        logger.info(f"Cleaned up data older than {cutoff_date}")
        
    except Exception as e:
        logger.error(f"Error cleaning up old data: {e}")

def process_stocks_batch(stock_list: pd.DataFrame, use_concurrent: bool = True) -> dict:
    """批量处理股票"""
    results = {'success': 0, 'failed': 0, 'total': len(stock_list)}
    
    if use_concurrent and CONFIG['MAX_WORKERS'] > 1:
        # 并发处理
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIG['MAX_WORKERS']) as executor:
            futures = {
                executor.submit(process_single_stock, row['code'], row['name']): (row['code'], row['name'])
                for _, row in stock_list.iterrows()
            }
            
            for future in concurrent.futures.as_completed(futures):
                code, name = futures[future]
                try:
                    success = future.result()
                    if success:
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                except Exception as e:
                    logger.error(f"Exception processing {code}: {e}")
                    results['failed'] += 1
                    
    else:
        # 串行处理
        for index, row in stock_list.iterrows():
            if index % 200 == 0:
                bs.login()  # 确保每100个股票重新登录
            success = process_single_stock(row['code'], row['name'])
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
                
    return results

def stat_all(tmp_datetime: datetime.datetime):
    """主处理函数"""
    start_time = time.time()
    
    try:
        # 登录baostock
        bs.login()
        
        datetime_str = tmp_datetime.strftime("%Y-%m-%d")
        datetime_int = tmp_datetime.strftime("%Y%m%d")
        
        logger.info(f"Starting daily job for {datetime_str}")
        
        # 获取股票列表
        stock_list = get_stock_list()
        if stock_list.empty:
            logger.warning("No stocks to process")
            return
            
        # 添加日期列
        stock_list['date'] = datetime_int
        
        # 处理股票
        results = process_stocks_batch(stock_list)
        
        # 清理过期数据
        cleanup_old_data()
        
        # 统计信息
        elapsed = time.time() - start_time
        logger.info(f"Job completed: {results['success']} success, {results['failed']} failed, "
                   f"total {results['total']} stocks in {elapsed:.2f}s")
                   
    except Exception as e:
        logger.error(f"Job failed: {e}")
        raise
    finally:
        # 登出baostock
        bs.logout()

if __name__ == '__main__':
    # 创建日志目录
    import os
    os.makedirs('logs', exist_ok=True)
    
    # 执行主任务
    tmp_datetime = common.run_with_args(stat_all)
