#!/bin/bash

MAX_TRIES=5
RETRY_DELAY_S=2

if [ -z "$1" ]
  then
  	echo "Provide the name of the GCE instance to update."
    echo "For example:"
    echo "  $0 ueo-vm-1 [diff-lookback]"
    exit 1
fi

gcloud compute instances start "$1"

echo "Connecting to \"$1\" via SSH..."
count=0
until gcloud compute ssh "$1" --command "cd ueo-watch; git pull"
do
	((count++))
	attempt_count="Attempt $count:"
	if [ $count -ge $MAX_TRIES ]
		then
			echo "$attempt_count No response, exiting."
			exit 1
	fi
	echo "$attempt_count No response, trying again."
	sleep $RETRY_DELAY_S
done

lookback=$2
if [ -z "$lookback" ]
  then
    lookback=1
fi

new_urls=$(gcloud compute ssh "$1" --command "cd ueo-watch; git diff HEAD~$lookback | grep -E '^\+((url)|(navigate)|(user_visible_url)):|^\+\+\+ b/' | sed -e 's/+\(\(url\)\|\(navigate\)\|\(user_visible_url\)\): //g' | sed -e 's/+++ b\//<FILE> /g'")
old_ifs=$IFS
IFS=$'\n'
new_urls=($new_urls)
IFS=$old_ifs

if [ ${#new_urls[@]} != 0 ]
then
  echo "URLs added:"
  echo ""
  printf '%s\n' "${new_urls[@]}"
  echo ""

  basepath=""
  for url in "${new_urls[@]}"
  do
    if [[ "$url" =~ ^\<FILE\>\ .*  ]]
    then
      filepath=$(echo "$url" | sed -e 's/<FILE> //')
      basepath=$(dirname "$filepath")
    else
      echo "Press Enter to verify $url"
      read
      gcloud compute ssh "$1" --command "cd /home/trevor/ueo-watch/$basepath; . ../prod-env/bin/activate; /home/trevor/urlwatch/urlwatch --urls urls.yaml --config urlwatch.yaml --cache cache.db --hooks ../config/hooks.py --test-filter \"$url\"" | less
    fi
  done
fi

exit 0