# ueo-watch
This repository contains configuration files to set up URL watching jobs relevant to UEO.  There are also a few convenience scripts for maintaining the system.  Sets of jobs are organized into folders within this project.  At the moment there is a set of housing jobs (`housing` folder) and benefits eligibility jobs (`eligibility` folder).

# Environment Setup
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
`urlwatch` needs to be present on the machine and in the `PATH` for the various run scripts to work.  Production runs of `ueo-watch` use the `dev` branch of the [trevorshannon/urlwatch](https://github.com/trevorshannon/urlwatch) fork, though you can try another version of `urlwatch` if you wish.

```
git clone https://github.com/trevorshannon/urlwatch.git
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

### Optional: Pyppeteer
The `urlwatch` fork used by this project still uses Pyppeteer to run `navigate` jobs.  While the intention is to migrate away from Pyppeteer and towards Playwright, should you want to install Pyppeteer, you can follow these steps.  Note that the default set of Python packages in this project's `requirements.txt` includes Playwright, so that will also be installed unless you modify `requirements.txt`.  This Pyppeteer installation is done outside any [virtual environment](https://www.freecodecamp.org/news/how-to-setup-virtual-environments-in-python/) (because that's how the production system was originally set up), but you can certainly do it within one.

```
pip3 install pyppeteer
```

The default Chrome version used by pyppeteer does not work for this project, but you can force it to use a different version with an environment variable:

```
echo 'export PYPPETEER_CHROMIUM_REVISION=839947' >> ~/.bashrc
```

Running the Pyppeteer install command will ensure Chrome is downloaded and ready for Pyppeteer to use:

```
~/.local/bin/pyppeteer-install
```

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

And finally, initialize Playwright:

```
playwright install
```


# First Run
It can be useful to set up some test jobs to ensure all is working.  These jobs can be whatever you please, but this section suggests some that may be helpful in highlighting  problems with your environment.  **The production jobs (under `housing` and `eligibility`) take a long time to run and will notify other users by default when they finish.**

```
cd ~/ueo-watch/example
urlwatch --hooks ../config/hooks.py --urls urls.yaml --config urlwatch.yaml --cache cache.db
```

You should see output with many "NEW" URLs and no "ERROR" URLs.  If you run the above `urlwatch` command again, you should see output with diffs for each URL.

