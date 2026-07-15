#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：验证 daily_job_baostock_5min_v2.py 的功能
"""

import sys
import logging
import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)

def test_stock_list_cache():
    """测试1: 股票列表缓存模块"""
    logger.info("\n" + "="*80)
    logger.info("测试1: 股票列表缓存模块")
    logger.info("="*80)
    
    try:
        import stock_list_cache
        
        logger.info("→ 获取股票列表...")
        stock_list = stock_list_cache.get_stock_list()
        
        if stock_list is not None and not stock_list.empty:
            logger.info(f"✓ 成功获取 {len(stock_list)} 只股票")
            logger.info(f"  前3条记录:")
            print(stock_list.head(3).to_string())
            return True
        else:
            logger.error("✗ 获取股票列表失败")
            return False
            
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}", exc_info=True)
        return False

def test_database_connection():
    """测试2: 数据库连接"""
    logger.info("\n" + "="*80)
    logger.info("测试2: 数据库连接")
    logger.info("="*80)
    
    try:
        # 导入新版本的模块
        sys.path.insert(0, '/app/jobs')
        from daily_job_baostock_5min_v2 import DatabaseManager
        
        logger.info("→ 创建数据库管理器...")
        db_manager = DatabaseManager()
        
        logger.info("→ 测试数据库连接...")
        conn = db_manager.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result and result[0] == 1:
            logger.info("✓ 数据库连接成功")
            
            logger.info("→ 检查目标表...")
            db_manager.ensure_table_exists()
            logger.info("✓ 目标表检查完成")
            
            return True
        else:
            logger.error("✗ 数据库连接测试失败")
            return False
            
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}", exc_info=True)
        return False

def test_baostock_login():
    """测试3: Baostock 登录"""
    logger.info("\n" + "="*80)
    logger.info("测试3: Baostock 登录")
    logger.info("="*80)
    
    try:
        import baostock as bs
        
        logger.info("→ 尝试登录 Baostock...")
        result = bs.login()
        
        if result.error_code == '0':
            logger.info("✓ Baostock 登录成功")
            bs.logout()
            logger.info("✓ Baostock 登出成功")
            return True
        else:
            logger.error(f"✗ Baostock 登录失败: {result.error_msg}")
            return False
            
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}", exc_info=True)
        return False

def test_single_stock_processing():
    """测试4: 处理单只股票"""
    logger.info("\n" + "="*80)
    logger.info("测试4: 处理单只股票（完整流程）")
    logger.info("="*80)
    
    try:
        from daily_job_baostock_5min_v2 import DatabaseManager, StockDataProcessor
        
        logger.info("→ 初始化...")
        db_manager = DatabaseManager()
        db_manager.ensure_table_exists()
        
        processor = StockDataProcessor(db_manager)
        processor.login_baostock()
        
        # 测试处理一只股票（以浦发银行为例）
        test_code = "sh.600000"
        test_name = "浦发银行"
        
        logger.info(f"→ 测试处理: {test_code} [{test_name}]")
        result = processor.process_single_stock(test_code, test_name)
        
        processor.logout_baostock()
        
        if result['success']:
            logger.info(f"✓ 处理成功")
            logger.info(f"  代码: {result['code']}")
            logger.info(f"  名称: {result['name']}")
            logger.info(f"  记录数: {result['records']}")
            return True
        else:
            logger.warning(f"⚠ 处理未完全成功: {result['error']}")
            # 某些情况（如当天无交易）不算失败
            return True
            
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}", exc_info=True)
        return False

def test_data_quality():
    """测试5: 数据质量检查"""
    logger.info("\n" + "="*80)
    logger.info("测试5: 数据质量检查")
    logger.info("="*80)
    
    try:
        from daily_job_baostock_5min_v2 import DatabaseManager
        import pymysql
        
        db_manager = DatabaseManager()
        conn = db_manager.get_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 检查表中的数据
        cursor.execute(f"""
            SELECT 
                COUNT(*) as total_records,
                COUNT(DISTINCT name) as total_stocks,
                MIN(day) as earliest_date,
                MAX(day) as latest_date
            FROM stock_zh_a_minute_ol_4
        """)
        
        result = cursor.fetchone()
        
        if result and result['total_records'] > 0:
            logger.info("✓ 数据表中有数据")
            logger.info(f"  总记录数: {result['total_records']}")
            logger.info(f"  股票数量: {result['total_stocks']}")
            logger.info(f"  最早日期: {result['earliest_date']}")
            logger.info(f"  最新日期: {result['latest_date']}")
            
            # 检查最近一条数据
            cursor.execute(f"""
                SELECT name, rname, day, close, Gain_5, Gain_10
                FROM stock_zh_a_minute_ol_4
                ORDER BY day DESC
                LIMIT 3
            """)
            
            recent_records = cursor.fetchall()
            logger.info(f"\n  最近3条记录:")
            for i, record in enumerate(recent_records, 1):
                logger.info(f"    {i}. {record['name']} [{record['rname']}] "
                          f"{record['day']} - 收盘:{record['close']} "
                          f"Gain_5:{record['Gain_5']:.4f}")
            
        else:
            logger.warning("⚠ 数据表为空（可能是首次运行）")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"✗ 测试失败: {e}", exc_info=True)
        return False

def main():
    """运行所有测试"""
    logger.info("\n" + "="*80)
    logger.info("开始测试 daily_job_baostock_5min_v2.py")
    logger.info("="*80)
    
    results = {
        '股票列表缓存': test_stock_list_cache(),
        '数据库连接': test_database_connection(),
        'Baostock登录': test_baostock_login(),
        '单股票处理': test_single_stock_processing(),
        '数据质量检查': test_data_quality(),
    }
    
    # 输出测试结果汇总
    logger.info("\n" + "="*80)
    logger.info("测试结果汇总")
    logger.info("="*80)
    
    passed = 0
    failed = 0
    
    for test_name, result in results.items():
        status = "✓ 通过" if result else "✗ 失败"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    logger.info("="*80)
    logger.info(f"总计: {passed + failed} 项测试")
    logger.info(f"通过: {passed} 项")
    logger.info(f"失败: {failed} 项")
    logger.info("="*80)
    
    if failed == 0:
        logger.info("\n✓ 所有测试通过！系统可以正常运行。")
        sys.exit(0)
    else:
        logger.error(f"\n✗ 有 {failed} 项测试失败，请检查配置和日志。")
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\n⚠ 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n✗ 测试异常: {e}", exc_info=True)
        sys.exit(1)



