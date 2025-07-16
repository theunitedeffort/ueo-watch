# ueo-watch
This repository contains configuration files to set up URL watching jobs relevant to UEO.  There are also a few convenience scripts for maintaining the system.  Sets of jobs are organized into folders within this project.  At the moment there is a set of housing jobs (`housing` folder), benefits eligibility jobs (`eligibility` folder), and automated affordable housing search jobs (`autohouse` folder).

# Setup
These configuration files were written to be used on a Google Compute Engine instance running Linux (Debian Buster).  The instructions below are meant to replicate the environment as it currently exists for production runs. 

## Prerequisites
This is meant to be an exhaustive list of prerequisites, but some may be missing!  Documentation edits and updates are welcome.

### Python >= 3.8
The default `python3` with Debian Buster is 3.7 but `urlwatch` and other libs need >= 3.8.  Install Python 3.10 (or whatever version you are happiest with):

```
cd ~
sudo apt-get install wget build-essential libreadline-gplv2-dev libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev libbz2-dev libffi-dev zlib1g-dev liblzma-dev -y
curl -O https://www.python.org/ftp/python/3.10.14/Python-3.10.14.tgz
tar -xvf Python-3.10.13.tgz
cd Python-3.10.13
./configure --enable-optimizations
make test
make altinstall
```

### urlwatch
[urlwatch](https://urlwatch.readthedocs.io/en/latest/index.html) needs to be present on the machine and in the `PATH` for the various run scripts to work.  Production runs of `ueo-watch` use the `dev` branch of the [trevorshannon/urlwatch](https://github.com/trevorshannon/urlwatch) fork, though you can try another version of `urlwatch` if you wish.

```
cd ~
git clone https://github.com/trevorshannon/urlwatch.git
```

Switch to the `dev` branch which (confusingly) is what's used for our production runs

```
cd urlwatch
git checkout dev
```

The `urlwatch` binary should be added to your path so it can be more easily called from the command line and scripts.

```
echo 'export PATH="$PATH:$HOME/urlwatch"' >> ~/.bashrc
```

### pdftotext
While the `pdftotext` Python package will be installed in the Installation step below, there are some [OS-specific dependencies](https://github.com/jalan/pdftotext?tab=readme-ov-file#os-dependencies) for that package that must be installed separately.

```
sudo apt install build-essential libpoppler-cpp-dev pkg-config python3-dev
```

## Google Cloud Setup
The jobs in `autohouse` are meant to search for affordable housing properties matching a given set of search parameters.  These search parameters are stored on Google Drive in a Google Sheet.  A separate script generates the list of jobs for urlwatch from this spreadsheet and therefore needs access to the sheet.

The below assumes the existence of a Google Cloud project.

### Create a Google Cloud service account
1. Go to Cloud Console [Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts).
1. Create a new service account with no roles.
1. Clicking on the new service account on the [Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts) page and go to the Keys tab.
1. Add a new JSON key by selecting **Add key > Create new key** and choose the JSON option.
1. Save the key in a secure location.

### Enable Google Drive API
1. Go to the [Google Drive API](https://console.developers.google.com/apis/api/drive.googleapis.com/overview) on the APIs & Services page of your Google Cloud project.
1. Click on Enable API.

### Share search parameters spreadsheet with the service account
1. Find the spreadsheet containing housing search parameters on Google Drive.
1. Using the Drive UI, share the spreadsheet with the email address associated with the new service account.  It will likely be of the form `{ID}@{PROJECT}.iam.gserviceaccount.com`.  Provide **view-only** access to this email address.


## Installation
First, clone this repo:

```
cd ~
git clone https://github.com/theunitedeffort/ueo-watch.git
```

Then, set up a Python virtual environment to manage the various Python libraries that will be installed.

```
cd ~/ueo-watch
mkdir env
/usr/local/bin/python3.10 -m venv env
. env/bin/activate
```

Install the dependencies:

```
pip3 install -r requirements.txt
```

## Initialization
The `urlwatch` fork used by this project still uses Pyppeteer to run `navigate` jobs.  While the intention is to migrate away from Pyppeteer and towards Playwright, the production environment still uses Pyppeteer. The default Chrome version used by pyppeteer does not work for this project, but you can force it to use a different version with an environment variable:

```
echo 'export PYPPETEER_CHROMIUM_REVISION=839947' >> ~/.bashrc
```

Running the Pyppeteer install command will ensure Chrome is downloaded and ready for Pyppeteer to use:

```
source ~/.bashrc
~/.local/bin/pyppeteer-install
```


# First Run
It can be useful to set up some test jobs to ensure all is working.  These jobs can be whatever you please, but this section suggests some that may be helpful in highlighting  problems with your environment.  **The production jobs (under `housing` and `eligibility`) take a long time to run and will notify other users by default when they finish.**

```
cd ~/ueo-watch/example
urlwatch --hooks ../config/hooks.py --urls urls.yaml --config urlwatch.yaml --cache cache.db
```

You should see output with many "NEW" URLs and no "ERROR" URLs.  If you run the above `urlwatch` command again, you should see output with diffs for each URL.

# Reporting Setup
The production system reports changes via an email reporter, a Google Cloud Storage reporter, and a Jira reporter.  All are custom reporters defined in [hooks.py](https://github.com/theunitedeffort/ueo-watch/blob/main/config/hooks.py).  Some setup needs to be done for those reporters to work correctly.

## Email reporter
Sendgrid is a convenient tool to automatically send emails from a Google Compute Engine instance.  To set this up, follow the guide published by Google Cloud on [sending email with Sendgrid using Postfix](https://cloud.google.com/compute/docs/tutorials/sending-mail/using-sendgrid#postfixsendgrid). Note you must have a [Sendgrid API key](https://cloud.google.com/compute/docs/tutorials/sending-mail/using-sendgrid#before-you-begin), which is free.

The max message size should be set to match the SendGrid system and it's convenient to set up bounce handling.  Add the following to the end of `/etc/postfix/main.cf`

```
# size limit from sendgrid server
message_size_limit = 31457280

# ensure bounces get reported
notify_classes = bounce, resource, software
bounce_notice_recipient = you@yourdomain.com
bounce_template_file = /etc/postfix/bounce.cf
```

Create `/etc/postfix/bounce.cf` and fill it with:

```
# This failure template is used for undeliverable mail.

failure_template = <<EOF
Charset: us-ascii
From: no-reply@theunitedeffort.org
Subject: Undelivered Mail Returned to Sender
Postmaster-Subject: Postmaster Copy: Undelivered Mail

Undeliverable mail!

EOF
```

## GCS reporter
The email reports a simply summaries of what changed.  The full change report is in HTML format and gets uploaded to Google Cloud Storage.  This reporter works using the `gsutil` command and a service account.  Set up service account access by following [this helpful guide](https://gist.github.com/ryderdamen/926518ddddd46dd4c8c2e4ef5167243d).

## Jira reporter
Reported changes generate issues in Jira for better tracking and process visibility.  To use the Jira reporter, a Jira API key is needed.  This API key should be stored in a .netrc file. If no such file exists, create  `~/.netrc` and fill it with something like:

```
machine ueo.atlassian.net
login myaccount@theunitedeffort.org
password MY_API_KEY
```

# Cronjob Setup
To have the ueo-watch jobs run daily, edit the cron table with:

```
crontab -e
```

And add the following job, replacing `YOUR_USERNAME` with your username and `YOUR_VENV` with the name of your python virtual environment (which you're definitely using, right??) on the GCE instance:

```
0 6 * * * export PATH=$PATH:/home/YOUR_USERNAME/urlwatch; export PYPPETEER_CHROMIUM_REVISION=839947; . /home/YOUR_USERNAME/ueo-watch/YOUR_VENV/bin/activate && /home/YOUR_USERNAME/ueo-watch/run.sh > /home/YOUR_USERNAME/ueo-watch/run.log 2>&1
```

# Acknowledgements
Thanks to [Tang3672](https://github.com/Tang3672) for contributions (outside of GitHub) to the `autohouse` project.
