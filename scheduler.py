#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定时任务调度器
使用APScheduler框架来定时执行daily_job_dongcai.py
"""

import os
import sys
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 导入配置
from config import SCHEDULER_CONFIG, JOB_CONFIG

# 配置日志
logging.basicConfig(
    level=getattr(logging, SCHEDULER_CONFIG['log_level']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(SCHEDULER_CONFIG['log_file'], encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 创建调度器
scheduler = BlockingScheduler(timezone=SCHEDULER_CONFIG['timezone'])

def daily_job_wrapper():
    """包装daily_job_dongcai.py的执行"""
    try:
        logger.info("开始执行daily_job_dongcai.py...")
        
        # 导入并执行daily_job_dongcai的main函数
        from jobs.daily_job_dongcai import stat_all
        from jobs import common
        
        # 获取当前时间
        current_time = datetime.now()
        logger.info(f"执行时间: {current_time}")
        
        # 执行主要任务
        stat_all(current_time)
        
        logger.info("daily_job_dongcai.py执行完成")
        
    except Exception as e:
        logger.error(f"执行daily_job_dongcai.py时发生错误: {str(e)}", exc_info=True)
        raise

def job_listener(event):
    """任务执行监听器"""
    if event.exception:
        logger.error(f"任务执行失败: {event.job_id}", exc_info=True)
    else:
        logger.info(f"任务执行成功: {event.job_id}")

# 添加监听器
scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

# 配置定时任务
# 使用配置文件中的时间设置
job_time = SCHEDULER_CONFIG['daily_job_time']
scheduler.add_job(
    daily_job_wrapper,
    'cron',
    hour=job_time['hour'],
    minute=job_time['minute'],
    second=job_time['second'],
    id='daily_job_dongcai',
    name='每日东财数据更新任务',
    coalesce=JOB_CONFIG['coalesce'],
    max_instances=JOB_CONFIG['max_instances'],
    misfire_grace_time=JOB_CONFIG['misfire_grace_time']
)

# 如果配置了启动时立即执行
if JOB_CONFIG['run_on_startup']:
    logger.info("配置为启动时立即执行一次任务...")
    scheduler.add_job(
        daily_job_wrapper,
        'date',
        run_date=datetime.now(),
        id='startup_job',
        name='启动时执行任务'
    )

def main():
    """主函数"""
    logger.info("=" * 50)
    logger.info("定时任务调度器启动")
    logger.info("当前时间: %s", datetime.now())
    logger.info("任务列表:")
    
    # 列出所有任务
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name}: {job.trigger}")
    
    logger.info("=" * 50)
    
    try:
        # 启动调度器
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("接收到退出信号，正在关闭调度器...")
        scheduler.shutdown()
        logger.info("调度器已关闭")

if __name__ == '__main__':
    main()
