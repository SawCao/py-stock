#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版Python定时任务调度器
每天下午4点执行turnover_rise和daily_job_dongcai，并发送短信通知
"""

import os
import sys
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
import requests
import json

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

def turnover_rise_job():
    """执行turnover_rise任务"""
    try:
        logger.info("开始执行turnover_rise任务...")
        
        
        # 执行turnover_rise任务
        from jobs.turnover_rise import stat_all
        stat_all()
        
        logger.info("turnover_rise任务完成")
        
        
    except Exception as e:
        error_msg = f"turnover_rise任务执行失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        #sms_notifier.send_batch_sms(error_msg)
        raise

def daily_job_dongcai_task():
    """执行daily_job_dongcai任务"""
    try:
        logger.info("开始执行daily_job_dongcai任务...")
    
        
        # 执行daily_job_dongcai任务
        from jobs.daily_job_baostock_5min import stat_all
        current_time = datetime.now()
        stat_all(current_time)
        
        logger.info("daily_job_dongcai任务完成")
        
    except Exception as e:
        error_msg = f"daily_job_dongcai任务执行失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        #sms_notifier.send_batch_sms(error_msg)
        raise

def combined_daily_task():
    """每天下午4点执行的合并任务"""
    try:
        logger.info("开始执行每日股票数据更新任务...")
        
        # 发送开始通知
        #sms_notifier.send_batch_sms("每日股票数据更新任务开始执行 - 16:00")
        
        # 先执行turnover_rise
        logger.info("执行turnover_rise任务...")
        from jobs.turnover_rise import stat_all as turnover_rise_main
        turnover_rise_main()
        
        # 再执行daily_job_dongcai
        logger.info("执行daily_job_dongcai任务...")
        from jobs.daily_job_dongcai_old import stat_all as daily_job_main
        daily_job_main(datetime.now())
        
        logger.info("每日股票数据更新任务全部完成")
        
        # 发送完成通知
        #sms_notifier.send_batch_sms("每日股票数据更新任务全部完成 - 16:00")
        
    except Exception as e:
        error_msg = f"每日股票数据更新任务执行失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        #sms_notifier.send_batch_sms(error_msg)
        raise

def job_listener(event):
    """任务执行监听器"""
    if event.exception:
        logger.error(f"任务执行失败: {event.job_id} - {event.exception}", exc_info=True)
        #sms_notifier.send_batch_sms(f"任务执行失败: {event.job_id}")
    else:
        logger.info(f"任务执行成功: {event.job_id}")

# 添加监听器
scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)

def setup_jobs():
    """配置所有定时任务"""
    
    # 每天下午4点执行合并任务（工作日）
    scheduler.add_job(
        combined_daily_task,
        'cron',
        day_of_week='mon-fri',
        hour=16,
        minute=0,
        second=0,
        id='daily_combined_task',
        name='每日股票数据更新任务',
        coalesce=JOB_CONFIG['coalesce'],
        max_instances=JOB_CONFIG['max_instances'],
        misfire_grace_time=JOB_CONFIG['misfire_grace_time']
    )

def list_all_jobs():
    """列出所有已配置的任务"""
    logger.info("已配置的任务列表:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name} ({job.id})")
        logger.info(f"    触发器: {job.trigger}")
        logger.info(f"    下次执行时间: {job.next_run_time}")
        logger.info("-" * 40)

def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("增强版Python定时任务调度器启动")
    logger.info("当前时间: %s", datetime.now())
    
    # 配置所有任务
    setup_jobs()
    
    # 列出所有任务
    list_all_jobs()
    
    logger.info("=" * 60)
    
    try:
        # 启动调度器
        logger.info("正在启动调度器...")
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("接收到退出信号，正在关闭调度器...")
        scheduler.shutdown()
        logger.info("调度器已安全关闭")
    except Exception as e:
        logger.error(f"调度器启动失败: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()
