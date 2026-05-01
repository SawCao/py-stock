# A股分钟级数据收集系统 V2

## 📋 概述

这是 `daily_job_baostock_5min.py` 的重构版本，主要改进了代码结构、日志系统和异常处理机制。

## ✨ 主要改进

### 1. 使用股票列表缓存模块

- ✅ 从 `stock_list_cache.py` 获取股票列表
- ✅ 利用缓存机制，减少对数据源的请求
- ✅ 支持每周自动更新缓存

### 2. 独立的数据库管理

- ✅ 不依赖 `common` 模块
- ✅ 实现了 `DatabaseManager` 类，统一管理所有数据库操作
- ✅ 支持批量插入和逐条插入（失败时的备用方案）
- ✅ 使用连接池提高性能
- ✅ 自动创建数据表（如果不存在）
- ✅ 支持 ON DUPLICATE KEY UPDATE（避免重复数据）

### 3. 优化的日志系统

#### 三个日志级别：
- **详细日志文件**: `logs/stock_minute_v2_YYYYMMDD.log` - 记录所有调试信息
- **错误日志文件**: `logs/stock_minute_v2_errors_YYYYMMDD.log` - 只记录错误信息
- **控制台输出**: 显示关键进度信息

#### 日志特点：
- ✅ 清晰标识每只股票的处理状态（✓成功 / ✗失败 / ⚠警告）
- ✅ 详细记录失败原因和堆栈信息
- ✅ 任务结束时输出失败股票清单
- ✅ 进度提示（每50只股票）
- ✅ 时间预估（剩余处理时间）

#### 日志示例：
```
2024-01-20 18:00:01 - [INFO] - 开始执行A股分钟级数据收集任务
→ 处理股票: sh.600000 [浦发银行]
    查询 sh.600000 的数据范围: 2024-01-14 ~ 2024-01-20
    sh.600000 [浦发银行] 获取到 240 条记录
    sh.600000 [浦发银行] 计算了 6 个周期的Gain指标
  ✓ sh.600000 [浦发银行] 处理成功，插入 240 条记录

→ 处理股票: sh.600001 [邯郸钢铁]
  ✗ sh.600001 [邯郸钢铁] 获取数据失败（已重试3次）: Connection timeout

进度: 50/5000 (1.0%) | 成功: 48 | 失败: 2 | 跳过: 0 | 预计剩余: 98.5分钟

=================================================================================================
失败股票清单（共 2 只）:
=================================================================================================
1. sh.600001 [邯郸钢铁] - 原因: Connection timeout
2. sz.000002 [万科A] - 原因: 数据格式错误
```

### 4. 增强的异常处理

- ✅ 三层异常捕获：函数级、股票级、任务级
- ✅ 自动重试机制（可配置重试次数和延迟）
- ✅ 批量插入失败时自动降级为逐条插入
- ✅ 异常不会中断整个任务，只影响单只股票
- ✅ 详细的异常堆栈信息记录

### 5. 其他改进

- ✅ 面向对象设计，代码结构更清晰
- ✅ 配置集中管理
- ✅ 支持命令行参数（`--days` 控制查询天数，`--date` 指定基准日期）
- ✅ 灵活的时间范围控制（默认查询前6天，可自定义）
- ✅ 自动清理过期数据
- ✅ 进度实时显示
- ✅ 统计信息完善

## 📦 依赖

```bash
pip install pandas numpy pymysql sqlalchemy baostock akshare
```

## 🔧 配置

### 环境变量

```bash
export MYSQL_HOST="127.0.0.1"
export MYSQL_PORT="3306"
export MYSQL_USER="root"
export MYSQL_PWD="mysqldb"
export MYSQL_DB="stock_data"
```

### 配置参数

在代码中的 `CONFIG` 字典：

```python
CONFIG = {
    'MAX_WORKERS': 1,              # 并发线程数（建议为1）
    'RETRY_TIMES': 3,              # 重试次数
    'RETRY_DELAY': 2,              # 重试延迟(秒)
    'CLEANUP_DAYS': 100,           # 数据保留天数
    'BATCH_SIZE': 500,             # 批处理大小
    'TIMEOUT': 30,                 # 请求超时时间(秒)
    'SLEEP_BETWEEN_STOCKS': 1,    # 股票间延迟(秒)
    'QUERY_DAYS': 6,               # 查询最近N天的数据（默认6天）
}
```

## 🚀 使用方法

### 基本用法

```bash
# 使用默认参数（查询前6天数据）
python daily_job_baostock_5min_v2.py

# 查询前10天数据
python daily_job_baostock_5min_v2.py --days 10

# 指定日期并查询前7天数据
python daily_job_baostock_5min_v2.py --date 20241020 --days 7

# 简写形式
python daily_job_baostock_5min_v2.py -d 10

# 查看帮助
python daily_job_baostock_5min_v2.py --help
```

### 命令行参数

| 参数 | 简写 | 类型 | 默认值 | 说明 |
|-----|------|------|--------|------|
| `--days` | `-d` | int | 6 | 查询最近N天的数据 |
| `--date` | - | str | 当前日期 | 指定基准日期（格式: YYYYMMDD）|

### 定时任务

在 crontab 中配置：

```bash
# 每天18:00执行（使用默认参数，查询前6天数据）
0 18 * * * cd /app/jobs/new_job && python daily_job_baostock_5min_v2.py >> /app/logs/cron_v2.log 2>&1

# 每天18:00执行（查询前10天数据）
0 18 * * * cd /app/jobs/new_job && python daily_job_baostock_5min_v2.py --days 10 >> /app/logs/cron_v2.log 2>&1
```

## 📊 数据表结构

```sql
CREATE TABLE stock_zh_a_minute_ol_4 (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    day DATETIME NOT NULL COMMENT '时间',
    name VARCHAR(20) NOT NULL COMMENT '股票代码',
    rname VARCHAR(50) COMMENT '股票名称',
    open DECIMAL(10, 3) COMMENT '开盘价',
    close DECIMAL(10, 3) COMMENT '收盘价',
    high DECIMAL(10, 3) COMMENT '最高价',
    low DECIMAL(10, 3) COMMENT '最低价',
    volume BIGINT COMMENT '成交量',
    Gain_5 DECIMAL(10, 6) COMMENT '5周期波动率',
    Gain_10 DECIMAL(10, 6) COMMENT '10周期波动率',
    Gain_15 DECIMAL(10, 6) COMMENT '15周期波动率',
    Gain_20 DECIMAL(10, 6) COMMENT '20周期波动率',
    Gain_30 DECIMAL(10, 6) COMMENT '30周期波动率',
    Gain_60 DECIMAL(10, 6) COMMENT '60周期波动率',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_name_day (name, day),
    INDEX idx_day (day),
    INDEX idx_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 🔍 日志查看

### 查看实时日志

```bash
# 查看详细日志
tail -f logs/stock_minute_v2_20240120.log

# 查看错误日志
tail -f logs/stock_minute_v2_errors_20240120.log

# 只看失败的股票
grep "✗" logs/stock_minute_v2_20240120.log
```

### 统计失败数量

```bash
# 统计失败的股票数量
grep "处理失败" logs/stock_minute_v2_20240120.log | wc -l

# 查看失败股票清单
grep -A 100 "失败股票清单" logs/stock_minute_v2_20240120.log
```

## 📈 性能优化建议

1. **并发数**: 建议设置为1，避免 baostock 限流
2. **批处理**: 默认500条记录一批，可根据数据库性能调整
3. **重试策略**: 默认重试3次，间隔2秒
4. **数据清理**: 默认保留100天数据，可根据存储空间调整

## ⚠️ 注意事项

1. **Baostock 限流**: 
   - 建议设置 `SLEEP_BETWEEN_STOCKS >= 1` 秒
   - 每200只股票重新登录一次

2. **数据库连接**:
   - 使用连接池管理
   - 批量插入失败会自动降级为逐条插入

3. **日志文件**:
   - 按日期分文件存储
   - 注意定期清理旧日志文件

4. **错误处理**:
   - 单只股票失败不影响其他股票
   - 所有失败会在任务结束时汇总显示

## 🆚 与旧版本对比

| 特性 | 旧版本 | V2版本 |
|-----|-------|--------|
| 股票列表 | akshare直接获取 | 使用缓存模块 |
| 数据库操作 | 依赖common模块 | 独立管理 |
| 日志级别 | 单一日志文件 | 详细日志+错误日志+控制台 |
| 失败记录 | 散落在日志中 | 任务结束统一汇总 |
| 异常处理 | 基础try-except | 三层异常捕获+自动重试 |
| 进度显示 | 无 | 实时进度+时间预估 |
| 批量插入 | 无 | 支持+失败降级 |
| 代码结构 | 函数式 | 面向对象 |

## 🐛 故障排查

### 问题1: 无法连接数据库

```bash
# 检查环境变量
echo $MYSQL_HOST
echo $MYSQL_USER

# 测试数据库连接
mysql -h $MYSQL_HOST -P $MYSQL_PORT -u $MYSQL_USER -p$MYSQL_PWD -e "SELECT 1"
```

### 问题2: Baostock 登录失败

```bash
# 检查网络连接
ping www.baostock.com

# 手动测试登录
python -c "import baostock as bs; print(bs.login())"
```

### 问题3: 大量股票失败

查看错误日志文件，分析失败原因：
```bash
grep "原因:" logs/stock_minute_v2_errors_20240120.log | sort | uniq -c | sort -rn
```

## 📝 开发计划

- [ ] 支持多线程并发（需要解决baostock限流问题）
- [ ] 增加数据质量检查
- [ ] 支持数据补录功能
- [ ] 添加邮件/钉钉通知
- [ ] 性能监控和报表

## 📧 联系方式

如有问题或建议，请查看项目文档或联系开发团队。

---

**最后更新**: 2024-01-20
**版本**: 2.0.0

