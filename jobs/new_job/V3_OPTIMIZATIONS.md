# Baostock 数据采集脚本 V3 优化记录

**更新日期**: 2026-04-19
**相关文件**:
1. `jobs/new_job/daily_job_baostock_5min_v3.py` (由 `v2` 升级)
2. `jobs/new_job/turnover_rise_baostock_v3.py` (由 `_optimized` 升级)

## 问题背景
之前的脚本（V2 和 optimized 版本）在后台定时运行（crontab）时，经常出现以下问题：
1. **进程卡死与堆叠**：脚本有时会永远在后台运行而不停止，导致每天产生的新进程堆积。
2. **CPU 与内存占用高**：卡死的进程逐渐消耗系统资源，部分循环逻辑在遇到网络异常时可能导致 CPU 飙升。
3. **执行时间极长**：数据入库采用逐行插入（`cursor.execute`），对于全市场 5000 多只股票，这种数据库高频 I/O 操作极为耗时。

## 优化与修复内容

### 1. 引入全局网络超时机制 (Socket Timeout)
- **原因**：Baostock 底层使用 Python 的 `socket` 模块进行网络通信，默认没有超时时间。当服务器负载高或网络丢包时，网络请求会永远阻塞。
- **修复**：在脚本头部引入 `socket` 模块，并设置 `socket.setdefaulttimeout(30)`，强制所有底层网络请求在 30 秒无响应后抛出超时异常，防止进程假死。

### 2. 引入看门狗机制 (Watchdog via Signal)
- **原因**：某些复杂的内部逻辑（如 Baostock 内部处理）可能会在不触发网络超时的前提下陷入无限等待。
- **修复**：利用 Linux 的 `signal` 模块，在处理单只股票前设定 120 秒的报警定时器（`signal.alarm(120)`）。如果处理该股票的时间超过 120 秒，系统将强制抛出自定义的 `TimeoutException`，强行中断当前股票的处理，记录错误日志，并自动重新登录 Baostock 以恢复连接状态。

### 3. 防御性死循环保护
- **原因**：在获取 Baostock 数据时使用的 `while rs.next():` 循环，若网络状态异常导致 `next()` 错误地持续返回 `True` 但无有效数据，会导致死循环，使 CPU 占用率达到 100%。
- **修复**：在 `while` 循环中引入了 `max_loops = 5000` 的计数器限制。一旦循环次数超过合理范围，立刻强行 `break` 跳出循环并记录错误。

### 4. 数据库批量插入优化 (Batch Insert)
- **原因**：`turnover_rise_baostock_optimized.py` 原本使用 `iterrows()` 遍历 DataFrame 并逐条执行 `cursor.execute` 插入，网络 I/O 成本极高。
- **修复**：
  - 将逐条插入重构为使用 `cursor.executemany` 的批量插入，极大地提升了数据库写入性能，同时保留了 `ON DUPLICATE KEY UPDATE` 的防冲突特性。
  - 增加了降级机制：如果批量插入意外失败（例如因为某一条数据的特定字段导致整体约束冲突），代码会自动降级回退到逐条插入，确保数据的完整性。
  - **验证**：编写并执行了 `test_insertion.py` 专门验证了批量插入与更新机制的正确性。

## 后续建议
- 请将 `crontab` 或相关调度配置中的脚本路径更新为带有 `_v3.py` 后缀的新脚本。
- 可以定期观察 `logs` 目录下的运行日志，查看是否有股票频繁触发 `TimeoutException` 看门狗拦截。