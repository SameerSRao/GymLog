#!/bin/sh
elapsed=0
until wget -q -O /dev/null "http://${API_HOST}:${API_PORT}/health" 2>/dev/null; do
    if [ "$elapsed" -ge 60 ]; then
        echo "API not reachable after 60s, starting nginx anyway"
        break
    fi
    echo "Waiting for API (${elapsed}s)..."
    sleep 2
    elapsed=$((elapsed + 2))
done
exec /docker-entrypoint.sh "$@"
