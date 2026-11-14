#!/bin/sh
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p "${DATA_DIR:-/app/data}" "${MODELS_DIR:-/models}"
  chown -R app:app "${DATA_DIR:-/app/data}" "${MODELS_DIR:-/models}" 2>/dev/null || true
  exec setpriv --reuid=app --regid=app --init-groups "$@"
fi
exec "$@"
