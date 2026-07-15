#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同步股票行业板块和概念板块映射。

数据源：Akshare 东方财富板块接口
- stock_board_industry_name_em / stock_board_industry_cons_em
- stock_board_concept_name_em / stock_board_concept_cons_em
"""

import logging
import os
import time
from typing import Iterable, Optional

import akshare as ak
import pandas as pd
import pymysql


MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PWD = os.environ.get("MYSQL_PWD", "mysqldb")
MYSQL_DB = os.environ.get("MYSQL_DB", "stock_data")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))

REQUEST_SLEEP_SECONDS = float(os.environ.get("STOCK_BOARD_SYNC_SLEEP_SECONDS", 0.2))


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("stock_board_sync")


def get_db_connection() -> pymysql.Connection:
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PWD,
        database=MYSQL_DB,
        port=MYSQL_PORT,
        charset="utf8mb4",
    )


def ensure_tables() -> None:
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_board_catalog (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                board_type VARCHAR(20) NOT NULL COMMENT 'industry 或 concept',
                board_code VARCHAR(32) NOT NULL COMMENT '东方财富板块代码',
                board_name VARCHAR(128) NOT NULL COMMENT '板块名称',
                source VARCHAR(32) NOT NULL DEFAULT 'akshare_em',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_board_type_code (board_type, board_code),
                KEY idx_board_type_name (board_type, board_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票板块目录';
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS stock_board_membership (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                board_type VARCHAR(20) NOT NULL COMMENT 'industry 或 concept',
                board_code VARCHAR(32) NOT NULL COMMENT '东方财富板块代码',
                board_name VARCHAR(128) NOT NULL COMMENT '板块名称',
                stock_code VARCHAR(10) NOT NULL COMMENT '6位股票代码',
                stock_name VARCHAR(64) DEFAULT NULL COMMENT '股票名称',
                source VARCHAR(32) NOT NULL DEFAULT 'akshare_em',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_board_stock (board_type, board_code, stock_code),
                KEY idx_stock_code (stock_code),
                KEY idx_board_type_name (board_type, board_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票板块成员映射';
            """
        )
        conn.commit()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def normalize_stock_code(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith(("sh.", "sz.", "bj.")):
        text = text.split(".", 1)[1]
    return text.zfill(6) if text.isdigit() else text


def fetch_board_catalog(board_type: str) -> pd.DataFrame:
    if board_type == "industry":
        df = ak.stock_board_industry_name_em()
    elif board_type == "concept":
        df = ak.stock_board_concept_name_em()
    else:
        raise ValueError(f"unsupported board_type: {board_type}")

    df = df.rename(columns={"板块代码": "board_code", "板块名称": "board_name"})
    df = df[["board_code", "board_name"]].copy()
    df["board_type"] = board_type
    df["source"] = "akshare_em"
    return df


def fetch_board_members(board_type: str, board_name: str, board_code: str) -> pd.DataFrame:
    if board_type == "industry":
        df = ak.stock_board_industry_cons_em(symbol=board_code)
    elif board_type == "concept":
        df = ak.stock_board_concept_cons_em(symbol=board_code)
    else:
        raise ValueError(f"unsupported board_type: {board_type}")

    df = df.rename(columns={"代码": "stock_code", "名称": "stock_name"})
    df = df[["stock_code", "stock_name"]].copy()
    df["stock_code"] = df["stock_code"].map(normalize_stock_code)
    df = df[df["stock_code"] != ""].copy()
    df["board_type"] = board_type
    df["board_code"] = board_code
    df["board_name"] = board_name
    df["source"] = "akshare_em"
    return df[["board_type", "board_code", "board_name", "stock_code", "stock_name", "source"]]


def upsert_catalog(cursor: pymysql.cursors.Cursor, rows: Iterable[tuple]) -> None:
    cursor.executemany(
        """
        INSERT INTO stock_board_catalog (board_type, board_code, board_name, source)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            board_name = VALUES(board_name),
            source = VALUES(source),
            updated_at = CURRENT_TIMESTAMP
        """,
        list(rows),
    )


def upsert_memberships(cursor: pymysql.cursors.Cursor, rows: Iterable[tuple]) -> None:
    cursor.executemany(
        """
        INSERT INTO stock_board_membership (board_type, board_code, board_name, stock_code, stock_name, source)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            board_name = VALUES(board_name),
            stock_name = VALUES(stock_name),
            source = VALUES(source),
            updated_at = CURRENT_TIMESTAMP
        """,
        list(rows),
    )


def clear_memberships_for_type(cursor: pymysql.cursors.Cursor, board_type: str) -> None:
    cursor.execute("DELETE FROM stock_board_membership WHERE board_type = %s", (board_type,))
    cursor.execute("DELETE FROM stock_board_catalog WHERE board_type = %s", (board_type,))


def sync_board_type(board_type: str, limit: Optional[int] = None) -> dict:
    catalog_df = fetch_board_catalog(board_type)
    if limit and limit > 0:
        catalog_df = catalog_df.head(limit).copy()

    logger.info("sync %s boards: %s", board_type, len(catalog_df))

    conn = None
    cursor = None
    membership_count = 0
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        clear_memberships_for_type(cursor, board_type)
        upsert_catalog(
            cursor,
            [tuple(row) for row in catalog_df[["board_type", "board_code", "board_name", "source"]].itertuples(index=False, name=None)],
        )

        for row in catalog_df.itertuples(index=False):
            logger.info("fetch %s board %s(%s)", board_type, row.board_name, row.board_code)
            member_df = fetch_board_members(board_type, row.board_name, row.board_code)
            if member_df.empty:
                continue
            upsert_memberships(
                cursor,
                [tuple(item) for item in member_df.itertuples(index=False, name=None)],
            )
            membership_count += len(member_df)
            conn.commit()
            time.sleep(REQUEST_SLEEP_SECONDS)

        conn.commit()
        return {
            "board_type": board_type,
            "board_count": len(catalog_df),
            "membership_count": membership_count,
        }
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def main() -> None:
    ensure_tables()
    summary = []
    for board_type in ["industry", "concept"]:
        summary.append(sync_board_type(board_type))
    logger.info("sync done: %s", summary)


if __name__ == "__main__":
    main()
