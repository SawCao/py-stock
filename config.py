#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时任务配置文件
用户可以在此配置定时任务的执行时间和其他参数
"""

import os
from datetime import datetime

# 定时任务配置
SCHEDULER_CONFIG = {
    # 任务执行时间配置
    'daily_job_time': {
        'hour': 9,      # 小时 (0-23)
        'minute': 30,   # 分钟 (0-59)
        'second': 0,    # 秒 (0-59)
    },
    
    # 时区设置
    'timezone': 'Asia/Shanghai',
    
    # 日志配置
    'log_level': 'INFO',  # DEBUG, INFO, WARNING, ERROR
    'log_file': 'scheduler.log',
    'log_max_size': '10MB',
    'log_backup_count': 5,
    
    # 任务重试配置
    'max_retries': 3,
    'retry_delay': 300,  # 重试延迟（秒）
    
    # 任务超时配置
    'job_timeout': 3600,  # 任务超时时间（秒）
    
    # 错误通知配置（可选）
    'enable_email_notification': False,
    'email_config': {
        'smtp_server': 'smtp.gmail.com',
        'smtp_port': 587,
        'username': 'your_email@gmail.com',
        'password': 'your_password',
        'to_email': 'recipient@gmail.com'
    }
}

# 数据库配置（如果需要）
DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 3306)),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'stock_data')
}

# 任务配置
JOB_CONFIG = {
    # 是否启用每日任务
    'enable_daily_job': True,
    
    # 是否在程序启动时立即执行一次
    'run_on_startup': False,
    
    # 是否在错过执行时间后补执行
    'coalesce': True,
    
    # 最大并发实例数
    'max_instances': 1,
    
    # 容错时间（秒）
    'misfire_grace_time': 300
}

# 测试配置
TEST_CONFIG = {
    # 测试模式下的执行间隔（秒）
    'test_interval': 60,
    
    # 测试模式下的最大执行次数
    'max_test_runs': 1
}
