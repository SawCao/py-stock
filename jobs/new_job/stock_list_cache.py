#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
股票列表缓存管理模块
功能：将股票列表缓存到数据库，每周自动更新一次
"""

import os
import logging
import pandas as pd
import pymysql
from datetime import datetime, timedelta
from typing import Optional, Tuple
import akshare as ak

# 数据库配置
MYSQL_HOST = os.environ.get('MYSQL_HOST', "127.0.0.1")
MYSQL_USER = os.environ.get('MYSQL_USER', "root")
MYSQL_PWD = os.environ.get('MYSQL_PWD', "mysqldb")
MYSQL_DB = os.environ.get('MYSQL_DB', "stock_data")
MYSQL_PORT = int(os.environ.get('MYSQL_PORT', 3306))

# 缓存配置
CACHE_EXPIRE_DAYS = 7  # 缓存过期天数（每周更新一次）

# 配置日志
logger = logging.getLogger('stock_list_cache')

def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PWD,
        database=MYSQL_DB,
        charset='utf8mb4'
    )

def init_stock_list_table():
    """
    初始化股票列表缓存表
    
    表结构：
    - id: 自增主键
    - code: 股票代码（带市场前缀，如 sh.600000）
    - raw_code: 原始代码（不带前缀，如 600000）
    - name: 股票名称
    - latest_price: 最新价格
    - is_active: 是否有效（1=有效，0=无效）
    - created_at: 创建时间
    - updated_at: 更新时间
    """
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS stock_list_cache (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(20) NOT NULL COMMENT '股票代码（带市场前缀）',
            raw_code VARCHAR(10) NOT NULL COMMENT '原始股票代码',
            name VARCHAR(50) COMMENT '股票名称',
            latest_price DECIMAL(10, 3) COMMENT '最新价格',
            is_active TINYINT DEFAULT 1 COMMENT '是否有效：1=有效，0=无效',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            UNIQUE KEY uk_code (code),
            INDEX idx_raw_code (raw_code),
            INDEX idx_is_active (is_active),
            INDEX idx_updated_at (updated_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票列表缓存表';
        """
        
        cursor.execute(create_table_sql)
        conn.commit()
        logger.info("✓ 股票列表缓存表初始化成功")
        return True
        
    except Exception as e:
        logger.error(f"✗ 初始化股票列表缓存表失败: {str(e)}", exc_info=True)
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def check_cache_freshness() -> Tuple[bool, Optional[datetime]]:
    """
    检查缓存是否新鲜（是否需要更新）
    
    Returns:
        (is_fresh, last_update_time)
        - is_fresh: True=缓存新鲜不需要更新，False=缓存过期需要更新
        - last_update_time: 最后更新时间
    """
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = %s AND table_name = 'stock_list_cache'
        """, (MYSQL_DB,))
        
        if cursor.fetchone()[0] == 0:
            logger.info("⚠ 股票列表缓存表不存在，需要初始化")
            return False, None
        
        # 获取最新的更新时间和记录数
        cursor.execute("""
            SELECT MAX(updated_at) as last_update, COUNT(*) as total_count 
            FROM stock_list_cache 
            WHERE is_active = 1
        """)
        
        result = cursor.fetchone()
        last_update = result[0]
        total_count = result[1]
        
        if not last_update or total_count == 0:
            logger.info("⚠ 股票列表缓存为空，需要首次更新")
            return False, None
        
        # 计算缓存年龄
        now = datetime.now()
        cache_age = now - last_update
        is_fresh = cache_age.days < CACHE_EXPIRE_DAYS
        
        if is_fresh:
            logger.info(f"✓ 缓存新鲜 - 最后更新: {last_update.strftime('%Y-%m-%d %H:%M:%S')}, "
                       f"已有 {total_count} 条记录, 距今 {cache_age.days} 天")
        else:
            logger.info(f"⚠ 缓存过期 - 最后更新: {last_update.strftime('%Y-%m-%d %H:%M:%S')}, "
                       f"距今 {cache_age.days} 天（超过 {CACHE_EXPIRE_DAYS} 天）")
        
        return is_fresh, last_update
        
    except Exception as e:
        logger.error(f"✗ 检查缓存新鲜度失败: {str(e)}", exc_info=True)
        return False, None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def fetch_stock_list_from_source() -> Optional[pd.DataFrame]:
    """
    从数据源（akshare）获取股票列表
    
    Returns:
        股票列表DataFrame或None
    """
    try:
        logger.info("→ 正在从akshare获取股票列表...")
        
        # 获取A股实时行情数据
        data = ak.stock_zh_a_spot()
        
        if data.empty:
            logger.error("✗ 获取到的股票列表为空")
            return None
        
        logger.info(f"✓ 成功获取 {len(data)} 条原始股票数据")
        
        # 标准化列名
        data = data.rename(columns={
            '代码': 'raw_code',
            '名称': 'name',
            '昨收': 'latest_price'
        })
        
        # 过滤条件
        def is_valid_a_share(code: str) -> bool:
            """判断是否为有效A股代码（排除B股和北交所）
            注意：baostock不支持北交所股票查询
            """
            if not code or not isinstance(code, str):
                return False
            # 排除B股（900开头=上海B股、200开头=深圳B股）
            if code.startswith('900') or code.startswith('200'):
                return False
            # 排除北交所股票（8或4开头且6位数字，或bj开头）
            # baostock不支持北交所，在这里就过滤掉
            if code.startswith('bj'):
                return False
            if len(code) == 6 and (code.startswith('8') or code.startswith('4')):
                return False
            return True
        
        def is_not_st_stock(name: str) -> bool:
            """过滤ST股票"""
            return isinstance(name, str) and "ST" not in name.upper()
        
        def has_valid_price(price) -> bool:
            """检查价格是否有效"""
            return pd.notna(price) and float(price) > 0
        
        # 应用过滤条件
        mask = (
            data['raw_code'].apply(is_valid_a_share) &
            data['name'].apply(is_not_st_stock) &
            data['latest_price'].apply(has_valid_price)
        )
        
        filtered_data = data[mask].copy()
        
        # 添加带市场前缀的代码
        def add_market_prefix(code: str) -> str:
            """添加市场前缀
            注意：北交所股票已在前面的过滤条件中被排除，不会执行到这里
            """
            # 如果已经包含标准市场前缀（含点号），直接返回
            if '.' in code:
                return code
            
            # 处理特殊情况：某些数据源可能返回 "sh920010" 这样的格式（带市场代码但没有点号）
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
                # 其他情况原样返回（理论上不应该执行到这里）
                return code
        
        filtered_data['code'] = filtered_data['raw_code'].apply(add_market_prefix)
        
        # 选择需要的列
        result = filtered_data[['code', 'raw_code', 'name', 'latest_price']].copy()
        
        logger.info(f"✓ 过滤后得到 {len(result)} 只有效股票")
        logger.debug(f"  样例数据:\n{result.head(3).to_string()}")
        
        return result
        
    except Exception as e:
        logger.error(f"✗ 从数据源获取股票列表失败: {str(e)}", exc_info=True)
        return None

def update_stock_list_cache(stock_df: pd.DataFrame) -> bool:
    """
    更新股票列表缓存
    
    策略：
    1. 将数据库中现有股票标记为无效（is_active=0）
    2. 插入或更新新的股票列表
    3. 对于已存在的股票，更新信息并标记为有效
    
    Args:
        stock_df: 股票列表DataFrame
        
    Returns:
        是否更新成功
    """
    if stock_df is None or stock_df.empty:
        logger.error("✗ 股票列表数据为空，无法更新缓存")
        return False
    
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        logger.info(f"→ 开始更新股票列表缓存，共 {len(stock_df)} 条记录")
        
        # 步骤1: 将所有现有记录标记为无效
        cursor.execute("UPDATE stock_list_cache SET is_active = 0")
        logger.info(f"  已将现有记录标记为无效")
        
        # 步骤2: 批量插入或更新
        insert_sql = """
            INSERT INTO stock_list_cache (code, raw_code, name, latest_price, is_active)
            VALUES (%s, %s, %s, %s, 1)
            ON DUPLICATE KEY UPDATE
                raw_code = VALUES(raw_code),
                name = VALUES(name),
                latest_price = VALUES(latest_price),
                is_active = 1,
                updated_at = CURRENT_TIMESTAMP
        """
        
        success_count = 0
        fail_count = 0
        
        # 批量执行
        batch_data = []
        for _, row in stock_df.iterrows():
            try:
                batch_data.append((
                    row['code'],
                    row['raw_code'],
                    row['name'],
                    float(row['latest_price']) if pd.notna(row['latest_price']) else None
                ))
                
                # 每1000条批量提交一次
                if len(batch_data) >= 1000:
                    cursor.executemany(insert_sql, batch_data)
                    conn.commit()
                    success_count += len(batch_data)
                    logger.debug(f"  已处理 {success_count} 条记录")
                    batch_data = []
                    
            except Exception as e:
                logger.error(f"  ✗ 处理股票 {row.get('code', 'Unknown')} 失败: {str(e)}")
                fail_count += 1
        
        # 处理剩余数据
        if batch_data:
            cursor.executemany(insert_sql, batch_data)
            conn.commit()
            success_count += len(batch_data)
        
        # 步骤3: 清理长期无效的记录（超过30天未更新）
        cursor.execute("""
            DELETE FROM stock_list_cache 
            WHERE is_active = 0 
            AND updated_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
        """)
        deleted_count = cursor.rowcount
        conn.commit()
        
        if deleted_count > 0:
            logger.info(f"  清理了 {deleted_count} 条长期无效记录")
        
        # 统计信息
        cursor.execute("SELECT COUNT(*) FROM stock_list_cache WHERE is_active = 1")
        active_count = cursor.fetchone()[0]
        
        logger.info(f"✓ 股票列表缓存更新完成")
        logger.info(f"  成功: {success_count} 条")
        logger.info(f"  失败: {fail_count} 条")
        logger.info(f"  当前有效股票: {active_count} 只")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ 更新股票列表缓存失败: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_stock_list_from_cache() -> Optional[pd.DataFrame]:
    """
    从缓存中获取股票列表
    
    Returns:
        股票列表DataFrame或None
    """
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
            SELECT code, raw_code, name, latest_price, updated_at
            FROM stock_list_cache
            WHERE is_active = 1
            ORDER BY code
        """)
        
        results = cursor.fetchall()
        
        if not results:
            logger.warning("⚠ 缓存中没有有效的股票数据")
            return None
        
        df = pd.DataFrame(results)
        logger.info(f"✓ 从缓存中读取到 {len(df)} 只股票")
        
        return df
        
    except Exception as e:
        logger.error(f"✗ 从缓存读取股票列表失败: {str(e)}", exc_info=True)
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_stock_list(force_update: bool = False) -> Optional[pd.DataFrame]:
    """
    获取股票列表（智能缓存）
    
    逻辑：
    1. 检查缓存是否新鲜
    2. 如果缓存新鲜且不强制更新，从缓存读取
    3. 如果缓存过期或强制更新，从数据源获取并更新缓存
    
    Args:
        force_update: 是否强制更新（忽略缓存）
        
    Returns:
        股票列表DataFrame或None
    """
    logger.info("="*80)
    logger.info("获取股票列表")
    logger.info("="*80)
    
    # 初始化表（如果不存在）
    init_stock_list_table()
    
    # 检查是否需要更新
    if not force_update:
        is_fresh, last_update = check_cache_freshness()
        
        if is_fresh:
            logger.info("→ 使用缓存数据")
            stock_list = get_stock_list_from_cache()
            
            if stock_list is not None and not stock_list.empty:
                return stock_list
            else:
                logger.warning("⚠ 缓存读取失败，尝试从数据源更新")
    else:
        logger.info("⚠ 强制更新模式，将从数据源获取最新数据")
    
    # 从数据源获取
    logger.info("→ 从数据源获取最新股票列表")
    stock_list = fetch_stock_list_from_source()
    
    if stock_list is None or stock_list.empty:
        logger.error("✗ 从数据源获取股票列表失败")
        
        # 尝试使用旧缓存作为备选
        logger.info("→ 尝试使用旧缓存数据作为备选")
        return get_stock_list_from_cache()
    
    # 更新缓存
    if update_stock_list_cache(stock_list):
        logger.info("✓ 股票列表获取完成")
        return stock_list
    else:
        logger.warning("⚠ 缓存更新失败，但返回从数据源获取的数据")
        return stock_list

def get_stock_info(code: str) -> Optional[dict]:
    """
    获取单个股票信息
    
    Args:
        code: 股票代码（带或不带市场前缀）
        
    Returns:
        股票信息字典或None
    """
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 支持带前缀或不带前缀的查询
        cursor.execute("""
            SELECT code, raw_code, name, latest_price, updated_at
            FROM stock_list_cache
            WHERE (code = %s OR raw_code = %s) AND is_active = 1
            LIMIT 1
        """, (code, code))
        
        result = cursor.fetchone()
        return result
        
    except Exception as e:
        logger.error(f"✗ 获取股票信息失败 [{code}]: {str(e)}")
        return None
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

# 测试函数
def test_stock_list_cache():
    """测试股票列表缓存功能"""
    import sys
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    print("\n" + "="*80)
    print("测试1: 首次获取股票列表（会从数据源获取并缓存）")
    print("="*80)
    stock_list = get_stock_list()
    if stock_list is not None:
        print(f"✓ 获取成功，共 {len(stock_list)} 只股票")
        print("\n前5条记录:")
        print(stock_list.head())
    else:
        print("✗ 获取失败")
    
    print("\n" + "="*80)
    print("测试2: 再次获取股票列表（应该从缓存读取）")
    print("="*80)
    stock_list = get_stock_list()
    if stock_list is not None:
        print(f"✓ 获取成功，共 {len(stock_list)} 只股票")
    else:
        print("✗ 获取失败")
    
    print("\n" + "="*80)
    print("测试3: 查询单个股票信息")
    print("="*80)
    if stock_list is not None and not stock_list.empty:
        test_code = stock_list.iloc[0]['code']
        stock_info = get_stock_info(test_code)
        if stock_info:
            print(f"✓ 查询成功: {stock_info}")
        else:
            print(f"✗ 查询失败: {test_code}")
    
    print("\n" + "="*80)
    print("测试4: 强制更新")
    print("="*80)
    stock_list = get_stock_list(force_update=True)
    if stock_list is not None:
        print(f"✓ 强制更新成功，共 {len(stock_list)} 只股票")
    else:
        print("✗ 强制更新失败")

if __name__ == "__main__":
    test_stock_list_cache()

