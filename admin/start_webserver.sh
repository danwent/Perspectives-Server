#!/bin/bash 

logdir=../logs
logfile=webserver.log
command='python ../notary_http.py'
pid=`ps -Af | grep "$command" | grep -v grep | awk '{print $2}'`

if [ -n "$pid" ]
then
	echo "notary is already running"
	exit 1
else
	echo "starting notary..."
	date=`date`
	echo "notary started from script at $date" >> $logdir/$logfile
	$command &
fi 
