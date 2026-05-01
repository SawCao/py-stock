from __future__ import annotations

import math
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import pymysql
from flask import Flask, jsonify, request
from flask_cors import CORS


app = Flask(__name__)
CORS(app)


MYSQL_HOST = os.environ.get("MYSQL_HOST", "stock-mysql")
MYSQL_USER = os.environ.get("MYSQL_USER", "stock_user")
MYSQL_PWD = os.environ.get("MYSQL_PWD", "stock_pass_2024_sawtt")
MYSQL_DB = os.environ.get("MYSQL_DB", "stock_data")
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", 3306))

GAIN_COLUMNS = {"Gain_5", "Gain_10", "Gain_15", "Gain_20", "Gain_30", "Gain_60"}


def get_connection() -> pymysql.Connection:
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PWD,
        database=MYSQL_DB,
        port=MYSQL_PORT,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def normalize_code(code: str) -> str:
    if not code:
        return ""
    code = code.strip()
    if code.startswith(("sh.", "sz.")):
        return code.split(".", 1)[1]
    if code.startswith(("sh", "sz")) and len(code) == 8:
        return code[2:]
    return code


def symbol_from_code(code: str) -> str:
    code = normalize_code(code)
    if not code:
        return ""
    return f"sh.{code}" if code.startswith(("5", "6", "9")) else f"sz.{code}"


def eastmoney_url(code: str) -> str:
    raw = normalize_code(code)
    prefixed = symbol_from_code(raw).replace(".", "")
    return f"http://quote.eastmoney.com/{prefixed}.html"


def tonghuashun_url(code: str) -> str:
    return f"http://stockpage.10jqka.com.cn/{normalize_code(code)}/"


def parse_date(value: str, default: datetime) -> datetime:
    if not value:
        return default
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return default


def clamp_period(value: str | None) -> int:
    try:
        period = int(value or 30)
    except ValueError:
        period = 30
    return max(5, min(period, 240))


def stock_profile_map(codes: list[str]) -> dict[str, dict[str, Any]]:
    if not codes:
        return {}

    placeholders = ", ".join(["%s"] * len(codes))
    profile: dict[str, dict[str, Any]] = {}

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT code, raw_code, name, latest_price, is_active
                FROM stock_list_cache
                WHERE raw_code IN ({placeholders}) OR code IN ({placeholders})
                """,
                codes + [symbol_from_code(code) for code in codes],
            )
            for row in cursor.fetchall():
                raw = normalize_code(row.get("raw_code") or row.get("code") or "")
                if raw:
                    profile.setdefault(raw, {}).update(
                        {
                            "stock_name": row.get("name") or "",
                            "latest_price": float(row.get("latest_price") or 0),
                            "is_active": int(row.get("is_active") or 0),
                        }
                    )

            cursor.execute(
                f"""
                SELECT code, industry, industry_classification
                FROM stock_industry
                WHERE code IN ({placeholders})
                ORDER BY id DESC
                """,
                [symbol_from_code(code) for code in codes],
            )
            for row in cursor.fetchall():
                raw = normalize_code(row.get("code") or "")
                if raw and raw not in profile:
                    profile[raw] = {}
                if raw and "industry" not in profile[raw]:
                    profile[raw].update(
                        {
                            "industry": row.get("industry") or "未知",
                            "market": row.get("industry_classification") or "未知",
                        }
                    )

    return profile


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def query_search_results(
    gain_threshold: float,
    start_date: datetime,
    end_date: datetime,
    gain_type: str,
    search: str,
) -> list[dict[str, Any]]:
    like_clause = ""
    params: list[Any] = [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), gain_threshold]
    if search:
        like_clause = " AND (name LIKE %s OR rname LIKE %s)"
        keyword = f"%{normalize_code(search)}%" if search.isdigit() else f"%{search}%"
        params.extend([keyword, f"%{search}%"])

    sql = f"""
        SELECT
            name AS t2name,
            MAX(COALESCE(NULLIF(rname, ''), name)) AS rname,
            COUNT(*) AS gain_Amplitude_num,
            MIN(day) AS gain_start_date,
            MAX(day) AS gain_end_date,
            MIN(CAST(low AS DECIMAL(18, 4))) AS min_low,
            MAX(CAST(high AS DECIMAL(18, 4))) AS max_high,
            MIN(CAST(volume AS DECIMAL(18, 4))) AS min_volume,
            MAX(CAST(volume AS DECIMAL(18, 4))) AS max_volume
        FROM stock_zh_a_minute_ol_4
        WHERE DATE(day) BETWEEN %s AND %s
          AND CAST({gain_type} AS DECIMAL(18, 8)) > %s
          {like_clause}
        GROUP BY name
        ORDER BY gain_Amplitude_num DESC, t2name ASC
        LIMIT 200
    """

    results: list[dict[str, Any]] = []
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            results = list(cursor.fetchall())

            codes = [row["t2name"] for row in results]
            rise_map: dict[str, dict[str, int]] = {}
            if codes:
                placeholders = ", ".join(["%s"] * len(codes))
                cursor.execute(
                    f"""
                    SELECT
                        code AS raw_code,
                        SUM(CASE WHEN rise_continue = 1 THEN 1 ELSE 0 END) AS num_rise_continue_5day,
                        SUM(CASE WHEN turnover > 15 THEN 1 ELSE 0 END) AS num_turnover_rate_gt_015
                    FROM stock_zh_a_daily
                    WHERE date BETWEEN %s AND %s
                      AND code IN ({placeholders})
                    GROUP BY raw_code
                    """,
                    [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), *codes],
                )
                for row in cursor.fetchall():
                    rise_map[row["raw_code"]] = row

    profiles = stock_profile_map([row["t2name"] for row in results])
    response: list[dict[str, Any]] = []
    for row in results:
        code = row["t2name"]
        profile = profiles.get(code, {})
        rise = rise_map.get(code, {})

        min_low = safe_float(row.get("min_low"))
        max_high = safe_float(row.get("max_high"))
        min_volume = safe_float(row.get("min_volume"))
        max_volume = safe_float(row.get("max_volume"))

        price_diff = "0.00%" if min_low <= 0 else f"{((max_high - min_low) / min_low) * 100:.2f}%"
        volume_diff = "0.00%" if min_volume <= 0 else f"{((max_volume - min_volume) / min_volume) * 100:.2f}%"

        response.append(
            {
                "t2name": code,
                "rname": row.get("rname") or profile.get("stock_name") or code,
                "gain_Amplitude_num": int(row.get("gain_Amplitude_num") or 0),
                "price_diff": price_diff,
                "volume_diff": volume_diff,
                "gain_start_date": str(row.get("gain_start_date") or ""),
                "gain_end_date": str(row.get("gain_end_date") or ""),
                "market": profile.get("market") or "未知",
                "industry": profile.get("industry") or "未知",
                "num_rise_continue_5day": int(rise.get("num_rise_continue_5day") or 0),
                "num_turnover_rate_gt_015": int(rise.get("num_turnover_rate_gt_015") or 0),
                "url_1": eastmoney_url(code),
                "url_2": tonghuashun_url(code),
            }
        )

    return response


def query_stock_detail(stock_code: str) -> dict[str, Any] | None:
    raw_code = normalize_code(stock_code)
    symbol = symbol_from_code(raw_code)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT symbol, code, date, open, high, low, close, volume, turnover
                FROM stock_zh_a_daily
                WHERE symbol = %s
                ORDER BY date DESC
                LIMIT 2
                """,
                (symbol,),
            )
            rows = list(cursor.fetchall())

    if not rows:
        return None

    latest = rows[0]
    previous_close = safe_float(rows[1]["close"]) if len(rows) > 1 else safe_float(latest["open"])
    current_price = safe_float(latest["close"])
    change = current_price - previous_close
    change_percent = (change / previous_close * 100) if previous_close else 0.0
    volume = safe_float(latest["volume"])
    turnover_amount = current_price * volume
    turnover_rate = safe_float(latest.get("turnover"))
    market_cap = turnover_amount / (turnover_rate / 100.0) if turnover_rate > 0 else 0.0

    profile = stock_profile_map([raw_code]).get(raw_code, {})
    return {
        "stockCode": raw_code,
        "stockName": profile.get("stock_name") or raw_code,
        "currentPrice": round(current_price, 2),
        "change": round(change, 2),
        "changePercent": round(change_percent, 2),
        "volume": int(volume),
        "turnover": round(turnover_amount, 2),
        "marketCap": round(market_cap, 2),
        "pe": 0,
        "pb": 0,
        "high": safe_float(latest["high"]),
        "low": safe_float(latest["low"]),
        "open": safe_float(latest["open"]),
        "close": current_price,
    }


def query_kline(stock_code: str, period: int) -> list[dict[str, Any]]:
    raw_code = normalize_code(stock_code)
    symbol = symbol_from_code(raw_code)
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT date, open, close, low, high, volume
                FROM stock_zh_a_daily
                WHERE symbol = %s
                ORDER BY date DESC
                LIMIT %s
                """,
                (symbol, period),
            )
            rows = list(cursor.fetchall())

    rows.reverse()
    return [
        {
            "date": row["date"].strftime("%Y-%m-%d") if hasattr(row["date"], "strftime") else str(row["date"]),
            "open": safe_float(row["open"]),
            "close": safe_float(row["close"]),
            "low": safe_float(row["low"]),
            "high": safe_float(row["high"]),
            "volume": safe_float(row["volume"]),
        }
        for row in rows
    ]


def floor_bucket(ts: datetime, minutes: int) -> datetime:
    floored_minute = (ts.minute // minutes) * minutes
    return ts.replace(minute=floored_minute, second=0, microsecond=0)


def query_money_flow(stock_code: str, start_date: datetime, end_date: datetime) -> dict[str, Any]:
    raw_code = normalize_code(stock_code)
    profile = stock_profile_map([raw_code]).get(raw_code, {})

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT day, open, close, high, low, volume, rname
                FROM stock_zh_a_minute_ol_4
                WHERE name = %s
                  AND DATE(day) BETWEEN %s AND %s
                ORDER BY day ASC
                """,
                (raw_code, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
            )
            rows = list(cursor.fetchall())

    if not rows:
        return {
            "stock_code": raw_code,
            "stock_name": profile.get("stock_name") or raw_code,
            "money_flow": [],
        }

    grouped: dict[datetime, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        ts = datetime.strptime(str(row["day"]), "%Y-%m-%d %H:%M:%S")
        grouped[floor_bucket(ts, 30)].append(row)

    money_flow: list[dict[str, Any]] = []
    for bucket_time in sorted(grouped):
        bucket_rows = grouped[bucket_time]
        first_open = safe_float(bucket_rows[0]["open"])
        last_close = safe_float(bucket_rows[-1]["close"])
        total_amount = 0.0
        for item in bucket_rows:
            total_amount += safe_float(item["close"]) * safe_float(item["volume"])

        if first_open <= 0 or total_amount <= 0:
            inflow = 0.0
            outflow = 0.0
        else:
            change_pct = (last_close - first_open) / first_open * 100
            intensity = min(abs(change_pct) / 5.0, 1.0)
            primary_fund = total_amount * 0.65 * intensity
            if change_pct >= 0:
                inflow = primary_fund
                outflow = 0.0
            else:
                inflow = 0.0
                outflow = primary_fund

        money_flow.append(
            {
                "time": bucket_time.strftime("%Y-%m-%d %H:%M:%S"),
                "inflow": round(inflow, 2),
                "outflow": round(outflow, 2),
                "netflow": round(inflow - outflow, 2),
            }
        )

    latest_name = rows[-1].get("rname") or profile.get("stock_name") or raw_code
    return {
        "stock_code": raw_code,
        "stock_name": latest_name,
        "money_flow": money_flow,
    }


@app.get("/")
def index() -> dict[str, str]:
    return {"status": "ok", "service": "backend_v2"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/stock_search")
@app.get("/api/stock_search")
def stock_search() -> Any:
    gain_type = request.args.get("gain_type", "Gain_5")
    if gain_type not in GAIN_COLUMNS:
        return jsonify({"error": f"unsupported gain_type: {gain_type}"}), 400

    now = datetime.now()
    start_date = parse_date(request.args.get("start_date", ""), now - timedelta(days=10))
    end_date = parse_date(request.args.get("end_date", ""), now)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    gain_threshold = safe_float(request.args.get("gain_threshold", 0.03))
    search = (request.args.get("search") or "").strip()
    return jsonify(query_search_results(gain_threshold, start_date, end_date, gain_type, search))


@app.get("/stock_detail/<stock_code>")
@app.get("/api/stock_detail/<stock_code>")
def stock_detail(stock_code: str) -> Any:
    result = query_stock_detail(stock_code)
    if not result:
        return jsonify({"error": "stock not found"}), 404
    return jsonify(result)


@app.get("/kline/<stock_code>")
@app.get("/api/kline/<stock_code>")
def kline(stock_code: str) -> Any:
    return jsonify(query_kline(stock_code, clamp_period(request.args.get("period"))))


@app.get("/money_flow/<stock_code>")
@app.get("/api/money_flow/<stock_code>")
def money_flow(stock_code: str) -> Any:
    now = datetime.now()
    start_date = parse_date(request.args.get("start_date", ""), now - timedelta(days=10))
    end_date = parse_date(request.args.get("end_date", ""), now)
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    return jsonify(query_money_flow(stock_code, start_date, end_date))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
