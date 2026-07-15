from __future__ import annotations

import hashlib
import json
import math
import os
import pickle
import subprocess
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

GAIN_COLUMNS = {"Gain_1", "Gain_5", "Gain_10", "Gain_15", "Gain_20", "Gain_30", "Gain_60"}
SEARCH_CACHE_TTL_SECONDS = int(os.environ.get("STOCK_SEARCH_CACHE_TTL", 86400))
LEGACY_STOCK_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "new_web", "data_cache.pickle")
SEARCH_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "stock_search_cache")
CRON_STATUS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cron_status")
LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")

CRON_JOBS: dict[str, dict[str, str]] = {
    "daily_job_baostock": {
        "script": "/app/jobs/new_job/daily_job_baostock_5min_v3.py",
        "log_prefix": "daily_job_baostock",
        "supports_date": "1",
        "supports_days": "1",
    },
    "turnover_rise_baostock": {
        "script": "/app/jobs/new_job/turnover_rise_baostock_v3.py",
        "log_prefix": "turnover_rise_baostock",
        "supports_days": "1",
    },
    "stock_board_sync": {
        "script": "/app/jobs/new_job/stock_board_sync.py",
        "log_prefix": "stock_board_sync",
    },
}

EXPECTED_MINUTE_ROWS_PER_DAY = 48


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


def is_table_missing_error(exc: Exception, table_name: str) -> bool:
    if not isinstance(exc, pymysql.err.ProgrammingError):
        return False
    if len(exc.args) < 2 or exc.args[0] != 1146:
        return False
    return table_name in str(exc.args[1])


def load_legacy_stock_profile_map() -> dict[str, dict[str, Any]]:
    if not os.path.exists(LEGACY_STOCK_CACHE_PATH):
        return {}

    try:
        with open(LEGACY_STOCK_CACHE_PATH, "rb") as file_obj:
            return pickle.load(file_obj)
    except (OSError, pickle.PickleError, EOFError):
        return {}


def ensure_search_cache_dir() -> None:
    os.makedirs(SEARCH_CACHE_DIR, exist_ok=True)


def search_cache_key(
    gain_threshold: float,
    start_date: datetime,
    end_date: datetime,
    gain_type: str,
    search: str,
) -> tuple[Any, ...]:
    return (
        round(gain_threshold, 8),
        start_date.strftime("%Y-%m-%d %H:%M:%S"),
        end_date.strftime("%Y-%m-%d %H:%M:%S"),
        gain_type,
        search,
    )


def search_cache_path(cache_key: tuple[Any, ...]) -> str:
    payload = repr(cache_key).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return os.path.join(SEARCH_CACHE_DIR, f"{digest}.pickle")


def load_search_cache(cache_path: str) -> list[dict[str, Any]] | None:
    if not os.path.exists(cache_path):
        return None

    file_age_seconds = datetime.now().timestamp() - os.path.getmtime(cache_path)
    if file_age_seconds > SEARCH_CACHE_TTL_SECONDS:
        try:
            os.remove(cache_path)
        except OSError:
            pass
        return None

    try:
        with open(cache_path, "rb") as file_obj:
            return pickle.load(file_obj)
    except (OSError, pickle.PickleError, EOFError):
        return None


def save_search_cache(cache_path: str, result: list[dict[str, Any]]) -> None:
    ensure_search_cache_dir()
    temp_path = f"{cache_path}.tmp.{os.getpid()}"
    try:
        with open(temp_path, "wb") as file_obj:
            pickle.dump(result, file_obj, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(temp_path, cache_path)
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def clear_search_cache_files() -> dict[str, Any]:
    ensure_search_cache_dir()
    removed = 0
    failed: list[str] = []
    for entry in os.listdir(SEARCH_CACHE_DIR):
        path = os.path.join(SEARCH_CACHE_DIR, entry)
        if not os.path.isfile(path):
            continue
        try:
            os.remove(path)
            removed += 1
        except OSError:
            failed.append(entry)
    return {"removed": removed, "failed": failed}


def load_cron_status(job_name: str) -> dict[str, Any]:
    path = os.path.join(CRON_STATUS_DIR, f"{job_name}.json")
    if not os.path.exists(path):
        return {
            "job_name": job_name,
            "status": "unknown",
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "log_file": None,
            "run_mode": None,
            "pid": None,
            "command": None,
        }

    try:
        with open(path, "r", encoding="utf-8") as file_obj:
            return json.load(file_obj)
    except (OSError, json.JSONDecodeError):
        return {
            "job_name": job_name,
            "status": "invalid_status_file",
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "log_file": path,
            "run_mode": None,
            "pid": None,
            "command": None,
        }


def save_cron_status(job_name: str, status: dict[str, Any]) -> None:
    os.makedirs(CRON_STATUS_DIR, exist_ok=True)
    path = os.path.join(CRON_STATUS_DIR, f"{job_name}.json")
    try:
        with open(path, "w", encoding="utf-8") as file_obj:
            json.dump(status, file_obj, ensure_ascii=False)
    except OSError:
        pass


def list_cron_statuses() -> list[dict[str, Any]]:
    return [load_cron_status(job_name) for job_name in CRON_JOBS]


def is_pid_running(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def get_pid_command(pid: int | None) -> str:
    if not pid or pid <= 0:
        return ""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "args="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return ""

    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def is_pid_zombie(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "stat="],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return False

    if result.returncode != 0:
        return False
    return result.stdout.strip().startswith("Z")


def is_expected_job_process(status: dict[str, Any]) -> bool:
    pid = status.get("pid")
    if not is_pid_running(pid):
        return False
    if is_pid_zombie(pid):
        return False

    current_command = get_pid_command(pid)
    if not current_command:
        return False

    job = CRON_JOBS.get(status.get("job_name"))
    expected_script = job.get("script") if job else None
    recorded_command = str(status.get("command") or "")

    if expected_script and expected_script in current_command:
        return True
    if recorded_command and recorded_command in current_command:
        return True
    return False


def normalize_cron_status(status: dict[str, Any]) -> dict[str, Any]:
    if status.get("status") == "running" and not is_expected_job_process(status):
        status = dict(status)
        status["status"] = "failed"
        if status.get("exit_code") is None:
            status["exit_code"] = -1
        if status.get("finished_at") is None:
            status["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_cron_status(str(status.get("job_name") or "unknown"), status)
    return status


def build_manual_log_file(job_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(LOG_DIR, f"manual_{job_name}_{timestamp}.log")


def parse_log_metadata(file_name: str) -> dict[str, Any]:
    name = os.path.basename(file_name)
    if name.startswith("cron_") and name.endswith(".log"):
        stem = name[:-4]
        parts = stem.split("_")
        date_part = parts[-1] if parts and parts[-1].isdigit() and len(parts[-1]) == 8 else None
        job_name = "_".join(parts[1:-1]) if date_part else "_".join(parts[1:])
        return {
            "run_mode": "scheduled",
            "job_name": job_name,
            "date": date_part,
        }
    if name.startswith("manual_") and name.endswith(".log"):
        stem = name[:-4]
        parts = stem.split("_")
        date_part = parts[-2] if len(parts) >= 3 and parts[-2].isdigit() and len(parts[-2]) == 8 else None
        time_part = parts[-1] if parts and parts[-1].isdigit() and len(parts[-1]) == 6 else None
        job_name = "_".join(parts[1:-2]) if date_part and time_part else "_".join(parts[1:])
        return {
            "run_mode": "manual",
            "job_name": job_name,
            "date": date_part,
        }
    return {
        "run_mode": "other",
        "job_name": None,
        "date": None,
    }


def trigger_cron_job(job_name: str) -> dict[str, Any]:
    job = CRON_JOBS.get(job_name)
    if not job:
        raise ValueError(f"unknown job: {job_name}")

    current_status = normalize_cron_status(load_cron_status(job_name))
    if current_status.get("status") == "running":
        raise RuntimeError(f"job already running: {job_name}")

    payload = request.get_json(silent=True) or {}
    raw_days = payload.get("days", request.values.get("days", 2))
    raw_date = payload.get("date", request.values.get("date"))

    try:
        days = max(1, min(int(raw_days), 60))
    except (TypeError, ValueError):
        days = 2

    log_file = build_manual_log_file(job_name)
    command = [
        "/bin/bash",
        "/app/jobs/run_cron_job.sh",
        job_name,
        log_file,
        "manual",
        "/usr/local/bin/python3",
        job["script"],
    ]

    if job.get("supports_days") == "1":
        command.extend(["--days", str(days)])

    if raw_date and job.get("supports_date") == "1":
        command.extend(["--date", str(raw_date)])

    env = os.environ.copy()
    env_file = "/app/.env"
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as file_obj:
            for line in file_obj:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    process = subprocess.Popen(command, cwd="/app", env=env)

    return {
        "job_name": job_name,
        "status": "started",
        "pid": process.pid,
        "log_file": log_file,
        "days": days,
        "date": raw_date,
    }


def query_minute_data_completeness(days: int) -> dict[str, Any]:
    days = max(1, min(days, 30))
    summaries: list[dict[str, Any]] = []
    incomplete_details: list[dict[str, Any]] = []
    summary_by_day: dict[str, dict[str, Any]] = {}
    start_day = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
    end_day = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    SUBSTRING(day, 1, 10) AS trade_date,
                    name AS stock_code,
                    MAX(COALESCE(NULLIF(rname, ''), name)) AS stock_name,
                    COUNT(*) AS row_count
                FROM stock_zh_a_minute_ol_4
                WHERE day >= %s AND day < %s
                GROUP BY SUBSTRING(day, 1, 10), name
                ORDER BY trade_date DESC, row_count ASC, stock_code ASC
                """,
                (start_day, end_day),
            )
            grouped_rows = list(cursor.fetchall())

    for row in grouped_rows:
        trade_date = str(row["trade_date"])
        row_count = int(row["row_count"] or 0)
        day_summary = summary_by_day.setdefault(
            trade_date,
            {
                "trade_date": trade_date,
                "stock_count": 0,
                "total_rows": 0,
                "incomplete_stock_count": 0,
            },
        )
        day_summary["stock_count"] += 1
        day_summary["total_rows"] += row_count

        if row_count < EXPECTED_MINUTE_ROWS_PER_DAY:
            day_summary["incomplete_stock_count"] += 1
            incomplete_details.append(
                {
                    "trade_date": trade_date,
                    "stock_code": row["stock_code"],
                    "stock_name": row.get("stock_name") or row["stock_code"],
                    "row_count": row_count,
                    "expected_rows": EXPECTED_MINUTE_ROWS_PER_DAY,
                    "missing_rows": EXPECTED_MINUTE_ROWS_PER_DAY - row_count,
                }
            )

    for trade_date in sorted(summary_by_day.keys(), reverse=True):
        day_summary = summary_by_day[trade_date]
        stock_count = int(day_summary["stock_count"] or 0)
        total_rows = int(day_summary["total_rows"] or 0)
        incomplete_count = int(day_summary["incomplete_stock_count"] or 0)
        complete_count = max(stock_count - incomplete_count, 0)
        expected_total_rows = stock_count * EXPECTED_MINUTE_ROWS_PER_DAY
        missing_rows = max(expected_total_rows - total_rows, 0)
        completion_rate = 0.0 if expected_total_rows <= 0 else total_rows / expected_total_rows * 100
        summaries.append(
            {
                "trade_date": trade_date,
                "stock_count": stock_count,
                "expected_rows_per_stock": EXPECTED_MINUTE_ROWS_PER_DAY,
                "complete_stock_count": complete_count,
                "incomplete_stock_count": incomplete_count,
                "total_rows": total_rows,
                "expected_total_rows": expected_total_rows,
                "missing_rows": missing_rows,
                "completion_rate": round(completion_rate, 2),
            }
        )

    return {
        "days": days,
        "expected_rows_per_stock": EXPECTED_MINUTE_ROWS_PER_DAY,
        "summary": summaries,
        "incomplete_details": incomplete_details,
    }


def read_log_file(log_name: str, lines: int) -> dict[str, Any]:
    safe_name = os.path.basename(log_name)
    path = os.path.join(LOG_DIR, safe_name)
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with open(path, "r", encoding="utf-8", errors="replace") as file_obj:
        content_lines = file_obj.readlines()

    selected = content_lines[-lines:] if lines > 0 else content_lines
    return {
        "log_name": safe_name,
        "path": path,
        "lines": len(selected),
        "content": "".join(selected),
        **parse_log_metadata(safe_name),
    }


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


def market_from_code(code: str) -> str:
    code = normalize_code(code)
    if not code:
        return "未知"
    if code.startswith(("430", "440", "83", "87")):
        return "北交所"
    if code.startswith("688"):
        return "科创板"
    if code.startswith(("300", "301")):
        return "创业板"
    if code.startswith(("000", "001", "002", "003", "600", "601", "603", "605")):
        return "主板"
    return "未知"


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
    legacy_profile = load_legacy_stock_profile_map()

    for code in codes:
        legacy_row = legacy_profile.get(code) or legacy_profile.get(symbol_from_code(code).replace(".", "").upper())
        if legacy_row:
            profile.setdefault(code, {}).update(
                {
                    "stock_name": legacy_row.get("name") or "",
                    "industry": legacy_row.get("industry") or "未知",
                    "market": legacy_row.get("market") or market_from_code(code),
                }
            )

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
                if raw and not profile[raw].get("industry"):
                    profile[raw].update(
                        {
                            "industry": row.get("industry") or "未知",
                            "industry_classification": row.get("industry_classification") or "未知",
                        }
                    )

            try:
                cursor.execute(
                    f"""
                    SELECT stock_code, board_type, GROUP_CONCAT(board_name ORDER BY board_name SEPARATOR ', ') AS board_names
                    FROM stock_board_membership
                    WHERE stock_code IN ({placeholders})
                    GROUP BY stock_code, board_type
                    """,
                    codes,
                )
                for row in cursor.fetchall():
                    raw = normalize_code(row.get("stock_code") or "")
                    if not raw:
                        continue
                    profile.setdefault(raw, {})
                    board_type = row.get("board_type") or ""
                    board_names = row.get("board_names") or ""
                    if board_type == "industry" and board_names and not profile[raw].get("industry_boards"):
                        profile[raw]["industry_boards"] = board_names
                    if board_type == "concept" and board_names and not profile[raw].get("concept_boards"):
                        profile[raw]["concept_boards"] = board_names
            except Exception as exc:
                if not is_table_missing_error(exc, "stock_board_membership"):
                    raise

    for code in codes:
        profile.setdefault(code, {})
        if not profile[code].get("market"):
            profile[code]["market"] = market_from_code(code)
        if not profile[code].get("industry"):
            profile[code]["industry"] = "未知"
        if not profile[code].get("industry_classification"):
            profile[code]["industry_classification"] = "未知"
        if not profile[code].get("industry_boards"):
            profile[code]["industry_boards"] = ""
        if not profile[code].get("concept_boards"):
            profile[code]["concept_boards"] = ""

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
    end_exclusive = end_date + timedelta(days=1)
    params: list[Any] = [
        start_date.strftime("%Y-%m-%d"),
        end_exclusive.strftime("%Y-%m-%d"),
        gain_threshold,
    ]
    if search:
        like_clause = " AND (name LIKE %s OR rname LIKE %s)"
        keyword = f"%{normalize_code(search)}%" if search.isdigit() else f"%{search}%"
        params.extend([keyword, f"%{search}%"])

    sql = f"""
        SELECT
            name AS t2name,
            SUBSTRING_INDEX(
                GROUP_CONCAT(COALESCE(NULLIF(rname, ''), name) ORDER BY day DESC SEPARATOR ','),
                ',',
                1
            ) AS rname,
            COUNT(*) AS gain_Amplitude_num,
            MIN(day) AS gain_start_date,
            MAX(day) AS gain_end_date,
            SUBSTRING_INDEX(GROUP_CONCAT(CAST(low AS DECIMAL(18, 4)) ORDER BY day ASC SEPARATOR ','), ',', 1) AS first_low,
            SUBSTRING_INDEX(GROUP_CONCAT(CAST(high AS DECIMAL(18, 4)) ORDER BY day DESC SEPARATOR ','), ',', 1) AS last_high,
            SUBSTRING_INDEX(GROUP_CONCAT(CAST(volume AS DECIMAL(18, 4)) ORDER BY day ASC SEPARATOR ','), ',', 1) AS first_volume,
            SUBSTRING_INDEX(GROUP_CONCAT(CAST(volume AS DECIMAL(18, 4)) ORDER BY day DESC SEPARATOR ','), ',', 1) AS last_volume
        FROM stock_zh_a_minute_ol_4
        WHERE day >= %s
          AND day < %s
          AND {gain_type} > %s
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

        first_low = safe_float(row.get("first_low"))
        last_high = safe_float(row.get("last_high"))
        first_volume = safe_float(row.get("first_volume"))
        last_volume = safe_float(row.get("last_volume"))

        price_diff = "0.00%" if first_low <= 0 else f"{((last_high - first_low) / first_low) * 100:.2f}%"
        volume_diff = "0.00%" if first_volume <= 0 else f"{((last_volume - first_volume) / first_volume) * 100:.2f}%"

        response.append(
            {
                "t2name": code,
                "rname": row.get("rname") or profile.get("stock_name") or code,
                "gain_Amplitude_num": int(row.get("gain_Amplitude_num") or 0),
                "price_diff": price_diff,
                "volume_diff": volume_diff,
                "gain_start_date": str(row.get("gain_start_date") or ""),
                "gain_end_date": str(row.get("gain_end_date") or ""),
                "industry": profile.get("industry") or "未知",
                "industry_classification": profile.get("industry_classification") or "未知",
                "industry_boards": profile.get("industry_boards") or "",
                "concept_boards": profile.get("concept_boards") or "",
                "num_rise_continue_5day": int(rise.get("num_rise_continue_5day") or 0),
                "num_turnover_rate_gt_015": int(rise.get("num_turnover_rate_gt_015") or 0),
                "url_1": eastmoney_url(code),
                "url_2": tonghuashun_url(code),
            }
        )

    return response


def get_cached_search_results(
    gain_threshold: float,
    start_date: datetime,
    end_date: datetime,
    gain_type: str,
    search: str,
) -> list[dict[str, Any]]:
    cache_key = search_cache_key(gain_threshold, start_date, end_date, gain_type, search)
    cache_path = search_cache_path(cache_key)
    cached = load_search_cache(cache_path)
    if cached is not None:
        return cached

    result = query_search_results(gain_threshold, start_date, end_date, gain_type, search)
    save_search_cache(cache_path, result)

    return result


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


def query_stock_basic_info(stock_code: str) -> dict[str, Any] | None:
    raw_code = normalize_code(stock_code)
    if not raw_code:
        return None

    symbol = symbol_from_code(raw_code)
    profile = stock_profile_map([raw_code]).get(raw_code, {})
    result: dict[str, Any] = {
        "stockCode": raw_code,
        "symbol": symbol,
        "stockName": profile.get("stock_name") or raw_code,
        "exchangeBoard": profile.get("market") or market_from_code(raw_code),
        "industry": profile.get("industry") or "未知",
        "industryClassification": profile.get("industry_classification") or "未知",
        "industryBoards": profile.get("industry_boards") or "",
        "conceptBoards": profile.get("concept_boards") or "",
        "latestPrice": round(safe_float(profile.get("latest_price")), 2),
        "isActive": bool(profile.get("is_active")),
        "latestTradeDate": None,
        "open": 0.0,
        "high": 0.0,
        "low": 0.0,
        "close": 0.0,
        "volume": 0,
        "turnoverRate": 0.0,
        "tables": {
            "stock_list_cache": None,
            "stock_industry": None,
            "stock_board_membership": [],
            "stock_zh_a_daily_latest": None,
        },
    }

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT *
                FROM stock_list_cache
                WHERE raw_code = %s OR code = %s
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """,
                (raw_code, symbol),
            )
            list_cache_row = cursor.fetchone()
            if list_cache_row:
                result["tables"]["stock_list_cache"] = list_cache_row

            cursor.execute(
                """
                SELECT *
                FROM stock_industry
                WHERE code = %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (symbol,),
            )
            industry_row = cursor.fetchone()
            if industry_row:
                result["industry"] = industry_row.get("industry") or result["industry"]
                result["industryClassification"] = industry_row.get("industry_classification") or "未知"
                result["stockName"] = industry_row.get("code_name") or result["stockName"]
                result["tables"]["stock_industry"] = industry_row

            try:
                cursor.execute(
                    """
                    SELECT board_type, board_code, board_name, stock_code, stock_name, source, updated_at
                    FROM stock_board_membership
                    WHERE stock_code = %s
                    ORDER BY board_type ASC, board_name ASC
                    """,
                    (raw_code,),
                )
                board_rows = list(cursor.fetchall())
                if board_rows:
                    result["tables"]["stock_board_membership"] = board_rows
                    industry_boards = [row.get("board_name") or "" for row in board_rows if row.get("board_type") == "industry"]
                    concept_boards = [row.get("board_name") or "" for row in board_rows if row.get("board_type") == "concept"]
                    result["industryBoards"] = ", ".join([name for name in industry_boards if name])
                    result["conceptBoards"] = ", ".join([name for name in concept_boards if name])
            except Exception as exc:
                if not is_table_missing_error(exc, "stock_board_membership"):
                    raise

            cursor.execute(
                """
                SELECT *
                FROM stock_zh_a_daily
                WHERE symbol = %s
                ORDER BY date DESC
                LIMIT 1
                """,
                (symbol,),
            )
            latest_daily = cursor.fetchone()
            if latest_daily:
                result["tables"]["stock_zh_a_daily_latest"] = latest_daily

    if latest_daily:
        close = safe_float(latest_daily.get("close"))
        result.update(
            {
                "latestTradeDate": latest_daily["date"].strftime("%Y-%m-%d") if hasattr(latest_daily.get("date"), "strftime") else str(latest_daily.get("date") or ""),
                "open": safe_float(latest_daily.get("open")),
                "high": safe_float(latest_daily.get("high")),
                "low": safe_float(latest_daily.get("low")),
                "close": close,
                "volume": int(safe_float(latest_daily.get("volume"))),
                "turnoverRate": round(safe_float(latest_daily.get("turnover")), 2),
            }
        )
        if result["latestPrice"] <= 0:
            result["latestPrice"] = round(close, 2)

    has_any_data = any(
        [
            result["stockName"] != raw_code,
            result["industry"] != "未知",
            result["latestPrice"] > 0,
            result["latestTradeDate"],
            result["tables"]["stock_list_cache"] is not None,
            result["tables"]["stock_industry"] is not None,
            bool(result["tables"]["stock_board_membership"]),
            result["tables"]["stock_zh_a_daily_latest"] is not None,
        ]
    )
    return result if has_any_data else None


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
    gain_type = request.args.get("gain_type", "Gain_1")
    if gain_type not in GAIN_COLUMNS:
        return jsonify({"error": f"unsupported gain_type: {gain_type}"}), 400

    now = datetime.now()
    start_date = parse_date(request.args.get("start_date", ""), now - timedelta(days=10))
    end_date = parse_date(request.args.get("end_date", ""), now)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    gain_threshold = safe_float(request.args.get("gain_threshold", 0.03))
    search = (request.args.get("search") or "").strip()
    return jsonify(get_cached_search_results(gain_threshold, start_date, end_date, gain_type, search))


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


@app.post("/api/admin/stock_search_cache/clear")
@app.get("/api/admin/stock_search_cache/clear")
def clear_stock_search_cache() -> Any:
    result = clear_search_cache_files()
    return jsonify({"status": "ok", **result})


@app.get("/api/admin/stock_basic_info")
def admin_stock_basic_info() -> Any:
    stock_code = (request.args.get("stock_code") or request.args.get("code") or "").strip()
    if not stock_code:
        return jsonify({"error": "missing stock_code"}), 400

    result = query_stock_basic_info(stock_code)
    if not result:
        return jsonify({"error": "stock not found"}), 404
    return jsonify(result)


@app.get("/api/admin/cron_status")
def cron_status() -> Any:
    return jsonify({"jobs": [normalize_cron_status(item) for item in list_cron_statuses()]})


@app.post("/api/admin/cron_trigger/<job_name>")
def cron_trigger(job_name: str) -> Any:
    try:
        return jsonify(trigger_cron_job(job_name))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 409


@app.get("/api/admin/logs")
def admin_logs() -> Any:
    log_name = request.args.get("name", "")
    if not log_name:
        return jsonify({"error": "missing log name"}), 400

    try:
        lines = max(1, min(int(request.args.get("lines", 200)), 2000))
    except ValueError:
        lines = 200

    try:
        return jsonify(read_log_file(log_name, lines))
    except FileNotFoundError:
        return jsonify({"error": f"log not found: {log_name}"}), 404


@app.get("/api/admin/log_files")
def admin_log_files() -> Any:
    date_filter = (request.args.get("date") or "").strip()
    job_filter = (request.args.get("job_name") or "").strip()
    run_mode_filter = (request.args.get("run_mode") or "").strip()
    files = []
    if os.path.isdir(LOG_DIR):
        for name in sorted(os.listdir(LOG_DIR)):
            path = os.path.join(LOG_DIR, name)
            if os.path.isfile(path):
                metadata = parse_log_metadata(name)
                if date_filter and metadata.get("date") != date_filter:
                    continue
                if job_filter and metadata.get("job_name") != job_filter:
                    continue
                if run_mode_filter and metadata.get("run_mode") != run_mode_filter:
                    continue
                files.append(
                    {
                        "name": name,
                        "size": os.path.getsize(path),
                        "updated_at": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S"),
                        **metadata,
                    }
                )
    return jsonify({"files": files})


@app.get("/api/admin/minute_data_completeness")
def minute_data_completeness() -> Any:
    try:
        days = int(request.args.get("days", 5))
    except ValueError:
        days = 5
    return jsonify(query_minute_data_completeness(days))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
