#!/bin/bash

MAX_TRIES=5
RETRY_DELAY_S=2

if [ -z "$1" ]
  then
  	echo "Provide the name of the GCE instance to update."
    echo "For example:"
    echo "  $0 ueo-vm-1"
    exit 1
fi

gcloud compute instances start "$1"

echo "Connecting to \"$1\" via SSH..."
COUNT=0
until gcloud compute ssh "$1" --command "cd ueo-watch; git pull"
do
	((COUNT++))
	ATTEMPT_COUNT="Attempt $COUNT:"
	if [ $COUNT -ge $MAX_TRIES ]
		then
			echo "$ATTEMPT_COUNT No response, exiting."
			exit 1
	fi
	echo "$ATTEMPT_COUNT No response, trying again."
	sleep $RETRY_DELAY_S
done

exit 0