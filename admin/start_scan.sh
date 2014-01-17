#!/bin/bash

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source $dir/_common_functions.sh

do_setup

rate=100
timeout=10

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
scan_cmd=`python notary_util/list_services.py | $scan_command --scans $rate --timeout $timeout >> $logdir/$scan_logfile 2>&1 &`
echo $scan_cmd
`$scan_cmd`

