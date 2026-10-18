#!/bin/sh
set -eu
# Idempotent first start. Explicitly remove/recreate only these named application
# containers when installing a newer release; never touch the existing web/MySQL services.
if ! docker container inspect skill-finder >/dev/null 2>&1; then
  docker run -d --name skill-finder --restart unless-stopped --network host \
    --user 65532:65532 --read-only --tmpfs /tmp:rw,nosuid,nodev,size=128m \
    --security-opt no-new-privileges --cap-drop ALL --pids-limit 160 \
    --memory 640m --memory-swap 1280m --cpus 1 \
    --log-opt max-size=10m --log-opt max-file=3 \
    --env-file /etc/skill-finder/service.env \
    -v /var/lib/skill-finder:/data \
    skill-finder:20261018
fi
if [ "${START_OPENCLAW:-1}" = 1 ] && ! docker container inspect skill-finder-openclaw >/dev/null 2>&1; then
  docker run -d --name skill-finder-openclaw --restart unless-stopped --network host \
    --user 1000:1000 --read-only \
    --security-opt no-new-privileges --cap-drop ALL --pids-limit 160 \
    --memory 768m --memory-swap 1536m --cpus 0.5 \
    --log-opt max-size=10m --log-opt max-file=3 \
    --env-file /etc/skill-finder/openclaw.env \
    -e HOME=/home/node -e NODE_OPTIONS=--max-old-space-size=384 \
    -e OPENCLAW_NO_RESPAWN=1 -e TZ=Asia/Shanghai \
    -e XDG_CACHE_HOME=/home/node/.openclaw/cache \
    -e NODE_COMPILE_CACHE=/home/node/.openclaw/cache/node \
    -v /opt/skill-finder/openclaw-tools:/tools:ro \
    -v /opt/skill-finder/openclaw-home:/home/node/.openclaw \
    -v /opt/skill-finder/openclaw-tmp:/tmp \
    node:24-bookworm-slim node /tools/node_modules/openclaw/openclaw.mjs \
    gateway --bind loopback --port 18789
fi
