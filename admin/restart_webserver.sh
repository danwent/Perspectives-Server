#!/bin/bash

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source $dir/_common_functions.sh

$dir/stop_webserver.sh

maxwait=30 #seconds
slept=0

while [ $slept -lt $maxwait ]
do
	server_pid=$(get_server_pid)

	if [ -n "$server_pid" ]
	then
		# server is still running; wait for it to shut down
		slept=$(( $slept + 1 ))
		#echo "sleeping $slept" seconds
		sleep 1
	else
		break
	fi
done

if [ $slept -eq $maxwait ]
then
	echo "ERROR: server did not stop after $maxwait seconds"
fi


$dir/start_webserver.sh

