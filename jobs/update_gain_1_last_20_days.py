#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

import os
import argparse
from datetime import datetime, timedelta

import pymysql


MYSQL_HOST = os.environ.get("MYSQL_HOST", "127.0.0.1")
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PWD = os.environ.get("MYSQL_PWD", "mysqldb")
MYSQL_DB = os.environ.get("MYSQL_DB", "stock_data")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))

TARGET_TABLE = "stock_zh_a_minute_ol_4"


def get_connection(cursorclass=pymysql.cursors.Cursor):
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PWD,
        database=MYSQL_DB,
        port=MYSQL_PORT,
        charset="utf8mb4",
        cursorclass=cursorclass,
        autocommit=False,
    )


def ensure_gain_1_column() -> None:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s AND column_name = 'Gain_1'
                """,
                (MYSQL_DB, TARGET_TABLE),
            )
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    f"ALTER TABLE {TARGET_TABLE} ADD COLUMN Gain_1 DECIMAL(10, 6) COMMENT '1周期波动率' AFTER volume"
                )
                conn.commit()


def recompute_gain_1(start_time: datetime) -> tuple[int, int]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"SELECT COUNT(*) FROM {TARGET_TABLE} WHERE day >= %s",
                (start_time.strftime("%Y-%m-%d %H:%M:%S"),),
            )
            scoped_rows = int(cursor.fetchone()[0] or 0)

            cursor.execute(
                f"""
                UPDATE {TARGET_TABLE}
                SET Gain_1 = CASE
                    WHEN CAST(low AS DECIMAL(16, 6)) > 0
                    THEN ROUND(
                        (CAST(high AS DECIMAL(16, 6)) - CAST(low AS DECIMAL(16, 6)))
                        / CAST(low AS DECIMAL(16, 6)),
                        6
                    )
                    ELSE 0
                END
                WHERE day >= %s
                """,
                (start_time.strftime("%Y-%m-%d %H:%M:%S"),),
            )
            updated_rows = cursor.rowcount
            conn.commit()
            return scoped_rows, updated_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Recompute Gain_1 from existing minute data")
    parser.add_argument("--days", type=int, default=20, help="Recompute rows from the last N days")
    args = parser.parse_args()

    ensure_gain_1_column()

    start_time = datetime.now() - timedelta(days=max(1, args.days))
    scoped_rows, updated_rows = recompute_gain_1(start_time)

    print(
        "Recomputed Gain_1 for "
        f"{updated_rows} rows out of {scoped_rows} scoped rows in {TARGET_TABLE} "
        f"since {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )


if __name__ == "__main__":
    main()
