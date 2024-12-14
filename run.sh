#!/bin/bash
set -x

echo "Running..."
date

# Get into a known directory we can run commands from
root_dir=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$root_dir"

# Run housing jobs
cp housing/cache.db housing/cache_before_latest_run.db.bak
urlwatch -v --hooks config/hooks.py --urls housing/urls.yaml --config housing/urlwatch.yaml --cache housing/cache.db 2> housing/urlwatch_debug.log 1> housing/urlwatch_output.log
# Check for errors in the housing debug log.
if [ $? -gt 0 ]
then
  body="$(tail -n 50 housing/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch housing error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t
fi
body="$(grep "ERROR: " housing/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch housing error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t
# Database garbage collection
urlwatch --hooks config/hooks.py --urls housing/urls.yaml --config housing/urlwatch.yaml --cache housing/cache.db --gc-cache 5
timestamp=$(date +%Y%m%d_%H%M%S)
gsutil cp housing/cache.db "gs://ueo-changes/housing/cache/cache_$timestamp.db"

# Run eligibility jobs
cp eligibility/cache.db eligibility/cache_before_latest_run.db.bak
urlwatch -v --hooks config/hooks.py --urls eligibility/urls.yaml --config eligibility/urlwatch.yaml --cache eligibility/cache.db 2> eligibility/urlwatch_debug.log 1> eligibility/urlwatch_output.log
# Check for errors in the eligibility debug log.
if [ $? -gt 0 ]
then
  body="$(tail -n 50 eligibility/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch eligibility error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t
fi
body="$(grep "ERROR: " eligibility/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch eligibility error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t
# Database garbage collection
urlwatch --hooks config/hooks.py --urls eligibility/urls.yaml --config eligibility/urlwatch.yaml --cache eligibility/cache.db --gc-cache 5
timestamp=$(date +%Y%m%d_%H%M%S)
gsutil cp eligibility/cache.db "gs://ueo-changes/eligibility/cache/cache_$timestamp.db"

# Run autohouse jobs
# First make the urls.py for urlwatch
python3 autohouse/make_urls.py > autohouse/make_urls_debug.log 2>&1
body="$(grep -i -B 10 "error: " autohouse/make_urls_debug.log)" && now="$(date)" && printf "Subject: autohouse make_urls error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t

# Then run urlwatch
cp autohouse/cache.db autohouse/cache_before_latest_run.db.bak
urlwatch -v --hooks config/hooks.py --urls autohouse/urls.yaml --config autohouse/urlwatch.yaml --cache autohouse/cache.db 2> autohouse/urlwatch_debug.log 1> autohouse/urlwatch_output.log
# Check for errors in the autohouse debug log.
if [ $? -gt 0 ]
then
  body="$(tail -n 50 autohouse/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch autohouse error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t
fi
body="$(grep "ERROR: " autohouse/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch autohouse error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t
# Database garbage collection
urlwatch --hooks config/hooks.py --urls autohouse/urls.yaml --config autohouse/urlwatch.yaml --cache autohouse/cache.db --gc-cache 5
timestamp=$(date +%Y%m%d_%H%M%S)
gsutil cp autohouse/cache.db "gs://ueo-changes/autohouse/cache/cache_$timestamp.db"

echo "Done."
