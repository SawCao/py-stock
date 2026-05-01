#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票换手率上涨数据采集脚本（优化版）
功能：从baostock获取股票历史数据，分析连续上涨情况，并存储到MySQL数据库
"""

import baostock as bs
import datetime
import pandas as pd
import pymysql
import numpy as np
import time
import os
import logging
import sys
import argparse
import socket
import signal
from datetime import datetime, timedelta
from typing import Optional, Tuple
import stock_list_cache

# 1. 全局网络超时设置，防止baostock假死
socket.setdefaulttimeout(30)

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("处理单只股票超时")


# ========== 配置部分 ==========

# 数据库配置
MYSQL_HOST = os.environ.get('MYSQL_HOST', "127.0.0.1")
MYSQL_USER = os.environ.get('MYSQL_USER', "root")
MYSQL_PWD = os.environ.get('MYSQL_PWD', "mysqldb")
MYSQL_DB = os.environ.get('MYSQL_DB', "stock_data")
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))

# 日志配置
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../log')
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f'turnover_rise_baostock_{datetime.now().strftime("%Y%m%d")}.log')

# 配置参数
QUERY_DAYS = 2  # 查询最近N天的数据（默认2天，适合每日执行）
RISE_CONTINUOUS_DAYS = 5  # 连续上涨天数
REQUEST_INTERVAL = 1  # 请求间隔（秒）

# ========== 日志配置 ==========

def setup_logger():
    """配置日志系统"""
    logger = logging.getLogger('turnover_rise_baostock')
    logger.setLevel(logging.INFO)
    
    # 清除已有的handlers
    logger.handlers.clear()
    
    # 文件处理器 - 详细日志
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # 控制台处理器 - 简洁日志
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger()

# ========== 工具函数 ==========

def format_stock_code(code: str) -> str:
    """
    格式化股票代码，添加市场前缀
    注意：北交所股票会被 is_valid_a_stock 函数过滤，这里的北交所处理仅作保留
    
    Args:
        code: 股票代码（可能带或不带市场前缀）
        
    Returns:
        带市场前缀的股票代码
    """
    # 如果已经带有标准市场前缀（含点号），直接返回
    if '.' in code:
        return code
    
    # 处理特殊情况：数据源可能返回 "sh920010" 这样的格式（带市场代码但没有点号）
    if code.startswith('sh') and len(code) == 8:
        return f"sh.{code[2:]}"
    if code.startswith('sz') and len(code) == 8:
        return f"sz.{code[2:]}"
    
    # 上海证券交易所：6开头（主板）、5开头（基金）
    if code.startswith('6') or code.startswith('5'):
        return f"sh.{code}"
    # 深圳证券交易所：0开头（主板）、3开头（创业板）、2开头（中小板/创业板）
    elif code.startswith('0') or code.startswith('3') or code.startswith('2'):
        return f"sz.{code}"
    else:
        # 其他情况，原样返回（包括理论上不应出现的北交所股票）
        return code

def is_valid_a_stock(code: str) -> bool:
    """
    判断是否为有效的A股代码（排除B股和北交所）
    注意：baostock不支持北交所股票查询
    
    Args:
        code: 股票代码
        
    Returns:
        是否为有效A股
    """
    # B股代码：900开头（上海B股）、200开头（深圳B股）
    if code.startswith('900') or code.startswith('200'):
        logger.debug(f"股票 {code} 为B股，已过滤")
        return False
    
    # 北交所股票：bj.开头或8/4开头的6位数字
    # baostock不支持北交所，需要过滤
    if code.startswith('bj.') or code.startswith('bj'):
        logger.debug(f"股票 {code} 为北交所股票，baostock不支持，已过滤")
        return False
    
    # 检查纯数字代码（8或4开头的6位数字是北交所）
    if '.' not in code and len(code) == 6:
        if code.startswith('8') or code.startswith('4'):
            logger.debug(f"股票 {code} 为北交所股票，baostock不支持，已过滤")
            return False
    
    return True

def is_st_stock(name: str) -> bool:
    """
    判断是否为ST股票
    
    Args:
        name: 股票名称
        
    Returns:
        是否为ST股票
    """
    return "ST" in name if name else False

def is_valid_price(price: float) -> bool:
    """
    判断价格是否有效（排除退市股票）
    
    Args:
        price: 股票价格
        
    Returns:
        价格是否有效
    """
    return not np.isnan(price) if isinstance(price, float) else price is not None

# ========== 核心业务函数 ==========

def login_baostock() -> bool:
    """
    登录baostock系统

    Returns:
        是否登录成功
    """
    try:
        max_retries = 30
        for i in range(max_retries):
            lg = bs.login()
            if lg.error_code == '0':
                logger.info("✓ Baostock登录成功")
                return True
            else:
                logger.warning(f"⚠ Baostock登录失败 - 错误码: {lg.error_code}, 错误信息: {lg.error_msg} (重试 {i+1}/{max_retries})")
            time.sleep(30)

        logger.error("✗ Baostock多次重试登录失败")
        return False
    except Exception as e:
        logger.error(f"✗ Baostock登录异常: {str(e)}", exc_info=True)
        return False
def logout_baostock():
    """登出baostock系统"""
    try:
        bs.logout()
        logger.info("✓ Baostock登出成功")
    except Exception as e:
        logger.warning(f"Baostock登出异常: {str(e)}")

def get_stock_data(code: str, start_date: str, end_date: str, adjust: str = "3") -> Optional[pd.DataFrame]:
    """
    获取股票历史数据
    
    Args:
        code: 股票代码（不带市场前缀）
        start_date: 开始日期 (格式: YYYY-MM-DD HH:MM:SS)
        end_date: 结束日期 (格式: YYYY-MM-DD HH:MM:SS)
        adjust: 复权类型 (1:后复权 2:前复权 3:不复权)
        
    Returns:
        处理后的DataFrame，失败返回None
    """
    stock_code = format_stock_code(code)
    
    # 格式化日期
    try:
        start_date_str = datetime.strptime(start_date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        end_date_str = datetime.strptime(end_date, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
    except ValueError as e:
        logger.error(f"✗ [{code}] 日期格式错误: {str(e)}")
        return None
    
    logger.info(f"→ [{code}] 开始查询数据: {start_date_str} 至 {end_date_str}")
    
    try:
        # 查询历史数据
        rs = bs.query_history_k_data_plus(
            stock_code,
            "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST",
            start_date=start_date_str,
            end_date=end_date_str,
            frequency="d",
            adjustflag=adjust
        )
        
        if rs.error_code != '0':
            error_msg = f"API返回错误码: {rs.error_code}, 错误信息: {rs.error_msg}"
            logger.error(f"✗ [{code}] {error_msg}")
            raise Exception(error_msg)
        
        logger.debug(f"  [{code}] 查询API响应成功 - 错误码: {rs.error_code}")
        
        # 获取查询结果
        data_list = []
        # 防御性死循环保护
        max_loops = 5000
        loop_cnt = 0
        while rs.next():
            data_list.append(rs.get_row_data())
            loop_cnt += 1
            if loop_cnt > max_loops:
                logger.error(f"✗ [{code}] 读取数据出现死循环风险，已截断")
                break
        
        if not data_list:
            logger.warning(f"⚠ [{code}] 未获取到任何数据")
            return None
        
        logger.info(f"✓ [{code}] 成功获取 {len(data_list)} 条原始数据")
        
        # 转换为DataFrame
        data = pd.DataFrame(data_list, columns=rs.fields)
        
        # 数据验证和清洗
        data = clean_and_validate_data(data, code)
        
        if data is None or data.empty:
            logger.warning(f"⚠ [{code}] 数据清洗后为空")
            return None
        
        # 计算上涨指标
        data = calculate_rise_indicators(data, code)
        
        # 添加股票代码（不带市场前缀）
        data["symbol"] = code
        
        # 处理 code 字段：去除市场前缀（sh./sz./bj.），只保留纯数字
        # baostock返回的code格式为 sh.600000, sz.000001 等
        if 'code' in data.columns:
            data['code'] = data['code'].apply(lambda x: x.split('.')[-1] if '.' in str(x) else x)
        
        # 选择需要的列（保留 code 字段，已去除市场前缀）
        data = data[["symbol", "code", "开盘", "最高", "最低", "收盘", "成交量", "换手率", 
                     "rise", "rise_continue", "日期"]]
        
        # 统计信息
        rise_continue_count = (data["rise_continue"] == 1).sum()
        logger.info(f"✓ [{code}] 数据处理完成 - 有效数据: {len(data)} 条, "
                   f"连续{RISE_CONTINUOUS_DAYS}天上涨: {rise_continue_count} 次")
        
        # 打印数据摘要
        if not data.empty:
            logger.debug(f"  [{code}] 数据摘要:\n{data.head(3).to_string()}")
            logger.debug(f"  [{code}] 最后几条:\n{data.tail(2).to_string()}")
        
        return data
        
    except Exception as e:
        logger.error(f"✗ [{code}] 获取数据异常: {str(e)}", exc_info=True)
        if "Broken pipe" in str(e) or "接收数据异常" in str(e) or "32" in str(e) or "timeout" in str(e).lower() or "未登录" in str(e) or "10001001" in str(e):
            raise TimeoutException(f"网络异常: {str(e)}")
        return None

def clean_and_validate_data(data: pd.DataFrame, code: str) -> Optional[pd.DataFrame]:
    """
    清洗和验证数据
    
    Args:
        data: 原始数据DataFrame
        code: 股票代码
        
    Returns:
        清洗后的DataFrame
    """
    try:
        original_count = len(data)
        
        # 转换数值列
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'turn']
        for col in numeric_columns:
            data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # 过滤停牌数据
        data = data[data['tradestatus'] == '1']
        tradestatus_filtered = original_count - len(data)
        if tradestatus_filtered > 0:
            logger.debug(f"  [{code}] 过滤停牌数据: {tradestatus_filtered} 条")
        
        # 过滤无效价格数据
        data = data[data['close'].notna() & (data['close'] > 0)]
        price_filtered = original_count - tradestatus_filtered - len(data)
        if price_filtered > 0:
            logger.debug(f"  [{code}] 过滤无效价格数据: {price_filtered} 条")
        
        # 重命名列
        data = data.rename(columns={
            'date': '日期',
            'open': '开盘',
            'high': '最高',
            'low': '最低',
            'close': '收盘',
            'volume': '成交量',
            'turn': '换手率'
        })
        
        # 检查必要字段
        required_columns = ['日期', '开盘', '最高', '最低', '收盘', '成交量', '换手率']
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            logger.error(f"✗ [{code}] 缺少必要字段: {missing_columns}")
            return None
        
        # 检查是否有NaN值
        nan_counts = data[required_columns].isna().sum()
        if nan_counts.any():
            logger.warning(f"⚠ [{code}] 存在NaN值:\n{nan_counts[nan_counts > 0]}")
            data = data.dropna(subset=required_columns)
        
        return data
        
    except Exception as e:
        logger.error(f"✗ [{code}] 数据清洗异常: {str(e)}", exc_info=True)
        return None

def calculate_rise_indicators(data: pd.DataFrame, code: str) -> pd.DataFrame:
    """
    计算上涨指标
    
    Args:
        data: 数据DataFrame
        code: 股票代码
        
    Returns:
        添加了上涨指标的DataFrame
    """
    try:
        # 计算每天是否上涨（收盘价 > 开盘价）
        data["rise"] = (data["收盘"] > data["开盘"]).astype(int)
        
        # 计算连续上涨
        data["rise_continue"] = 0
        
        for i in range(RISE_CONTINUOUS_DAYS - 1, len(data)):
            # 检查连续N天是否都上涨
            if all(data["rise"].iloc[i - RISE_CONTINUOUS_DAYS + 1:i + 1]):
                data.iloc[i, data.columns.get_loc("rise_continue")] = 1
        
        return data
        
    except Exception as e:
        logger.error(f"✗ [{code}] 计算上涨指标异常: {str(e)}", exc_info=True)
        return data

def save_to_mysql(data: pd.DataFrame) -> Tuple[int, int]:
    """
    保存数据到MySQL数据库
    
    Args:
        data: 要保存的数据
        
    Returns:
        (成功条数, 失败条数)
    """
    if data is None or data.empty:
        logger.warning("⚠ 数据为空，跳过保存")
        return 0, 0
    
    symbol = data['symbol'].iloc[0] if 'symbol' in data.columns else 'Unknown'
    conn = None
    cursor = None
    success_count = 0
    fail_count = 0
    
    try:
        # 建立数据库连接
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PWD,
            database=MYSQL_DB,
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        
        logger.info(f"→ [{symbol}] 开始保存数据到数据库，共 {len(data)} 条")
        
        # 转换日期
        data["date"] = pd.to_datetime(data["日期"])
        
        # 使用参数化查询避免SQL注入
        insert_sql = """
            INSERT INTO stock_zh_a_daily 
            (symbol, code, date, open, high, low, close, volume, turnover, rise_continue) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                code = VALUES(code),
                open = VALUES(open),
                high = VALUES(high),
                low = VALUES(low),
                close = VALUES(close),
                volume = VALUES(volume),
                turnover = VALUES(turnover),
                rise_continue = VALUES(rise_continue)
        """
        
        # 3. 改为批量插入优化 CPU 和 DB I/O
        batch_data = []
        for index, row in data.iterrows():
            batch_data.append((
                row['symbol'],
                row['code'],
                row['date'],
                float(row['开盘']) if pd.notna(row['开盘']) else None,
                float(row['最高']) if pd.notna(row['最高']) else None,
                float(row['最低']) if pd.notna(row['最低']) else None,
                float(row['收盘']) if pd.notna(row['收盘']) else None,
                float(row['成交量']) if pd.notna(row['成交量']) else None,
                float(row['换手率']) if pd.notna(row['换手率']) else None,
                int(row['rise_continue']) if pd.notna(row['rise_continue']) else 0
            ))
            
        try:
            cursor.executemany(insert_sql, batch_data)
            success_count += len(batch_data)
        except Exception as e:
            logger.warning(f"⚠ 批量插入失败，降级尝试逐条插入: {str(e)}")
            for item in batch_data:
                try:
                    cursor.execute(insert_sql, item)
                    success_count += 1
                except pymysql.IntegrityError as e:
                    logger.debug(f"  [{symbol}] 数据已存在或主键冲突: {str(e)}")
                    fail_count += 1
                except Exception as e:
                    logger.error(f"✗ [{symbol}] 插入数据失败: {str(e)}")
                    fail_count += 1
        
        conn.commit()
        logger.info(f"✓ [{symbol}] 数据保存完成 - 成功: {success_count} 条, 失败: {fail_count} 条")
        
        return success_count, fail_count
        
    except pymysql.Error as e:
        logger.error(f"✗ [{symbol}] 数据库错误: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        return success_count, fail_count
    except Exception as e:
        logger.error(f"✗ [{symbol}] 保存数据异常: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        return success_count, fail_count
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def process_single_stock(code: str, start_date: str, end_date: str) -> bool:
    """
    处理单个股票
    
    Args:
        code: 股票代码
        start_date: 开始日期
        end_date: 结束日期
        
    Returns:
        是否处理成功
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"开始处理股票: {code}")
    logger.info(f"{'='*80}")
    
    try:
        # 获取股票数据
        data = get_stock_data(code, start_date, end_date)
        
        if data is None or data.empty:
            logger.warning(f"⚠ [{code}] 未获取到有效数据，跳过")
            return False
        
        # 保存到数据库
        success, fail = save_to_mysql(data)
        
        return success > 0
        
    except Exception as e:
        logger.error(f"✗ [{code}] 处理异常: {str(e)}", exc_info=True)
        return False

def stat_all(query_days: int = QUERY_DAYS):
    """
    统计所有股票数据
    
    Args:
        query_days: 查询最近N天的数据，默认为 QUERY_DAYS
    """
    logger.info("="*100)
    logger.info("股票换手率上涨数据采集任务开始")
    logger.info("="*100)
    logger.info(f"日志文件: {LOG_FILE}")
    logger.info(f"数据库: {MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}")
    logger.info(f"查询天数: {query_days} 天")
    logger.info(f"连续上涨天数: {RISE_CONTINUOUS_DAYS} 天")
    
    # 计算时间范围
    now = datetime.now()
    start_time = now - timedelta(days=query_days)
    start_second = start_time.replace(hour=0, minute=0, second=0)
    end_second = now.replace(hour=23, minute=59, second=59)
    start_formatted_date = start_second.strftime('%Y-%m-%d %H:%M:%S')
    end_formatted_date = end_second.strftime('%Y-%m-%d %H:%M:%S')
    
    logger.info(f"查询时间范围: {start_formatted_date} 至 {end_formatted_date}")
    
    # 登录baostock
    if not login_baostock():
        logger.error("✗ Baostock登录失败，任务终止")
        return
    
    try:
        # 获取股票列表（智能缓存，每周自动更新）
        logger.info("\n获取股票列表（使用智能缓存）...")
        stock_list = stock_list_cache.get_stock_list()
        
        if stock_list is None or stock_list.empty:
            logger.error("✗ 未获取到股票列表")
            return
        
        total_stocks = len(stock_list)
        logger.info(f"✓ 成功获取股票列表，共 {total_stocks} 只股票\n")
        
        logger.info("→ 本次补数全量扫描最近窗口，依赖主键去重写入...")

        # 统计信息
        success_count = 0
        fail_count = 0
        skip_count = 0
        start_time_task = time.time()
        
        # 遍历处理每只股票
        for index, stock_info in stock_list.iterrows():
            try:
                code = stock_info['code']
                
                # 进度提示
                progress = (index + 1) / total_stocks * 100
                logger.info(f"\n【进度: {index + 1}/{total_stocks} ({progress:.1f}%)】")
                
                # 验证股票代码
                if not is_valid_a_stock(code):
                    skip_count += 1
                    continue
                
                # 处理股票
                retry_count = 0
                max_retries = 3
                while retry_count <= max_retries:
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(120)
                    try:
                        if process_single_stock(code, start_formatted_date, end_formatted_date):
                            success_count += 1
                        else:
                            fail_count += 1
                        break
                    except TimeoutException as e:
                        retry_count += 1
                        if retry_count <= max_retries:
                            logger.warning(f"⚠ 股票 {code} 网络超时或异常，休眠10秒后重连 (重试 {retry_count}/{max_retries})...")
                            time.sleep(10)
                            try:
                                logout_baostock()
                            except:
                                pass
                            login_baostock()
                        else:
                            logger.error(f"✗ 股票 {code} 处理超时或异常（已重试{max_retries}次）")
                            fail_count += 1
                    finally:
                        signal.alarm(0)

                
                # 请求间隔
                time.sleep(REQUEST_INTERVAL)
                
                # 定期输出统计信息
                if (index + 1) % 100 == 0:
                    elapsed = time.time() - start_time_task
                    avg_time = elapsed / (index + 1)
                    remaining = (total_stocks - index - 1) * avg_time
                    logger.info(f"\n{'='*80}")
                    logger.info(f"阶段统计 [{index + 1}/{total_stocks}]:")
                    logger.info(f"  成功: {success_count}, 失败: {fail_count}, 跳过: {skip_count}")
                    logger.info(f"  已用时: {elapsed/60:.1f} 分钟, 预计剩余: {remaining/60:.1f} 分钟")
                    logger.info(f"{'='*80}\n")
                
            except Exception as e:
                logger.error(f"✗ 处理股票异常 [{stock_info.get('code', 'Unknown')}]: {str(e)}", exc_info=True)
                fail_count += 1
        
        # 最终统计
        total_time = time.time() - start_time_task
        logger.info("\n" + "="*100)
        logger.info("任务完成统计")
        logger.info("="*100)
        logger.info(f"总股票数: {total_stocks}")
        logger.info(f"成功: {success_count} ({success_count/total_stocks*100:.1f}%)")
        logger.info(f"失败: {fail_count} ({fail_count/total_stocks*100:.1f}%)")
        logger.info(f"跳过: {skip_count} ({skip_count/total_stocks*100:.1f}%)")
        logger.info(f"总耗时: {total_time/60:.1f} 分钟")
        logger.info(f"平均处理时间: {total_time/total_stocks:.2f} 秒/股")
        logger.info("="*100)
        
    except Exception as e:
        logger.error(f"✗ 任务执行异常: {str(e)}", exc_info=True)
    finally:
        # 登出baostock
        logout_baostock()

# ========== 主程序入口 ==========

def parse_arguments():
    """
    解析命令行参数
    
    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        description='股票换手率上涨数据采集脚本（优化版）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 使用默认参数（查询前2天数据）
  python turnover_rise_baostock_optimized.py
  
  # 查询前7天数据
  python turnover_rise_baostock_optimized.py --days 7
  
  # 查询前30天数据
  python turnover_rise_baostock_optimized.py -d 30
        """
    )
    
    parser.add_argument(
        '-d', '--days',
        type=int,
        default=QUERY_DAYS,
        metavar='N',
        help=f'查询最近N天的数据（默认: {QUERY_DAYS}天，适合每日执行）'
    )
    
    return parser.parse_args()

if __name__ == "__main__":
    try:
        # 解析命令行参数
        args = parse_arguments()
        
        # 执行任务
        stat_all(query_days=args.days)
    except KeyboardInterrupt:
        logger.warning("\n⚠ 用户中断任务")
        logout_baostock()
    except Exception as e:
        logger.error(f"✗ 程序异常: {str(e)}", exc_info=True)
        logout_baostock()
        sys.exit(1)
