#!/bin/bash

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source $dir/_common_functions.sh

do_setup

scan_pid=$(get_scan_pid)

if [ -n "$scan_pid" ];
then
	echo "killing scanner from script at $date" >> $logdir/$scan_logfile
	kill $scan_pid
else
	echo "Scanner is not running"
fi

