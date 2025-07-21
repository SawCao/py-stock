# 增强版Python定时任务调度器

## 概述

本项目使用**APScheduler**框架替代传统的crontab，实现更灵活、更强大的Python定时任务调度系统。

## 主要特性

- ✅ **纯Python实现**：无需依赖系统crontab
- ✅ **分钟级调度**：支持每分钟执行数据抓取
- ✅ **小时级调度**：支持每小时执行数据更新
- ✅ **特定时间点**：支持工作日9:30和15:30的特定任务
- ✅ **任务监控**：完整的日志记录和错误处理
- ✅ **灵活配置**：通过配置文件调整任务参数
- ✅ **高可靠性**：支持任务失败重试和异常处理

## 文件结构

```
├── enhanced_scheduler.py    # 增强版调度器主程序
├── Dockerfile.job.new      # 新的Docker镜像（移除crontab依赖）
├── config.py               # 配置文件
├── requirements.txt        # Python依赖
└── jobs/                   # 任务脚本目录
    ├── daily_job_dongcai.py    # 分钟级数据抓取
    ├── turnover_rise.py        # 小时级数据更新
    └── common.py              # 开盘/收盘数据处理
```

## 定时任务配置

| 任务名称 | 执行频率 | 对应脚本 | 功能描述 |
|---------|----------|----------|----------|
| 分钟级数据抓取 | 每分钟 | `daily_job_dongcai.py` | 实时抓取分钟级股票数据 |
| 小时级数据更新 | 每小时整点 | `turnover_rise.py` | 更新小时级统计数据 |
| 开盘前数据准备 | 工作日9:30 | `common.py` | 开盘前数据预处理 |
| 收盘后数据整理 | 工作日15:30 | `common.py` | 收盘后数据整理分析 |

## 使用方法

### 1. 直接运行

```bash
python enhanced_scheduler.py
```

### 2. Docker运行

```bash
# 构建镜像
docker build -f Dockerfile.job.new -t stock-scheduler-enhanced .

# 运行容器
docker run -d \
  --name stock-scheduler \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/data:/app/data \
  stock-scheduler-enhanced
```

### 3. Docker Compose集成

更新`docker-compose.yml`中的job服务：

```yaml
  job:
    build:
      context: .
      dockerfile: Dockerfile.job.new
    container_name: stock-job-enhanced
    depends_on:
      - mysql
      - redis
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    environment:
      - TZ=Asia/Shanghai
    restart: unless-stopped
```

## 配置说明

### 调度器配置 (`config.py`)

```python
SCHEDULER_CONFIG = {
    'log_level': 'INFO',
    'log_file': '/app/logs/scheduler.log',
    'timezone': 'Asia/Shanghai',
    'daily_job_time': {
        'hour': 9,
        'minute': 30,
        'second': 0
    }
}

JOB_CONFIG = {
    'coalesce': True,           # 合并错过的任务
    'max_instances': 1,         # 最大并发实例数
    'misfire_grace_time': 300,  # 任务错过执行的宽限时间（秒）
    'run_on_startup': False     # 启动时是否立即执行
}
```

## 日志监控

所有任务执行日志保存在`/app/logs/scheduler.log`中，包含：
- 任务开始和结束时间
- 执行结果（成功/失败）
- 错误信息和堆栈跟踪
- 下次执行时间预告

## 任务管理

### 查看任务状态
```bash
# 进入容器
docker exec -it stock-job-enhanced bash

# 查看日志
tail -f /app/logs/scheduler.log
```

### 手动触发任务
```python
# 在Python环境中
from enhanced_scheduler import minute_job_wrapper
minute_job_wrapper()  # 手动执行分钟级任务
```

## 优势对比

| 特性 | 传统crontab | APScheduler方案 |
|------|-------------|-----------------|
| 配置方式 | 文件配置 | Python代码配置 |
| 错误处理 | 简单日志 | 完整异常捕获 |
| 任务监控 | 需额外工具 | 内置日志系统 |
| 动态调整 | 需重启服务 | 支持运行时调整 |
| 依赖管理 | 系统级 | Python虚拟环境 |
| 跨平台 | Unix系统 | 全平台支持 |

## 故障排查

1. **任务不执行**：检查日志文件中的错误信息
2. **时间不准确**：确认容器时区设置正确
3. **内存泄漏**：监控容器内存使用情况
4. **数据库连接**：检查数据库连接配置

## 扩展建议

- 添加Web界面管理任务
- 集成Prometheus监控
- 支持任务执行结果通知
- 添加任务执行统计报表
