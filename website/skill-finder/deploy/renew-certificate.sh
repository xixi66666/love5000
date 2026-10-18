#!/bin/sh
set -eu
docker run --rm --network host --memory 256m \
  -e PYTHONPATH=/tools \
  -v /opt/skill-finder/certbot-tools:/tools:ro \
  -v /opt/skill-finder/letsencrypt:/etc/letsencrypt \
  -v /opt/skill-finder/acme:/acme \
  python:3.12-slim-bookworm python /tools/bin/certbot renew --quiet --no-random-sleep-on-renew
nginx -t && nginx -s reload
