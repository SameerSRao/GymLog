#!/bin/sh
# Read the DNS resolver from /etc/resolv.conf.
# nginx needs IPv6 addresses in brackets.
NS=$(grep -m1 '^nameserver' /etc/resolv.conf | awk '{print $2}')
case "$NS" in
    *:*) export NGINX_RESOLVER="[$NS]" ;;
    *)   export NGINX_RESOLVER="$NS" ;;
esac

# Wait up to 60s for the API to be reachable so nginx doesn't cache
# a failed DNS lookup at startup.
elapsed=0
until wget -q -O /dev/null "http://${API_HOST}:${API_PORT}/health" 2>/dev/null; do
    if [ "$elapsed" -ge 60 ]; then
        echo "Warning: API not reachable after 60s, starting nginx anyway"
        break
    fi
    echo "Waiting for API (${elapsed}s)..."
    sleep 2
    elapsed=$((elapsed + 2))
done

exec /docker-entrypoint.sh "$@"
