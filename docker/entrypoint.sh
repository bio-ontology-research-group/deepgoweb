#!/usr/bin/env bash
# Container entrypoint. Optionally downloads the model/data assets, then runs the
# requested role. Roles: `web` (gunicorn), `worker` (celery), or any raw command.
set -euo pipefail

# Pull assets unless disabled (set DOWNLOAD_ASSETS=0 when they live on a mounted volume
# that is already populated).
if [ "${DOWNLOAD_ASSETS:-1}" = "1" ]; then
  docker/download_assets.sh
fi

wait_for_db() {
  python - <<'PY'
import os, time, sys
import psycopg2
host=os.environ.get("POSTGRES_HOST","db"); port=os.environ.get("POSTGRES_PORT","5432")
for _ in range(60):
    try:
        psycopg2.connect(host=host, port=port, dbname=os.environ.get("POSTGRES_DB","deepgoweb"),
                         user=os.environ.get("POSTGRES_USER","postgres"),
                         password=os.environ.get("POSTGRES_PASSWORD","postgres")).close()
        sys.exit(0)
    except Exception as e:
        print(f"[entrypoint] waiting for postgres {host}:{port} ... {e}"); time.sleep(2)
sys.exit("postgres not reachable")
PY
}

case "${1:-web}" in
  web)
    wait_for_db
    python manage.py migrate --noinput
    exec gunicorn deepgoweb.wsgi:application \
        --bind 0.0.0.0:8000 \
        --workers "${GUNICORN_WORKERS:-3}" \
        --timeout "${GUNICORN_TIMEOUT:-300}"
    ;;
  worker)
    wait_for_db
    exec celery -A deepgoweb worker -l info \
        --pool "${CELERY_POOL:-prefork}" \
        --concurrency "${CELERY_CONCURRENCY:-2}"
    ;;
  *)
    exec "$@"
    ;;
esac
