#!/bin/sh
alembic upgrade head
gunicorn -k uvicorn.workers.UvicornWorker src.app:app --bind 0.0.0.0:80  --log-level ${LOG_LEVEl-'debug'} --access-logfile '-' --preload --max-requests ${UVICORN_LIMIT_MAX_REQUESTS-2000} --max-requests-jitter 300
