#!/bin/bash

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source $dir/_common_functions.sh

do_setup

# on launch the database and key pair are automatically created if necessary

# setup crontab
crontab crontab_content

