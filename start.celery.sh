celery -A src.tasks.tasks beat --loglevel=info &
celery -A src.tasks.tasks worker --max-tasks-per-child 180 --concurrency=2
