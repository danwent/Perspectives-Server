#!/bin/bash

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source $dir/_common_functions.sh

do_setup

server_pid=$(get_server_pid)

if [ -n "$server_pid" ]
then
	kill $server_pid
	echo "Stopped notary"
	echo "notary stopped from script at $date" >> $logdir/$server_logfile
else
	echo "No notary was running"
fi 

