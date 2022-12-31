#!/bin/bash
set -e

readonly LOG_PATH=/tmp/urlwatch_debug.log
readonly TEST_RECIPIENT=trevor@theunitedeffort.org

echo "Running test..."

readonly TEMP_FILE=$(mktemp)

function cleanup {
  echo "Cleaning up"
  echo "  Removing $TEMP_FILE"
  rm -f "$TEMP_FILE"
}

trap cleanup EXIT

# Get into a known directory we can run commands from
readonly ROOT_DIR=$( cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )
cd "$ROOT_DIR"

# Store a backup copy of the database in case actionable changes are detected
# during testing that need to be kept out of the database and saved for
# an actual urlwatch run with proper reporting.
echo "Backing up database"
cp cache.db cache-backup.db

# Change the email address reports are sent to so that we don't send test
# reports to a production email list.
echo "Changing report recipient"
cat urlwatch.yaml | sed -E "s/^([[:blank:]]*to: )(.*)/\1'$TEST_RECIPIENT'/" > "$TEMP_FILE"

echo "Running urlwatch..."
urlwatch -v --hooks ../config/hooks.py --urls urls.yaml --config "$TEMP_FILE" --cache cache.db 2> "$LOG_PATH"

echo "Done! Log is at $LOG_PATH"
