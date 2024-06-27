# ueo-watch
This repository contains configuration files to set up URL watching jobs relevant to UEO.  There are also a few convenience scripts for maintaining the system.

# Environment
These configuration files were written to be used on a Google Compute Engine instance running Linux (Debian Buster).  The instructions below are meant to replicate the environment as it currently exists for production runs. 

## Prerequisites
This is meant to be an exhaustive list of prerequisites, but some may be missing!  Documentation edits and updates are welcome.

### urlwatch
`urlwatch` needs to be present on the machine and in the `PATH` for the various run scripts to work.  Production runs of `ueo-watch` use the `dev` branch of the [trevorshannon/urlwatch](https://github.com/trevorshannon/urlwatch) fork, though you can try another version of `urlwatch` if you wish.

```
cd ~
git clone https://github.com/trevorshannon/urlwatch.git
```

The `urlwatch` binary should be added to your path so it can be more easily called from the command line and scripts.

```
echo 'export PATH="$PATH:$HOME/urlwatch"' >> ~/.bashrc
```
###
