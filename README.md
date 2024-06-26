# ueo-watch
This repository contains configuration files to set up URL watching jobs relevant to UEO.  There are also a few convenience scripts for maintaining the system.

# Environment
These configuration files were written to be used on a Google Compute Engine instance running Linux (Debian Buster).

## Prerequisites
This is meant to be an exhaustive list of prerequisites, but some may be missing!  Documentation edits and updates are welcome.

### urlwatch
`urlwatch` needs to be present on the machine and in the `PATH` for the various run scripts to work.  These config files are meant to be used with the `dev` branch of the [trevorshannon/urlwatch](https://github.com/trevorshannon/urlwatch) fork.
