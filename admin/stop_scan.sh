#!/bin/bash 

pid=`ps -Af | grep "python threaded_scanner.py" | grep -v grep | awk '{print $2}'`
if [ -n "$pid" ]; 
then
	date=`date`
	echo "killing scanner from script at $date" >> logs/scanner.log
	kill $pid
else
	echo "Scanner is not running"
fi

