#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
"""
A股1分钟级数据收集任务。

基于 daily_job_baostock_5min_v3.py 复用主流程、入库逻辑和 Gain 计算，
但底层数据源替换为 akshare 的 1分钟 K 线，不再使用 baostock。
"""

import datetime
import logging
import os
import time
from typing import Optional

import pandas as pd
import akshare as ak

import daily_job_baostock_5min_v3 as base_job

TARGET_TABLE = "stock_zh_a_minute_ol_1"


def setup_logging() -> logging.Logger:
    os.makedirs("logs", exist_ok=True)
    logger = logging.getLogger("stock_minute_data_1min_v1")
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    today = datetime.datetime.now().strftime("%Y%m%d")
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - [%(levelname)s] - %(funcName)s:%(lineno)d - %(message)s"
    )
    simple_formatter = logging.Formatter("%(asctime)s - [%(levelname)s] - %(message)s")

    file_handler = logging.FileHandler(f"logs/stock_minute_1min_{today}.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)

    error_handler = logging.FileHandler(
        f"logs/stock_minute_1min_errors_{today}.log", encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)
    return logger


def login_baostock(self) -> None:
    # 占位：不再需要登录
    self.bs_logged_in = True


def logout_baostock(self, timeout_sec: int = 5) -> None:
    # 占位：不再需要登出
    self.bs_logged_in = False


def fetch_minute_data(self, code: str, name: str, retry_count: int = 0) -> Optional[pd.DataFrame]:
    try:
        # Akshare 频控可能需要一点延时
        time.sleep(base_job.CONFIG.get("SLEEP_BETWEEN_STOCKS", 1))

        current_date = datetime.datetime.now()
        start_date_str = (current_date - datetime.timedelta(days=self.query_days)).strftime("%Y-%m-%d 09:00:00")
        end_date_str = current_date.strftime("%Y-%m-%d 15:30:00")

        pure_code = code.split(".")[1] if "." in code else code

        base_job.logger.debug(
            f"    查询 {code} (akshare={pure_code}) 的数据范围: {start_date_str} ~ {end_date_str}"
        )

        data = ak.stock_zh_a_hist_min_em(
            symbol=pure_code,
            start_date=start_date_str,
            end_date=end_date_str,
            period="1",
            adjust="qfq"
        )

        if data is None or data.empty:
            base_job.logger.warning(f"  ⚠ {code} [{name}] 返回数据为空")
            return None

        # akshare 1分钟K线返回列：['时间', '开盘', '收盘', '最高', '最低', '成交量', '成交额', '均价']
        data = data.rename(columns={
            "时间": "day",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume"
        })
        
        data["day"] = pd.to_datetime(data["day"])

        required_cols = ["day", "open", "close", "high", "low", "volume"]
        if not all(col in data.columns for col in required_cols):
            base_job.logger.warning(f"  ⚠ {code} [{name}] 缺少必需列，当前列: {data.columns.tolist()}")
            return None

        data = data[required_cols].copy()
        data["name"] = pure_code
        data["rname"] = name

        numeric_cols = ["open", "close", "high", "low", "volume"]
        for col in numeric_cols:
            data[col] = pd.to_numeric(data[col], errors="coerce")

        if data[numeric_cols].isnull().any().any():
            base_job.logger.debug(f"    {code} [{name}] 发现NaN值，将删除包含NaN的行")
            data = data.dropna(subset=numeric_cols)

        if data.empty:
            base_job.logger.warning(f"  ⚠ {code} [{name}] 清洗后数据为空")
            return None

        base_job.logger.debug(f"    {code} [{name}] 获取到 {len(data)} 条1分钟记录")
        return data

    except Exception as e:
        if retry_count < base_job.CONFIG["RETRY_TIMES"]:
            base_job.logger.warning(
                f"  ⚠ {code} [{name}] 获取数据失败，重试 {retry_count + 1}/{base_job.CONFIG['RETRY_TIMES']}: {e}"
            )
            time.sleep(base_job.CONFIG["RETRY_DELAY"])
            return fetch_minute_data(self, code, name, retry_count + 1)

        base_job.logger.error(
            f"  ✗ {code} [{name}] 获取数据失败（已重试{base_job.CONFIG['RETRY_TIMES']}次）: {e}"
        )
        return None


def main() -> None:
    base_job.TARGET_TABLE = TARGET_TABLE
    base_job.logger = setup_logging()
    
    # 替换处理器方法
    base_job.StockDataProcessor.login_baostock = login_baostock
    base_job.StockDataProcessor.logout_baostock = logout_baostock
    base_job.StockDataProcessor.fetch_minute_data = fetch_minute_data

    args = base_job.parse_arguments()
    start_datetime = datetime.datetime.now()
    base_job.process_all_stocks(start_datetime, query_days=args.days)


if __name__ == "__main__":
    main()
