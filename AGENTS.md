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

## Data Mapping Notes
For `stock_search`, minute-level matches come from `stock_zh_a_minute_ol_4`, while enrichment and counters come from `stock_zh_a_daily`, `stock_list_cache`, and `stock_industry`.

Important field semantics:
- `stock_zh_a_daily.code` is the plain 6-digit stock code and should be used when joining to minute data codes.
- `stock_zh_a_daily.symbol` includes market prefixes like `sh.600060` and is not suitable for direct joins to `stock_zh_a_minute_ol_4.name`.
- `stock_zh_a_daily.turnover` stores percentage values directly, e.g. `15.8355` means `15.8355%`, so the threshold for "换手率>15%天数" must be `turnover > 15`, not `turnover > 0.15`.

## Build, Test, and Development Commands
Set up Python dependencies with `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt` or run `./setup_py.sh`. Start the full stack with `docker compose up --build`; this launches MySQL, the Flask backend on `:5000`, and the Umi UI on `:8888`. For frontend development, use `cd web/umi-stock && npm install && npm run dev`; build production assets with `npm run build`.

## Coding Style & Naming Conventions
Follow the existing style rather than introducing a new formatter. Python uses 4-space indentation, snake_case function names, uppercase module constants, and descriptive script filenames such as `daily_job_baostock_5min_v3.py`. React/TypeScript files in `web/umi-stock/src/pages/` use PascalCase component names, camelCase state/props, and colocated `.less` styles. No repo-wide `black`, `ruff`, or lint script is committed, so keep edits small, readable, and consistent with nearby files.

## Testing Guidelines
Backend tests are mostly ad hoc Python scripts. Run unit-style coverage with `python3 -m unittest test_insert_minute.py`. Run integration smoke tests like `python3 jobs/test_daily_job_v2.py` only when MySQL, env vars, and external market APIs are available. Name new tests `test_*.py`, mock network calls where possible, and avoid requiring live Baostock or Tushare access for basic validation.

## Commit & Pull Request Guidelines
The visible history uses short, simple subjects (`first commit in nas`). Keep commit titles imperative and concise, and mention the area changed, for example `jobs: harden baostock retry handling`. PRs should state the operational impact, list any schema or cron changes, link related issues, and include screenshots for `web/umi-stock` UI changes. Never commit filled `.env` files, real tokens, or production passwords.
