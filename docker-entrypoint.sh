#!/bin/bash
set -e

if [ -f /mounted-config/crontab ]; then
  cp /mounted-config/crontab /app/crontab
fi

chmod 0644 /app/crontab
crontab /app/crontab

exec /usr/bin/supervisord
