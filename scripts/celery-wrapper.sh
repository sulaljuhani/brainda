#!/bin/sh
# Wrapper around celery to improve `celery call` UX in containers.
# If the `call` subcommand is used without a timeout, add `--timeout=30`
# so the command waits for execution and prints a SUCCESS line.

REAL_CELERY=${REAL_CELERY:-/usr/local/bin/celery-real}

# If the real celery binary is not in the default location, try to find it
if [ ! -x "$REAL_CELERY" ]; then
  REAL_CELERY=$(command -v celery-real 2>/dev/null || true)
fi

if [ -z "$REAL_CELERY" ] || [ ! -x "$REAL_CELERY" ]; then
  echo "celery wrapper error: cannot locate real celery binary" >&2
  exit 127
fi

case " $* " in
  *" call "*)
    # Extract the task name: assume last argument is the task
    # e.g., celery -A worker.tasks call worker.tasks.cleanup_old_data
    set -- "$@"
    task_name=""
    for arg in "$@"; do task_name="$arg"; done
    if [ -n "$task_name" ]; then
      # Run a small Python snippet to enqueue and wait for the result
      exec python - "$task_name" <<'PY'
import sys
task_name = sys.argv[1]
try:
    from worker.tasks import celery_app
except Exception as e:
    print(f"celery wrapper error: cannot import celery app: {e}", file=sys.stderr)
    sys.exit(1)

try:
    result = celery_app.send_task(task_name)
    value = result.get(timeout=30)
    print("SUCCESS")
    if value is not None:
        try:
            print(value)
        except Exception:
            pass
    sys.exit(0)
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
PY
    fi
    ;;
esac

exec "$REAL_CELERY" "$@"
