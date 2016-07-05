#!/bin/bash

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source $dir/_common_functions.sh

do_setup

rate=100
timeout=10

# note: we leave the arguments blank in git so you can override them with your own
# and safely commit a local patch.
# this way you'll never have a conflict when syncing the depo.
# please clear out the args string for any patches you send back
database_args=""
scan_args=""

scan_pid=$(get_scan_pid)

if [ -n "$scan_pid" ]
then
	echo "ignoring request to start scan from script because scanner is already running. $date" >> $logdir/$scan_logfile
	exit 1
fi


echo "starting scan from script at $date" >> $logdir/$scan_logfile
# Important: redirect stderr to stdout,
# or python throws the error "IOError: [Errno 5] Input/output error"
# when it is unable to write to stderr when no user is attached
scan_cmd=`python notary_util/list_services.py $database_args | $scan_command $database_args $scan_args --scans $rate --timeout $timeout --logfile &`
echo $scan_cmd
`$scan_cmd`

