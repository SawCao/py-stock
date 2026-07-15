#!/bin/bash
set -u

JOB_NAME="$1"
LOG_FILE="$2"
RUN_MODE="$3"
shift 3

STATUS_DIR="/app/data/cron_status"
STATUS_FILE="${STATUS_DIR}/${JOB_NAME}.json"
LOCK_FILE="${STATUS_DIR}/${JOB_NAME}.lock"
JOB_TIMEOUT_SECONDS="${CRON_JOB_TIMEOUT_SECONDS:-25200}"
STARTED_AT="$(date '+%Y-%m-%d %H:%M:%S')"
PID="$$"
COMMAND="$*"

mkdir -p "$STATUS_DIR"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  printf '%s\n' "[$STARTED_AT] ${JOB_NAME} is already running, skip duplicate launch" >> "$LOG_FILE"
  exit 99
fi

cat > "$STATUS_FILE" <<EOF
{"job_name":"${JOB_NAME}","status":"running","started_at":"${STARTED_AT}","finished_at":null,"exit_code":null,"log_file":"${LOG_FILE}","run_mode":"${RUN_MODE}","pid":${PID},"command":"${COMMAND}"}
EOF

timeout --kill-after=60s "$JOB_TIMEOUT_SECONDS" "$@" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
FINISHED_AT="$(date '+%Y-%m-%d %H:%M:%S')"

if [ "$EXIT_CODE" -eq 0 ]; then
  STATUS="success"
else
  STATUS="failed"
fi

cat > "$STATUS_FILE" <<EOF
{"job_name":"${JOB_NAME}","status":"${STATUS}","started_at":"${STARTED_AT}","finished_at":"${FINISHED_AT}","exit_code":${EXIT_CODE},"log_file":"${LOG_FILE}","run_mode":"${RUN_MODE}","pid":${PID},"command":"${COMMAND}"}
EOF

exit "$EXIT_CODE"
