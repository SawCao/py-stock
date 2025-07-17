import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np
from jobs.daily_job_dongcai import insert_minute
from libs import common

class TestInsertMinute(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # 创建测试表
        common.insert("""
        CREATE TABLE IF NOT EXISTS `stock_zh_a_minute_ol_4` (
          `day` datetime NOT NULL,
          `open` float DEFAULT NULL,
          `close` float DEFAULT NULL,
          `high` float DEFAULT NULL,
          `low` float DEFAULT NULL,
          `volume` float DEFAULT NULL,
          `name` varchar(255) NOT NULL,
          `rname` varchar(255) DEFAULT NULL,
          `Gain_5` float DEFAULT NULL,
          `Gain_6` float DEFAULT NULL,
          `Gain_7` float DEFAULT NULL,
          `Gain_8` float DEFAULT NULL,
          `Gain_9` float DEFAULT NULL,
          `Gain_10` float DEFAULT NULL,
          `Gain_15` float DEFAULT NULL,
          `Gain_20` float DEFAULT NULL,
          `Gain_30` float DEFAULT NULL,
          `Gain_60` float DEFAULT NULL,
          PRIMARY KEY (`name`,`day`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
    
    @classmethod
    def tearDownClass(cls):
        # 清理测试表
        common.insert("DROP TABLE IF EXISTS `stock_zh_a_minute_ol_4`;")
    
    @patch('akshare.stock_zh_a_hist_min_em')
    def test_insert_minute_success(self, mock_akshare):
        # 模拟akshare返回数据
        mock_data = pd.DataFrame({
            '时间': ['2023-01-01 09:30', '2023-01-01 09:31'],
            '开盘': [10.0, 10.1],
            '收盘': [10.1, 10.2],
            '最高': [10.2, 10.3],
            '最低': [9.9, 10.0],
            '成交量': [1000, 2000],
            '成交额': [10000, 20000],
            '最新价': [10.1, 10.2]
        })
        mock_akshare.return_value = mock_data
        
        # 执行测试
        insert_minute('600000', '浦发银行')
        
        # 验证数据是否插入
        result = common.select("SELECT * FROM stock_zh_a_minute_ol_4")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][6], '600000')  # name字段
        self.assertEqual(result[0][7], '浦发银行')  # rname字段
        
        # 验证涨幅计算
        self.assertGreater(result[1][8], 0)  # Gain_5应该大于0

    @patch('akshare.stock_zh_a_hist_min_em')
    def test_insert_minute_all_zero_gain(self, mock_akshare):
        # 模拟所有价格相同的数据（涨幅为0）
        mock_data = pd.DataFrame({
            '时间': ['2023-01-01 09:30', '2023-01-01 09:31'],
            '开盘': [10.0, 10.0],
            '收盘': [10.0, 10.0],
            '最高': [10.0, 10.0],
            '最低': [10.0, 10.0],
            '成交量': [1000, 2000],
            '成交额': [10000, 20000],
            '最新价': [10.0, 10.0]
        })
        mock_akshare.return_value = mock_data
        
        # 执行测试
        insert_minute('600000', '浦发银行')
        
        # 验证数据没有插入（因为涨幅全为0）
        result = common.select("SELECT * FROM stock_zh_a_minute_ol_4")
        self.assertEqual(len(result), 0)

if __name__ == '__main__':
    unittest.main()
