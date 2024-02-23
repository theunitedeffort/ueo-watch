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
if [ $? -gt 0 ]
then
  body="$(tail -n 50 housing/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch housing error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t
fi
body="$(grep "ERROR: " housing/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch housing error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t
# Database garbage collection
urlwatch  --urls housing/urls.yaml --config housing/urlwatch.yaml --cache housing/cache.db --gc-cache 5

# # Run market rate housing (test) jobs
# urlwatch -v --hooks config/hooks.py --urls housing_mr_testing/urls.yaml --config housing_mr_testing/urlwatch.yaml --cache housing_mr_testing/cache.db 2> housing_mr_testing/urlwatch_debug.log 1> housing_mr_testing/urlwatch_output.log
# # Check for errors in the debug log.
# if [ $? -gt 0 ]
# then
#   body="$(tail -n 50 housing_mr_testing/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch housing_mr_testing error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t
# fi
# body="$(grep "ERROR: " housing_mr_testing/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch housing_mr_testing error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t
# # Database garbage collection
# urlwatch  --urls housing_mr_testing/urls.yaml --config housing_mr_testing/urlwatch.yaml --cache housing_mr_testing/cache.db --gc-cache 5

# Run eligibility jobs
urlwatch -v --hooks config/hooks.py --urls eligibility/urls.yaml --config eligibility/urlwatch.yaml --cache eligibility/cache.db 2> eligibility/urlwatch_debug.log 1> eligibility/urlwatch_output.log
# Check for errors in the eligibility debug log.
if [ $? -gt 0 ]
then
  body="$(tail -n 50 eligibility/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch eligibility error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t
fi
body="$(grep "ERROR: " eligibility/urlwatch_debug.log)" && now="$(date)" && printf "Subject: urlwatch eligibility error [$now]\nFrom: Changebot <changebot@theunitedeffort.org>\nTo: trevor@theunitedeffort.org\n\n$body" | /sbin/sendmail -oi -t
# Database garbage collection
urlwatch  --urls eligibility/urls.yaml --config eligibility/urlwatch.yaml --cache eligibility/cache.db --gc-cache 5

echo "Done."
