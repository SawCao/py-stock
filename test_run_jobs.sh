#!/bin/bash

# 测试脚本 - 在docker容器内测试run_jobs.sh

echo "测试run_jobs.sh脚本..."

# 检查脚本是否存在
if [ ! -f "/app/run_jobs.sh" ]; then
    echo "错误: run_jobs.sh 脚本不存在"
    exit 1
fi

# 检查脚本是否有执行权限
if [ ! -x "/app/run_jobs.sh" ]; then
    echo "错误: run_jobs.sh 没有执行权限"
    exit 1
fi

# 检查Python模块是否可以导入
echo "检查Python模块导入..."
python -c "
import sys
sys.path.append('/app')
try:
    from jobs.daily_job_dongcai import stat_all
    print('✓ daily_job_dongcai 模块导入成功')
except Exception as e:
    print(f'✗ daily_job_dongcai 模块导入失败: {e}')
    sys.exit(1)

try:
    from jobs.turnover_rise import stat_all
    print('✓ turnover_rise 模块导入成功')
except Exception as e:
    print(f'✗ turnover_rise 模块导入失败: {e}')
    sys.exit(1)
"

echo "所有检查通过，run_jobs.sh 可以正常使用"
