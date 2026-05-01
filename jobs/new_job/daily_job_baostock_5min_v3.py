#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
"""
A股分钟级数据收集与波动率计算系统 V2
每日18点定时任务，收集全市场A股分钟级数据并计算多周期波动率指标

改进点：
1. 从 stock_list_cache 模块获取股票列表
2. 独立的数据库管理，不依赖 common 模块
3. 优化的日志系统，清晰记录每个股票的执行状态
4. 增强的异常处理机制
"""

import os
import sys
import time
import logging
import datetime
import warnings
import re
import argparse
import socket
import signal
from typing import List, Tuple, Optional, Dict

# 1. 全局网络超时设置，防止baostock底层的socket假死
socket.setdefaulttimeout(30)

from decimal import Decimal
import threading
import pandas as pd
import numpy as np
import pymysql
from pymysql import Connection, cursors
import baostock as bs
from sqlalchemy import create_engine, text
from sqlalchemy.types import NVARCHAR, DECIMAL, TIMESTAMP, INTEGER, BOOLEAN

# 导入股票列表缓存模块
import stock_list_cache

# 忽略警告
warnings.filterwarnings('ignore')

# ==================== 配置部分 ====================

# 数据库配置
MYSQL_HOST = os.environ.get('MYSQL_HOST', "127.0.0.1")
MYSQL_USER = os.environ.get('MYSQL_USER', "root")
MYSQL_PWD = os.environ.get('MYSQL_PWD', "mysqldb")
MYSQL_DB = os.environ.get('MYSQL_DB', "stock_data")
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))

# 任务配置
CONFIG = {
    'MAX_WORKERS': 1,  # 并发线程数（建议为1，避免baostock限流）
    'RETRY_TIMES': 3,  # 重试次数
    'RETRY_DELAY': 2,  # 重试延迟(秒)
    'CLEANUP_DAYS': 100,  # 数据保留天数
    'BATCH_SIZE': 500,  # 批处理大小
    'TIMEOUT': 30,  # 请求超时时间(秒)
    'SLEEP_BETWEEN_STOCKS': 1,  # 股票间延迟(秒)
    'QUERY_DAYS': 2,  # 查询最近N天的数据（默认6天）
    'MAX_CONSECUTIVE_EMPTY': 120,  # 连续无数据的股票超过该值则认为数据源异常，提前退出
    'MAX_RUNTIME_MINUTES': 999999,  # 任务最长运行时间，超过则强制收尾退出
}

# 计算周期配置
INTERVALS = [5, 10, 15, 20, 30, 60]

# 目标数据表
TARGET_TABLE = "stock_zh_a_minute_ol_4"

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("处理单只股票超时")


# ==================== 日志配置 ====================

def setup_logging() -> logging.Logger:
    """配置日志系统"""
    os.makedirs('logs', exist_ok=True)
    
    logger = logging.getLogger('stock_minute_data_v2')
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    
    # 文件处理器 - 详细日志
    today = datetime.datetime.now().strftime("%Y%m%d")
    file_handler = logging.FileHandler(
        f'logs/stock_minute_v2_{today}.log',
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    
    # 文件处理器 - 错误日志
    error_handler = logging.FileHandler(
        f'logs/stock_minute_v2_errors_{today}.log',
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # 设置格式
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - [%(levelname)s] - %(funcName)s:%(lineno)d - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - [%(levelname)s] - %(message)s'
    )
    
    file_handler.setFormatter(detailed_formatter)
    error_handler.setFormatter(detailed_formatter)
    console_handler.setFormatter(simple_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logging()

# ==================== 数据库管理 ====================

class DatabaseManager:
    """数据库管理类"""
    
    def __init__(self):
        self.connection_params = {
            'host': MYSQL_HOST,
            'port': MYSQL_PORT,
            'user': MYSQL_USER,
            'password': MYSQL_PWD,
            'database': MYSQL_DB,
            'charset': 'utf8mb4'
        }
        self.engine = None
        self._init_engine()
    
    def _init_engine(self):
        """初始化 SQLAlchemy 引擎"""
        try:
            connection_string = (
                f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PWD}@"
                f"{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}?charset=utf8mb4"
            )
            self.engine = create_engine(
                connection_string,
                pool_size=5,
                max_overflow=10,
                pool_recycle=3600,
                pool_pre_ping=True
            )
            logger.info("✓ 数据库引擎初始化成功")
        except Exception as e:
            logger.error(f"✗ 数据库引擎初始化失败: {e}", exc_info=True)
            raise
    
    def get_connection(self) -> Connection:
        """获取数据库连接"""
        try:
            return pymysql.connect(**self.connection_params)
        except Exception as e:
            logger.error(f"✗ 获取数据库连接失败: {e}", exc_info=True)
            raise
    
    def ensure_table_exists(self):
        """确保目标表存在"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 检查表是否存在
            cursor.execute(f"""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = '{MYSQL_DB}' 
                AND table_name = '{TARGET_TABLE}'
            """)
            
            if cursor.fetchone()[0] == 0:
                logger.warning(f"⚠ 表 {TARGET_TABLE} 不存在，开始创建...")
                self._create_table(cursor)
                conn.commit()
                logger.info(f"✓ 表 {TARGET_TABLE} 创建成功")
            else:
                logger.info(f"✓ 表 {TARGET_TABLE} 已存在")
                
        except Exception as e:
            logger.error(f"✗ 检查/创建表失败: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _create_table(self, cursor):
        """创建数据表"""
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            day DATETIME NOT NULL COMMENT '时间',
            name VARCHAR(20) NOT NULL COMMENT '股票代码',
            rname VARCHAR(50) COMMENT '股票名称',
            open DECIMAL(10, 3) COMMENT '开盘价',
            close DECIMAL(10, 3) COMMENT '收盘价',
            high DECIMAL(10, 3) COMMENT '最高价',
            low DECIMAL(10, 3) COMMENT '最低价',
            volume BIGINT COMMENT '成交量',
            Gain_5 DECIMAL(10, 6) COMMENT '5周期波动率',
            Gain_10 DECIMAL(10, 6) COMMENT '10周期波动率',
            Gain_15 DECIMAL(10, 6) COMMENT '15周期波动率',
            Gain_20 DECIMAL(10, 6) COMMENT '20周期波动率',
            Gain_30 DECIMAL(10, 6) COMMENT '30周期波动率',
            Gain_60 DECIMAL(10, 6) COMMENT '60周期波动率',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_name_day (name, day),
            INDEX idx_day (day),
            INDEX idx_name (name)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='A股分钟级数据表';
        """
        cursor.execute(create_sql)
    
    def insert_dataframe(self, df: pd.DataFrame, table_name: str) -> Tuple[int, int]:
        """
        插入DataFrame数据到数据库（使用 ON DUPLICATE KEY UPDATE）
        
        Returns:
            (成功数量, 失败数量)
        """
        if df is None or df.empty:
            logger.warning("⚠ DataFrame为空，跳过插入")
            return 0, 0
        
        success_count = 0
        fail_count = 0
        
        try:
            # 使用自定义批量插入，支持 ON DUPLICATE KEY UPDATE
            success_count = self._batch_insert_with_upsert(df, table_name)
            logger.debug(f"  成功插入/更新 {success_count} 条记录")
            
        except Exception as e:
            # 如果批量插入失败，尝试逐条插入
            logger.warning(f"⚠ 批量插入失败: {e}，尝试逐条插入")
            success_count, fail_count = self._insert_row_by_row(df, table_name)
        
        return success_count, fail_count
    
    def _batch_insert_with_upsert(self, df: pd.DataFrame, table_name: str) -> int:
        """
        批量插入数据，使用 ON DUPLICATE KEY UPDATE 处理主键冲突
        
        Returns:
            成功插入/更新的记录数
        """
        conn = None
        cursor = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 构建插入SQL
            columns = df.columns.tolist()
            placeholders = ', '.join(['%s'] * len(columns))
            columns_str = ', '.join([f"`{col}`" for col in columns])
            
            # 构建 ON DUPLICATE KEY UPDATE 子句（排除主键字段）
            update_cols = [col for col in columns if col not in ['name', 'day']]
            update_clause = ', '.join([f"`{col}`=VALUES(`{col}`)" for col in update_cols])
            
            insert_sql = f"""
                INSERT INTO {table_name} ({columns_str})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE {update_clause}
            """
            
            # 分批插入
            batch_size = CONFIG['BATCH_SIZE']
            total_rows = len(df)
            inserted_count = 0
            
            for start_idx in range(0, total_rows, batch_size):
                end_idx = min(start_idx + batch_size, total_rows)
                batch_df = df.iloc[start_idx:end_idx]
                
                # 准备批量数据
                batch_data = []
                for _, row in batch_df.iterrows():
                    values = tuple(row[col] for col in columns)
                    batch_data.append(values)
                
                # 执行批量插入
                cursor.executemany(insert_sql, batch_data)
                inserted_count += len(batch_data)
                
                logger.debug(f"    批次 {start_idx//batch_size + 1}: 插入/更新 {len(batch_data)} 条")
            
            conn.commit()
            logger.debug(f"  批量插入完成: 共 {inserted_count} 条记录")
            
            return inserted_count
            
        except Exception as e:
            logger.error(f"✗ 批量插入异常: {e}", exc_info=True)
            if conn:
                conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def _insert_row_by_row(self, df: pd.DataFrame, table_name: str) -> Tuple[int, int]:
        """逐条插入数据（批量失败时的备用方案）"""
        conn = None
        cursor = None
        success_count = 0
        fail_count = 0
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # 构建插入SQL
            columns = df.columns.tolist()
            placeholders = ', '.join(['%s'] * len(columns))
            columns_str = ', '.join([f"`{col}`" for col in columns])
            
            insert_sql = f"""
                INSERT INTO {table_name} ({columns_str})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE
                {', '.join([f"`{col}`=VALUES(`{col}`)" for col in columns if col not in ['name', 'day']])}
            """
            
            for idx, row in df.iterrows():
                try:
                    values = tuple(row[col] for col in columns)
                    cursor.execute(insert_sql, values)
                    success_count += 1
                except Exception as e:
                    fail_count += 1
                    logger.debug(f"    插入失败 (行{idx}): {e}")
            
            conn.commit()
            logger.debug(f"  逐条插入完成: 成功 {success_count}, 失败 {fail_count}")
            
        except Exception as e:
            logger.error(f"✗ 逐条插入异常: {e}", exc_info=True)
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
        
        return success_count, fail_count
    
    def cleanup_old_data(self, days: int = CONFIG['CLEANUP_DAYS']):
        """清理过期数据"""
        conn = None
        cursor = None
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
            
            delete_sql = f"DELETE FROM {TARGET_TABLE} WHERE day < %s"
            cursor.execute(delete_sql, (cutoff_date,))
            deleted_count = cursor.rowcount
            
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"✓ 清理了 {deleted_count} 条过期数据（早于 {cutoff_date}）")
            else:
                logger.info(f"✓ 无需清理数据（早于 {cutoff_date} 的记录为0）")
                
        except Exception as e:
            logger.error(f"✗ 清理过期数据失败: {e}", exc_info=True)
            if conn:
                conn.rollback()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

# ==================== 数据处理 ====================

class StockDataProcessor:
    """股票数据处理类"""
    
    def __init__(self, db_manager: DatabaseManager, query_days: int = CONFIG['QUERY_DAYS']):
        self.db_manager = db_manager
        self.bs_logged_in = False
        self.query_days = query_days
    
    def login_baostock(self):
        """登录baostock，带重试"""
        max_retries = 30
        for i in range(max_retries):
            try:
                if self.bs_logged_in:
                    return

                result = bs.login()
                if result.error_code == '0':
                    self.bs_logged_in = True
                    logger.info("✓ Baostock 登录成功")
                    return
                else:
                    logger.warning(f"⚠ Baostock 登录失败: {result.error_msg} (重试 {i+1}/{max_retries})")
            except Exception as e:
                logger.warning(f"⚠ Baostock 登录异常: {e} (重试 {i+1}/{max_retries})")
            time.sleep(30)

        raise Exception("Baostock login failed after max retries")
    
    def logout_baostock(self, timeout_sec: int = 3):
        """带超时的 baostock 登出"""
        if not self.bs_logged_in:
            return
        def _do_logout():
            try:
                bs.logout()
            except Exception as e:
                logger.warning(f"⚠ Baostock 登出异常: {e}")
        t = threading.Thread(target=_do_logout, daemon=True)
        t.start()
        t.join(timeout=timeout_sec)
        if t.is_alive():
            logger.warning(f"⚠ Baostock 登出在 {timeout_sec}s 内未完成，跳过")
        else:
            logger.info("✓ Baostock 登出成功")
        self.bs_logged_in = False
    
    def fetch_minute_data(self, code: str, name: str, retry_count: int = 0) -> Optional[pd.DataFrame]:
        """
        获取单只股票分钟级数据
        
        Args:
            code: 股票代码（格式：sh.600000）
            name: 股票名称
            retry_count: 当前重试次数
            
        Returns:
            DataFrame 或 None
        """
        try:
            time.sleep(CONFIG['SLEEP_BETWEEN_STOCKS'])
            
            current_date = datetime.datetime.now()
            # 获取最近N天的数据
            start_date_str = (current_date - datetime.timedelta(days=self.query_days)).strftime("%Y-%m-%d")
            end_date_str = current_date.strftime("%Y-%m-%d")
            
            logger.debug(f"    查询 {code} 的数据范围: {start_date_str} ~ {end_date_str} (最近{self.query_days}天)")
            
            # 获取5分钟K线数据
            rs = bs.query_history_k_data_plus(
                code,
                "time,open,high,low,close,volume",
                start_date=start_date_str,
                end_date=end_date_str,
                frequency="5",  # 5分钟
                adjustflag="3"  # 不复权
            )
            
            if rs.error_code != '0':
                error_msg = f"API返回错误码: {rs.error_code}, 错误信息: {rs.error_msg}"
                logger.warning(f"  ⚠ {code} [{name}] {error_msg}")
                raise Exception(error_msg)
            
            data = rs.get_data()
            if data.empty:
                logger.warning(f"  ⚠ {code} [{name}] 返回数据为空")
                return None
            
            # 数据预处理
            data = data.rename(columns={'time': 'day'})
            data['day'] = pd.to_datetime(data['day'], format='%Y%m%d%H%M%S%f')
            
            required_cols = ['day', 'open', 'close', 'high', 'low', 'volume']
            if not all(col in data.columns for col in required_cols):
                logger.warning(f"  ⚠ {code} [{name}] 缺少必需列，当前列: {data.columns.tolist()}")
                return None
            
            data = data[required_cols].copy()
            
            # 添加股票代码和名称
            data['name'] = code.split('.')[1] if '.' in code else code
            data['rname'] = name
            
            # 确保数值类型正确
            numeric_cols = ['open', 'close', 'high', 'low', 'volume']
            for col in numeric_cols:
                data[col] = pd.to_numeric(data[col], errors='coerce')
            
            # 检查是否有NaN值
            if data[numeric_cols].isnull().any().any():
                logger.debug(f"    {code} [{name}] 发现NaN值，将删除包含NaN的行")
                data = data.dropna(subset=numeric_cols)
            
            if data.empty:
                logger.warning(f"  ⚠ {code} [{name}] 清洗后数据为空")
                return None
            
            logger.debug(f"    {code} [{name}] 获取到 {len(data)} 条记录")
            return data
            
        except Exception as e:
            if retry_count < CONFIG['RETRY_TIMES']:
                logger.warning(f"  ⚠ {code} [{name}] 获取数据失败，重试 {retry_count + 1}/{CONFIG['RETRY_TIMES']}: {e}")
                if "Broken pipe" in str(e) or "接收数据异常" in str(e) or "32" in str(e) or "timeout" in str(e).lower() or "未登录" in str(e) or "10001001" in str(e):
                    logger.warning(f"  ⚠ 捕获到Broken pipe/网络异常/未登录，强制休眠10秒并重连...")
                    time.sleep(10)
                    try:
                        self.logout_baostock(timeout_sec=2)
                    except:
                        pass
                    self.login_baostock()
                else:
                    time.sleep(CONFIG['RETRY_DELAY'])
                return self.fetch_minute_data(code, name, retry_count + 1)
            else:
                logger.error(f"  ✗ {code} [{name}] 获取数据失败（已重试{CONFIG['RETRY_TIMES']}次）: {e}")
                return None
    
    def calculate_gain_indicators(self, data: pd.DataFrame, code: str, name: str) -> pd.DataFrame:
        """
        计算Gain指标（波动率）
        
        Args:
            data: 原始数据
            code: 股票代码
            name: 股票名称
            
        Returns:
            添加了Gain指标的DataFrame
        """
        if data is None or data.empty:
            return data
        
        try:
            for interval in INTERVALS:
                col_name = f"Gain_{interval}"
                
                # 计算滚动最高和最低
                high_max = data['high'].rolling(window=interval, min_periods=interval).max()
                low_min = data['low'].rolling(window=interval, min_periods=interval).min()
                
                # 计算Gain值：(最高-最低)/最低
                gain = np.where(low_min > 0, (high_max - low_min) / low_min, 0)
                data[col_name] = gain
            
            logger.debug(f"    {code} [{name}] 计算了 {len(INTERVALS)} 个周期的Gain指标")
            return data
            
        except Exception as e:
            logger.error(f"  ✗ {code} [{name}] 计算Gain指标失败: {e}", exc_info=True)
            return data
    
    def should_insert_data(self, data: pd.DataFrame, code: str, name: str) -> bool:
        """判断是否应该插入数据"""
        if data is None or data.empty:
            return False
        
        try:
            # 检查是否有非零的Gain值
            gain_cols = [f"Gain_{i}" for i in INTERVALS]
            has_valid_data = not (data[gain_cols].sum(axis=1) == 0).all()
            
            if not has_valid_data:
                logger.debug(f"    {code} [{name}] 所有Gain值为0，跳过插入")
            
            return has_valid_data
            
        except Exception as e:
            logger.error(f"  ✗ {code} [{name}] 判断数据有效性失败: {e}")
            return False
    
    def process_single_stock(self, code: str, name: str) -> Dict[str, any]:
        """
        处理单只股票
        
        Returns:
            处理结果字典
        """
        result = {
            'code': code,
            'name': name,
            'success': False,
            'error': None,
            'records': 0
        }
        
        try:
            logger.info(f"→ 处理股票: {code} [{name}]")
            
            # 1. 获取数据
            data = self.fetch_minute_data(code, name)
            if data is None:
                result['error'] = "获取数据失败或无数据"
                logger.warning(f"  ⚠ {code} [{name}] {result['error']}")
                return result
            
            # 2. 计算指标
            data = self.calculate_gain_indicators(data, code, name)
            
            # 3. 检查是否应该插入
            if not self.should_insert_data(data, code, name):
                result['error'] = "数据无效（所有Gain值为0）"
                result['success'] = True  # 这不算失败，只是数据不符合条件
                return result
            
            # 4. 插入数据库
            success_count, fail_count = self.db_manager.insert_dataframe(data, TARGET_TABLE)
            
            result['records'] = success_count
            result['success'] = success_count > 0
            
            if result['success']:
                logger.info(f"  ✓ {code} [{name}] 处理成功，插入 {success_count} 条记录")
            else:
                result['error'] = f"插入失败（失败{fail_count}条）"
                logger.error(f"  ✗ {code} [{name}] {result['error']}")
            
            return result
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"  ✗ {code} [{name}] 处理异常: {e}", exc_info=True)
            return result

# ==================== 主流程 ====================

def process_all_stocks(start_datetime: datetime.datetime, query_days: int = CONFIG['QUERY_DAYS']):
    """主处理流程"""
    start_time = time.time()
    max_runtime_seconds = CONFIG['MAX_RUNTIME_MINUTES'] * 60
    consecutive_empty = 0  # 连续无数据的计数器，用于识别数据源异常
    
    # 统计信息
    stats = {
        'total': 0,
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'total_records': 0,
        'failed_stocks': [],  # 记录失败的股票
        'processed': 0
    }
    
    db_manager = None
    processor = None
    
    try:
        logger.info("=" * 100)
        logger.info(f"开始执行A股分钟级数据收集任务 - {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"查询天数: {query_days} 天")
        logger.info("=" * 100)
        
        # 1. 初始化数据库
        logger.info("\n步骤1: 初始化数据库连接...")
        db_manager = DatabaseManager()
        db_manager.ensure_table_exists()
        
        # 2. 获取股票列表
        logger.info("\n步骤2: 获取股票列表...")
        stock_list = stock_list_cache.get_stock_list()
        
        if stock_list is None or stock_list.empty:
            logger.error("✗ 无法获取股票列表，任务终止")
            return
            
        logger.info("\n步骤2.5: 本次补数全量扫描最近窗口，依赖唯一键去重写入...")
        
        stats['total'] = len(stock_list)
        logger.info(f"✓ 获取到 {stats['total']} 只股票")
        
        # 3. 登录 baostock
        logger.info("\n步骤3: 登录 Baostock...")
        processor = StockDataProcessor(db_manager, query_days)
        processor.login_baostock()
        
        # 4. 处理每只股票
        logger.info(f"\n步骤4: 开始处理股票数据...")
        logger.info("=" * 100)
        
        for idx, row in stock_list.iterrows():
            try:
                stats['processed'] = idx  # 循环开始前记录已处理数量

                # 若整体运行时间超限，提前退出，避免长时间占用CPU
                if time.time() - start_time > max_runtime_seconds:
                    logger.error(
                        f"✗ 任务超过最大运行时间 {CONFIG['MAX_RUNTIME_MINUTES']} 分钟，提前结束"
                    )
                    break

                # 重新登录（每200只股票）
                if idx > 0 and idx % 200 == 0:
                    logger.info(f"\n已处理 {idx}/{stats['total']} 只股票，重新登录 Baostock...")
                    processor.logout_baostock()
                    processor.login_baostock()

                # 处理单只股票
                                # 2. 设置看门狗超时 (120秒)
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(120)
                try:
                    result = processor.process_single_stock(row['code'], row['name'])
                except TimeoutException as e:
                    logger.error(f"✗ 股票 {row['code']} 处理超时被看门狗拦截")
                    result = {'success': False, 'error': '处理超时', 'records': 0, 'code': row['code'], 'name': row['name']}
                    # 如果超时，底层连接可能已卡死，强制重新登录
                    processor.logout_baostock(timeout_sec=1)
                    processor.login_baostock()
                finally:
                    signal.alarm(0)  # 取消定时器


                # 连续无数据计数：当数据源返回空时快速识别并中断，避免无意义的长跑
                if not result['success'] and result.get('error') in ("获取数据失败或无数据",):
                    consecutive_empty += 1
                    if consecutive_empty >= CONFIG['MAX_CONSECUTIVE_EMPTY']:
                        logger.error(
                            f"✗ 连续 {consecutive_empty} 只股票无数据，疑似数据源异常，提前结束任务"
                        )
                        break
                else:
                    consecutive_empty = 0

                if result['success']:
                    stats['success'] += 1
                    stats['total_records'] += result['records']
                else:
                    if result['error'] and 'Gain值为0' not in result['error']:
                        stats['failed'] += 1
                        stats['failed_stocks'].append({
                            'code': result['code'],
                            'name': result['name'],
                            'error': result['error']
                        })
                    else:
                        stats['skipped'] += 1
                
                # 进度提示（每50只）
                if (idx + 1) % 50 == 0:
                    elapsed = time.time() - start_time
                    avg_time = elapsed / (idx + 1)
                    remaining = avg_time * (stats['total'] - idx - 1)
                    logger.info(f"\n进度: {idx + 1}/{stats['total']} "
                              f"({(idx + 1) / stats['total'] * 100:.1f}%) | "
                              f"成功: {stats['success']} | 失败: {stats['failed']} | "
                              f"跳过: {stats['skipped']} | "
                              f"预计剩余: {remaining / 60:.1f}分钟\n")
                
            except Exception as e:
                stats['failed'] += 1
                stats['failed_stocks'].append({
                    'code': row.get('code', 'Unknown'),
                    'name': row.get('name', 'Unknown'),
                    'error': str(e)
                })
                logger.error(f"✗ 处理股票时发生异常: {row.get('code', 'Unknown')} [{row.get('name', 'Unknown')}]: {e}", 
                           exc_info=True)
        # 循环正常退出后补充最终处理数量
        stats['processed'] = max(stats['processed'], stats['success'] + stats['failed'] + stats['skipped'])
        
        # 5. 清理过期数据
        logger.info(f"\n步骤5: 清理过期数据...")
        db_manager.cleanup_old_data()
        
        # 6. 输出汇总
        elapsed_time = time.time() - start_time
        logger.info("\n" + "=" * 100)
        logger.info("任务执行完成！")
        logger.info("=" * 100)
        logger.info(f"总耗时: {elapsed_time / 60:.2f} 分钟 ({elapsed_time:.2f} 秒)")
        logger.info(f"计划股票数: {stats['total']}")
        logger.info(f"已处理: {stats['processed']} ({stats['processed'] / stats['total'] * 100:.1f}% 计划量)")
        logger.info(f"成功处理: {stats['success']} ({(stats['success'] / stats['processed'] * 100) if stats['processed'] else 0:.1f}%)")
        logger.info(f"处理失败: {stats['failed']} ({(stats['failed'] / stats['processed'] * 100) if stats['processed'] else 0:.1f}%)")
        logger.info(f"跳过处理: {stats['skipped']} ({(stats['skipped'] / stats['processed'] * 100) if stats['processed'] else 0:.1f}%)")
        logger.info(f"插入记录: {stats['total_records']} 条")
        
        # 输出失败的股票列表
        if stats['failed_stocks']:
            logger.error("\n" + "=" * 100)
            logger.error(f"失败股票清单（共 {len(stats['failed_stocks'])} 只）:")
            logger.error("=" * 100)
            for i, stock in enumerate(stats['failed_stocks'], 1):
                logger.error(f"{i}. {stock['code']} [{stock['name']}] - 原因: {stock['error']}")
            logger.error("=" * 100)
        
    except Exception as e:
        logger.error(f"\n✗ 任务执行失败: {e}", exc_info=True)
        raise
        
    finally:
        # 登出 baostock
        if processor:
            processor.logout_baostock()
        
        logger.info("\n任务结束\n")

# ==================== 入口函数 ====================

def parse_arguments():
    """
    解析命令行参数
    
    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        description='A股分钟级数据收集与波动率计算系统 V2',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 使用默认参数（查询前6天数据）
  python daily_job_baostock_5min_v2.py
  
  # 查询前10天数据
  python daily_job_baostock_5min_v2.py --days 10
  
  # 指定日期并查询前7天数据
  python daily_job_baostock_5min_v2.py --date 20241020 --days 7
  
  # 简写形式
  python daily_job_baostock_5min_v2.py -d 10
        """
    )
    
    parser.add_argument(
        '-d', '--days',
        type=int,
        default=CONFIG['QUERY_DAYS'],
        metavar='N',
        help=f'查询最近N天的数据（默认: {CONFIG["QUERY_DAYS"]}天）'
    )
    
    parser.add_argument(
        '--date',
        type=str,
        default=None,
        metavar='YYYYMMDD',
        help='指定基准日期（格式: YYYYMMDD，默认为当前日期）'
    )
    
    return parser.parse_args()

def main():
    """主入口函数"""
    try:
        # 解析命令行参数
        args = parse_arguments()
        
        # 确定基准日期
        if args.date:
            target_datetime = datetime.datetime.strptime(args.date, "%Y%m%d")
            logger.info(f"使用指定日期: {target_datetime.strftime('%Y-%m-%d')}")
        else:
            target_datetime = datetime.datetime.now()
            logger.info(f"使用当前日期: {target_datetime.strftime('%Y-%m-%d')}")
        
        # 执行任务
        process_all_stocks(target_datetime, query_days=args.days)
        
    except KeyboardInterrupt:
        logger.warning("\n⚠ 任务被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ 程序异常退出: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
