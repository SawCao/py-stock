#!/bin/bash

# 设置环境变量
export PYTHONPATH=/app
export DATABASE_URL=${DATABASE_URL:-mysql+pymysql://stock_user:stock_pass_2024@mysql:3306/stock_data}
export REDIS_URL=${REDIS_URL:-redis://redis:6379/0}

# 获取当前时间
CURRENT_TIME=$(date +"%Y-%m-%d %H:%M:%S")
echo "开始执行定时任务，当前时间: $CURRENT_TIME"

# 执行daily_job_main
echo "开始执行 daily_job_main..."
python -c "
from datetime import datetime
import sys
sys.path.append('/app')
from jobs.daily_job_dongcai import stat_all
try:
    print('正在执行 daily_job_main...')
    stat_all()
    print('daily_job_main 执行完成')
except Exception as e:
    print(f'daily_job_main 执行失败: {e}')
    sys.exit(1)
"

DAILY_JOB_STATUS=$?
if [ $DAILY_JOB_STATUS -ne 0 ]; then
    echo "daily_job_main 执行失败，退出码: $DAILY_JOB_STATUS"
    exit $DAILY_JOB_STATUS
fi

# 执行turnover_rise_main
echo "开始执行 turnover_rise_main..."
python -c "
import sys
sys.path.append('/app')
from jobs.turnover_rise import stat_all
try:
    print('正在执行 turnover_rise_main...')
    stat_all()
    print('turnover_rise_main 执行完成')
except Exception as e:
    print(f'turnover_rise_main 执行失败: {e}')
    sys.exit(1)
"

TURNOVER_RISE_STATUS=$?
if [ $TURNOVER_RISE_STATUS -ne 0 ]; then
    echo "turnover_rise_main 执行失败，退出码: $TURNOVER_RISE_STATUS"
    exit $TURNOVER_RISE_STATUS
fi

echo "所有任务执行完成，时间: $(date +"%Y-%m-%d %H:%M:%S")"
