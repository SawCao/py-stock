# Repository Guidelines

## Project Structure & Module Organization
`jobs/` contains market-data collectors and batch scripts; prefer `jobs/new_job/` for the current Baostock-based pipelines and treat older files in `jobs/` as legacy unless you are fixing existing behavior. `libs/` holds shared database and utility helpers such as `libs/common.py`. Backend config and deployment files live at the repo root: `config.py`, `requirements.txt`, `Dockerfile.combined`, `docker-compose.yml`, `crontab`, and `supervisor/`. The active frontend is `web/umi-stock/` (Umi 4 + React + TypeScript); `web/new_web/` is an older Flask/jQuery UI that should only be touched for maintenance. Runtime outputs go to `logs/` and `data/`.

## Backend Runtime Notes
The active Flask backend for the Umi frontend is `web/backend_v2/`, not `web/new_web/`. Supervisor should run Gunicorn with `web.backend_v2.app:app`. `web/new_web/` is kept only as a legacy reference and should not be used as the live API implementation unless explicitly requested.

`web/backend_v2/app.py` must stay compatible with the existing frontend API contracts used by `web/umi-stock/src/pages/`:
- `GET /api/stock_search`
- `GET /api/stock_detail/:stockCode`
- `GET /api/kline/:stockCode`
- `GET /api/money_flow/:stockCode`

`/api/stock_search` uses a shared file cache under `data/stock_search_cache/` with a 24-hour TTL. After changing `stock_search` query logic, cache key semantics, or returned fields, clear the cache before validating behavior via `GET` or `POST /api/admin/stock_search_cache/clear`.

Cron job visibility is tracked with JSON status files under `data/cron_status/`, written by `jobs/run_cron_job.sh`. Use `GET /api/admin/cron_status` to quickly confirm whether each daily cron job started and whether it finished successfully.

Cron and manual trigger logs are separated:
- Scheduled runs write date-partitioned files like `logs/cron_<job_name>_YYYYMMDD.log`
- Manual runs write separate files like `logs/manual_<job_name>_YYYYMMDD_HHMMSS.log`

When updating admin log browsing, preserve support for filtering by `date`, `job_name`, and `run_mode`.

Admin APIs exposed by `web/backend_v2/app.py` now include:
- `GET` or `POST /api/admin/stock_search_cache/clear`
- `GET /api/admin/cron_status`
- `POST /api/admin/cron_trigger/:jobName`
- `GET /api/admin/log_files`
- `GET /api/admin/logs?name=<logName>&lines=<n>`
- `GET /api/admin/minute_data_completeness?days=<n>`

The Umi frontend includes an admin page at `/admin` for cron status, manual job trigger, cache clearing, and log viewing. When changing these admin workflows, keep backend and frontend behavior aligned.

Manual cron triggering via `/api/admin/cron_trigger/:jobName` supports a `days` parameter only for the Baostock jobs and currently defaults to `2` when not provided. `daily_job_baostock` also supports an optional `date` parameter in `YYYYMMDD` format if the trigger flow is extended later. `stock_board_sync` does not take `days` and should be triggered without extra range arguments.

For minute data completeness checks, use `stock_zh_a_minute_ol_4` and treat a full trading day as `48` expected 5-minute rows per stock: 24 rows in the morning session and 24 rows in the afternoon session. Stocks with fewer than 48 rows for a trading day should be reported as incomplete.

## Data Mapping Notes
For `stock_search`, minute-level matches come from `stock_zh_a_minute_ol_4`, while enrichment and counters come from `stock_zh_a_daily`, `stock_list_cache`, and `stock_industry`.

## Data Ingestion Notes
The currently active scheduled jobs are defined in `crontab`:
- `daily_job_baostock` runs `jobs/new_job/daily_job_baostock_5min_v3.py` at 16:00 on weekdays and writes 5-minute bars plus computed Gain fields into `stock_zh_a_minute_ol_4`.
- `turnover_rise_baostock` runs `jobs/new_job/turnover_rise_baostock_v3.py` at 17:00 on weekdays and writes daily bars plus turnover and `rise_continue` into `stock_zh_a_daily`.
- `stock_board_sync` runs `jobs/new_job/stock_board_sync.py` at 18:00 on weekdays and refreshes board catalogs plus stock-to-board memberships.

Both active jobs depend on `jobs/new_job/stock_list_cache.py` for the stock universe:
- `stock_list_cache.get_stock_list()` first tries `stock_list_cache` if the cache is fresh.
- If the cache is missing or older than 7 days, it fetches fresh A-share spot data from `akshare.stock_zh_a_spot()`, filters out B shares, Beijing exchange symbols, ST stocks, and invalid prices, then upserts the result into `stock_list_cache`.
- There is also a manual helper script `jobs/update_stock_list.py` for initializing, checking, and force-refreshing `stock_list_cache`, but it is not wired into the active cron.

Important ingestion/source mapping:
- `stock_list_cache` is populated from Akshare `stock_zh_a_spot()` via `jobs/new_job/stock_list_cache.py`.
- `stock_zh_a_minute_ol_4` is populated from Baostock 5-minute history via `jobs/new_job/daily_job_baostock_5min_v3.py`.
- `stock_zh_a_daily` is populated from Baostock daily history via `jobs/new_job/turnover_rise_baostock_v3.py`.
- No active job in this repository currently writes `stock_industry`; the table appears to be preloaded or maintained outside the checked-in cron/job pipeline. Do not assume it is refreshed automatically by the current app jobs.
- `jobs/new_job/stock_board_sync.py` is the dedicated sync script for multi-valued stock board memberships. It pulls Eastmoney board data through Akshare and writes:
- `stock_board_catalog` for board metadata (`industry` and `concept` board directories)
- `stock_board_membership` for many-to-many stock-to-board mappings such as `火力发电`, `电子`, and `新能源车`

Important field semantics:
- `stock_zh_a_daily.code` is the plain 6-digit stock code and should be used when joining to minute data codes.
- `stock_zh_a_daily.symbol` includes market prefixes like `sh.600060` and is not suitable for direct joins to `stock_zh_a_minute_ol_4.name`.
- `stock_zh_a_daily.turnover` stores percentage values directly, e.g. `15.8355` means `15.8355%`, so the threshold for "换手率>15%天数" must be `turnover > 15`, not `turnover > 0.15`.
- `stock_industry.industry` is the actual industry value currently available in the database, often code-prefixed names like `C36汽车制造业` or `J66货币金融服务`.
- `stock_industry.industry_classification` is the taxonomy label and is currently mostly `证监会行业分类`; do not mislabel it as a concept/sector field like `数字芯片设计` unless a separate source table is added.
- `stock_board_membership` is the authoritative source for multi-valued board tags. Use it for user-facing board labels like `火力发电`, `电子`, `新能源车`, or other industry/concept memberships.
- The user-facing "市场板块" label was misleading for current data. Treat `market_from_code()` as an exchange board classifier like `主板`/`创业板`/`科创板`, not as an industry or concept sector.

## Build, Test, and Development Commands
Set up Python dependencies with `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt` or run `./setup_py.sh`. Start the full stack with `docker compose up --build`; this launches MySQL, the Flask backend on `:5000`, and the Umi UI on `:8888`. For frontend development, use `cd web/umi-stock && npm install && npm run dev`; build production assets with `npm run build`.

### Local Docker Release Memory
When backend or frontend code changes need to be published locally, rebuild and restart the full stack from the repo root with `docker compose up -d --build`.
After the rebuild completes, verify service status with `docker compose ps` and confirm `stock-mysql`, `stock-backend`, and `stock-webui` are up before considering the local release finished.
For `web-backend`, runtime code should come from the built image, not a host bind mount of the whole repo or `jobs/`. Keep only runtime data mounts such as `./logs:/app/logs`, `./data:/app/data`, and the single-file cron mount `./crontab:/mounted-config/crontab:ro`. This avoids stale or partial host-mounted code masking newly built files like `jobs/new_job/stock_board_sync.py`.
Keep a root `.dockerignore` so backend builds do not send heavyweight frontend artifacts such as `web/umi-stock/node_modules/` into the Python image build context.

## Coding Style & Naming Conventions
Follow the existing style rather than introducing a new formatter. Python uses 4-space indentation, snake_case function names, uppercase module constants, and descriptive script filenames such as `daily_job_baostock_5min_v3.py`. React/TypeScript files in `web/umi-stock/src/pages/` use PascalCase component names, camelCase state/props, and colocated `.less` styles. No repo-wide `black`, `ruff`, or lint script is committed, so keep edits small, readable, and consistent with nearby files.

## Testing Guidelines
Backend tests are mostly ad hoc Python scripts. Run unit-style coverage with `python3 -m unittest test_insert_minute.py`. Run integration smoke tests like `python3 jobs/test_daily_job_v2.py` only when MySQL, env vars, and external market APIs are available. Name new tests `test_*.py`, mock network calls where possible, and avoid requiring live Baostock or Tushare access for basic validation.

## Commit & Pull Request Guidelines
The visible history uses short, simple subjects (`first commit in nas`). Keep commit titles imperative and concise, and mention the area changed, for example `jobs: harden baostock retry handling`. PRs should state the operational impact, list any schema or cron changes, link related issues, and include screenshots for `web/umi-stock` UI changes. Never commit filled `.env` files, real tokens, or production passwords.
