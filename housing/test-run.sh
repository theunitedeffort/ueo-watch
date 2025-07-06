#!/bin/bash
set -e

readonly TIMESTAMP=$(date +%Y%m%d_%H%M%S)
readonly LOG_PATH="/tmp/urlwatch_debug_$TIMESTAMP.log"
readonly TEST_RECIPIENT=trevor@theunitedeffort.org

echo "Running test..."

readonly TEMP_FILE=$(mktemp)
readonly TEMP_URLS=$(mktemp)

function cleanup {
  echo "Cleaning up"
  echo "  Removing $TEMP_FILE and $TEMP_URLS"
  rm -f "$TEMP_FILE"
  rm -f "$TEMP_URLS"
}

trap cleanup EXIT

# Get into a known directory we can run commands from
readonly ROOT_DIR=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$ROOT_DIR"

# Store a backup copy of the database in case actionable changes are detected
# during testing that need to be kept out of the database and saved for
# an actual urlwatch run with proper reporting.
echo "Backing up database"
cp cache.db "cache_$TIMESTAMP.db.bak"

# Change the email address reports are sent to so that we don't send test
# reports to a production email list.
# Change the max_tries parameter so that errors are immediately reported.
echo "Changing report recipient to $TEST_RECIPIENT and max_tries to 1"
cat urlwatch.yaml | \
  sed -E "s/^([[:blank:]]*to: )(.*)/\1'$TEST_RECIPIENT'/" | \
  sed -E "s/^([[:blank:]]*max_tries: )(.*)/\11/" | \
  tr '\n' '\r' | \
  sed -E "s/(\r[[:blank:]]*jira:\r[[:blank:]]*enabled:) true/\1 false/" | \
  tr '\r' '\n' > "$TEMP_FILE"
echo "Temporary urlwatch config created at $TEMP_FILE"
cat urls.yaml | \
  sed -E "s/^([[:blank:]]*max_tries: )(.*)/\11/" > "$TEMP_URLS"
echo "Temporary urls list created at $TEMP_URLS"

echo "Logging debug output to $LOG_PATH"
echo "Running urlwatch..."
echo
urlwatch -v --hooks ../config/hooks.py --urls "$TEMP_URLS" --config "$TEMP_FILE" --cache cache.db 2> "$LOG_PATH"
echo

echo "Done! Log is at $LOG_PATH"
