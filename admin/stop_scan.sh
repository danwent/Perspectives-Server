#!/bin/bash 

logdir=../logs
logfile=scanner.log
command='python ../notary_util/threaded_scanner.py'
pid=`ps -Af | grep "$command" | grep -v grep | awk '{print $2}'`


if ! [ -d $logdir ]
then
	mkdir $logdir
fi

if [ -n "$pid" ];
then
	date=`date`
	echo "killing scanner from script at $date" >> $logdir/$logfile
	kill $pid
else
	echo "Scanner is not running"
fi

