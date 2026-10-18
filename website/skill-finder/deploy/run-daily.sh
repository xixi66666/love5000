#!/bin/sh
set -eu
# Keep host-wide cron and web-triggered generation from overlapping.
exec 9>/run/skill-finder-daily.lock
flock -n 9 || exit 0
case "${1:-}" in
  collect|generate|notify) docker exec skill-finder python -m app.daily.cli "$1" ;;
  *) echo 'usage: run-daily.sh collect|generate|notify' >&2; exit 2 ;;
esac
