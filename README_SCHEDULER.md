# Python定时任务框架使用说明

本项目使用APScheduler框架实现了定时执行`daily_job_dongcai.py`的功能。

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 启动定时任务调度器

```bash
# 启动定时器（后台运行）
python scheduler.py

# 或者使用启动脚本
python run_scheduler.py start
```

### 2. 测试任务执行

```bash
# 立即执行一次任务（测试用）
python run_scheduler.py test

# 或者单次执行模式
python run_scheduler.py once
```

### 3. 配置定时任务

编辑`config.py`文件来自定义定时任务的执行时间：

```python
# 修改任务执行时间（默认每天9:30）
'daily_job_time': {
    'hour': 9,      # 小时 (0-23)
    'minute': 30,   # 分钟 (0-59)
    'second': 0,    # 秒 (0-59)
}
```

## 文件说明

- `scheduler.py`: 主调度器文件，包含APScheduler配置
- `config.py`: 配置文件，可自定义执行时间和其他参数
- `run_scheduler.py`: 启动脚本，提供多种运行模式
- `requirements.txt`: 依赖包列表
- `scheduler.log`: 日志文件（自动生成）

## 运行模式

### 正常模式
```bash
python scheduler.py
```
- 按照配置的时间每天定时执行
- 默认每天上午9:30执行
- 日志记录在`scheduler.log`

### 测试模式
```bash
python run_scheduler.py test
```
- 立即执行一次任务
- 用于验证任务是否能正常运行

### 单次执行模式
```bash
python run_scheduler.py once
```
- 执行一次后退出
- 适合手动触发任务

## 高级配置

### 修改执行时间
编辑`config.py`中的`SCHEDULER_CONFIG['daily_job_time']`：

```python
# 每天下午3点执行
'daily_job_time': {
    'hour': 15,
    'minute': 0,
    'second': 0,
}
```

### 日志配置
```python
# 修改日志级别
'log_level': 'DEBUG',  # DEBUG, INFO, WARNING, ERROR

# 修改日志文件
'log_file': 'my_scheduler.log'
```

### 任务容错配置
```python
# 错过执行时间后的容错时间（秒）
'misfire_grace_time': 300  # 默认5分钟
```

## 使用Docker运行

如果使用Docker，可以修改`docker-compose.yml`添加定时任务服务：

```yaml
scheduler:
  build: .
  command: python scheduler.py
  volumes:
    - .:/app
  depends_on:
    - db
  environment:
    - DB_HOST=db
    - DB_USER=root
    - DB_PASSWORD=yourpassword
```

## 常见问题

### 1. 任务没有按时执行
- 检查系统时间是否正确
- 查看`scheduler.log`日志文件
- 确认配置文件中的时间设置

### 2. 任务执行失败
- 检查数据库连接
- 确认`jobs/daily_job_dongcai.py`能独立运行
- 查看详细日志信息

### 3. 如何停止调度器
- 按`Ctrl+C`优雅停止
- 或者使用`kill`命令终止进程

## 监控和日志

### 查看实时日志
```bash
tail -f scheduler.log
```

### 查看任务状态
在Python交互环境中：
```python
from scheduler import scheduler
for job in scheduler.get_jobs():
    print(f"{job.name}: {job.next_run_time}")
```

## 扩展功能

### 添加新的定时任务
在`scheduler.py`中添加：

```python
def new_job():
    # 新任务逻辑
    pass

scheduler.add_job(
    new_job,
    'cron',
    hour=12,
    minute=0,
    id='new_daily_job',
    name='新任务'
)
