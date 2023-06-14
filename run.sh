#!/bin/bash
set -x

echo "Running..."
date

# Get into a known directory we can run commands from
root_dir=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$root_dir"

# Run housing jobs
urlwatch -v --hooks config/hooks.py --urls housing/urls.yaml --config housing/urlwatch.yaml --cache housing/cache.db 2> housing/urlwatch_debug.log 1> housing/urlwatch_output.log

# Check for errors in the housing debug log.
body="$(grep "ERROR: " housing/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch housing error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t

# Database garbage collection
urlwatch  --urls housing/urls.yaml --config housing/urlwatch.yaml --cache housing/cache.db --gc-cache 5

echo "Done."
