#!/bin/sh
set -eu

api_base_url="${API_BASE_URL:-}"
case "$api_base_url" in
  *[!A-Za-z0-9:/._-]*)
    echo "API_BASE_URL may contain only URL characters; refusing unsafe runtime config." >&2
    exit 1
    ;;
esac

printf 'window.PROPERTYIQ_API_URL = "%s";\n' "$api_base_url" \
  > /usr/share/nginx/html/runtime-config.js
