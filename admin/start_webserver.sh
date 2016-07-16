#!/bin/bash

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source $dir/_common_functions.sh

do_setup

# note: we leave the arguments blank in git so you can override them with your own
# and safely commit a local patch.
# this way you'll never have a conflict when syncing the depo.
# please clear out the args string for any patches you send back
server_args=""

server_pid=$(get_server_pid)

if [ -n "$server_pid" ]
then
	echo "notary is already running"
	exit 1
else
	echo "starting notary..."
	set -x
	$server_command $server_args --logfile
fi 
