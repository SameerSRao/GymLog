#!/bin/sh
# Read the first nameserver from /etc/resolv.conf.
# nginx requires IPv6 addresses in brackets, so wrap them if needed.
NS=$(grep -m1 '^nameserver' /etc/resolv.conf | awk '{print $2}')
case "$NS" in
    *:*) NGINX_RESOLVER="[$NS]" ;;
    *)   NGINX_RESOLVER="$NS" ;;
esac
export NGINX_RESOLVER
exec /docker-entrypoint.sh "$@"
