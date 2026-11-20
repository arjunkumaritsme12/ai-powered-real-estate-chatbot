#!/bin/sh
set -eu

data_dir="${DATA_DIR:-/app/data}"
seed_dir="/app/seed-data"

mkdir -p "$data_dir"
if [ ! -s "$data_dir/scraped_documents.json" ] && [ -f "$seed_dir/scraped_documents.json" ]; then
  cp -a "$seed_dir/." "$data_dir/"
  echo "Initialized the empty data directory from the bundled PropertyIQ knowledge base."
fi

exec "$@"
