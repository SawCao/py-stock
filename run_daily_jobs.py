#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import logging
from datetime import datetime

# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import jobs
from jobs import turnover_rise_baostock, daily_job_baostock_5min

# Configure logging
log_dir = "/app/log"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, f"daily_jobs_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def run_jobs():
    """Runs the daily jobs."""
    logger.info("Starting daily jobs...")
    
    try:
        logger.info("Executing turnover_rise_baostock.stat_all()...")
        turnover_rise_baostock.stat_all()
        logger.info("turnover_rise_baostock.stat_all() completed.")
    except Exception as e:
        logger.error(f"Error executing turnover_rise_baostock.stat_all(): {e}", exc_info=True)

    try:
        logger.info("Executing daily_job_baostock_5min.stat_all()...")
        current_time = datetime.now()
        daily_job_baostock_5min.stat_all(current_time)
        logger.info("daily_job_baostock_5min.stat_all() completed.")
    except Exception as e:
        logger.error(f"Error executing daily_job_baostock_5min.stat_all(): {e}", exc_info=True)

    logger.info("Daily jobs finished.")

if __name__ == '__main__':
    run_jobs()