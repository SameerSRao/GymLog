#!/bin/sh
# Extract the first nameserver from /etc/resolv.conf so nginx can use it
# as a dynamic resolver (required when proxy_pass uses a variable).
NGINX_RESOLVER=$(grep -m1 '^nameserver' /etc/resolv.conf | awk '{print $2}')
export NGINX_RESOLVER
exec /docker-entrypoint.sh "$@"
