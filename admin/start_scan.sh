#!/bin/bash 

date=`date`
rate=100
timeout=10 
logdir=../logs
logfile=scanner.log
command='python ../notary_util/threaded_scanner.py'

if ! [ -d $logdir ]
then
	mkdir $logdir
fi

if [ 1 -eq `ps -Af | grep "$command" | grep -v grep | wc -l` ]
then
	echo "ignoring request to start scan from script because scanner is already running. $date" >> $logdir/$logfile
	exit 1
fi


echo "starting scan from script at $date" >> $logdir/$logfile
python ../notary_util/list_services.py | $command --scans $rate --timeout $timeout >> ../$logdir/$logfile 2>&1 &

