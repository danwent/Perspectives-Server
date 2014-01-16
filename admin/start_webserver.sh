#!/bin/bash

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source $dir/_common_functions.sh

do_setup

# note: we leave the options blank in git so you can override them with your own
# and safely commit a local patch.
# this way you'll never have a conflict when syncing the depo.
# please clear out the options string for any patches you send back
server_options=""

server_pid=$(get_server_pid)

if [ -n "$server_pid" ]
then
	echo "notary is already running"
	exit 1
else
	echo "starting notary..."
	# Important: redirect stderr to stdout,
	# or python throws the error "IOError: [Errno 5] Input/output error"
	# when it is unable to write to stderr when no user is attached
	# TODO: send stderr and stdout to the correct log inside server's python code
	cmd=`$server_command $server_options --echo-screen >> $logdir/$server_logfile 2>&1 &`
	`$cmd`
	echo "notary started from script at $date" >> $logdir/$server_logfile
fi 
