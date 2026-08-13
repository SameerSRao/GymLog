#!/bin/sh
PORT=${PORT:-80}
export PORT
# Wait up to 60s for the API to respond before starting nginx.
# This ensures nginx resolves api.railway.internal correctly at startup
# rather than caching a failed lookup made before the api is ready.
elapsed=0
until wget -q -O /dev/null "http://${API_HOST}:${API_PORT}/health" 2>/dev/null; do
    if [ "$elapsed" -ge 60 ]; then
        echo "Warning: API not reachable after 60s, starting nginx anyway"
        break
    fi
    echo "Waiting for API (${elapsed}s elapsed)..."
    sleep 2
    elapsed=$((elapsed + 2))
done
echo "API is ready, starting nginx"
exec /docker-entrypoint.sh "$@"
