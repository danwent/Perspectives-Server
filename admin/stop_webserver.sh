#!/bin/bash 

logdir=../logs
logfile=webserver.log
command='python ../notary_http.py'
pid=`ps -Af | grep "$command" | grep -v grep | awk '{print $2}'`

if [ -n "$pid" ]
then
	kill $pid 
	echo "Stopped notary"
	date=`date`
	echo "notary stopped from script at $date" >> $logdir/$logfile
else
	echo "No notary was running"
fi 

