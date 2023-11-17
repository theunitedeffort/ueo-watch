#!/bin/bash

MAX_TRIES=5
RETRY_DELAY_S=2

error() {
  echo -e "\033[31mERROR: $1\033[0m"
  exit 1
}

remote_run() {
  echo "Running on \"$vm_name\": $1"
  gcloud compute ssh "$vm_name" --command "$1"
}

cleanup() {
  # If the script exits prematurely, this will reset the urls.yaml to the
  # initial configuration. If the script exits at the end as intended, this
  # will do nothing since we checked for a clean working directory initially.
  git checkout -- "$local_config_path"
}

if [ -z "$1" ] || [ -z "$2" ] || [ -z "$3" ]
  then
    echo "Changes a URL in a urlwatch config to a new value and also updates the "
    echo "remote database to move existing snapshots to the new URL."
    echo ""
    echo "Usage:"
    echo "  $0 config-dir url-to-change new-url [vm-name]"
    exit 1
fi

root_dir=$(dirname "$0")
config_dir=$1
old_url=$2
new_url=$3
vm_name=$4
if [ -z "$vm_name" ]
  then
    vm_name="ueo-vm-1"
fi
local_config_path="$root_dir/$config_dir/urls.yaml"

# https://unix.stackexchange.com/a/155077
if output=$(git status --untracked-files=no --porcelain) && [ -z "$output" ]; then
  echo "Clean working directory, continuing."
else
  git status --untracked-files=no
  error "This command must be run on a clean working directory."
fi

trap cleanup EXIT

url_match=$(cat "$local_config_path" | grep ": $old_url\$")
if [ -z "$url_match" ]; then
  error "No such URL $old_url in $local_config_path"
fi

echo "Updating $local_config_path with new URL $new_url"
sed -i '' "s|$old_url|$new_url|" "$local_config_path"

git commit -a -m "Automated update of $old_url to $new_url"
git push

gcloud compute instances start "$vm_name"

echo "Connecting to \"$vm_name\" via SSH..."
count=0
until remote_run "echo"
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

remote_run "cd ueo-watch/$config_dir && cp cache.db cache-change-url.db.bak"
remote_run "cd ueo-watch/$config_dir && ~/urlwatch/urlwatch --urls urls.yaml --config urlwatch.yaml --cache cache.db --change-location $old_url $new_url"
remote_run "cd ueo-watch && git checkout -- $config_dir/urls.yaml && git pull"

