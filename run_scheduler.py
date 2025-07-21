#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时任务启动脚本
提供多种运行模式：正常模式、测试模式、单次执行模式
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def run_normal_mode():
    """正常运行模式 - 启动定时调度器"""
    print("启动定时任务调度器...")
    print("按 Ctrl+C 停止")
    os.system(f"{sys.executable} scheduler.py")

def run_test_mode():
    """测试模式 - 立即执行一次任务"""
    print("测试模式：立即执行一次daily_job_dongcai.py...")
    
    try:
        from jobs.daily_job_dongcai import stat_all
        from jobs import common
        
        current_time = datetime.now()
        print(f"执行时间: {current_time}")
        
        stat_all(current_time)
        print("测试执行完成！")
        
    except Exception as e:
        print(f"测试执行失败: {str(e)}")
        import traceback
        traceback.print_exc()

def run_once_mode():
    """单次执行模式 - 执行一次后退出"""
    print("单次执行模式...")
    cf()

def main():
    parser = argparse.ArgumentParser(description='定时任务管理脚本')
    parser.add_argument(
        'mode',
        choices=['start', 'test', 'once'],
        help='运行模式: start(启动定时器), test(测试执行), once(单次执行)'
    )
    
    args = parser.parse_args()
    
    if args.mode == 'start':
        run_normal_mode()
    elif args.mode == 'test':
        run_test_mode()
    elif args.mode == 'once':
        run_once_mode()

if __name__ == '__main__':
    main()
