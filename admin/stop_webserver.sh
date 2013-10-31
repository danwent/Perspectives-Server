#!/bin/bash 

pid=`ps -Af | grep "python notary_http.py" | grep -v grep | awk '{print $2}'`

if [ -n "$pid" ]
then
	kill $pid 
	echo "Stopped notary_http.py"
	date=`date`
	echo "notary_http.py stopped from script at $date" >> logs/webserver.log
else
	echo "No notary_http.py was running"
fi 

