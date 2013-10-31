#!/bin/bash 

pid=`ps -Af | grep "python notary_http.py" | grep -v grep | awk '{print $2}'`

if [ -n "$pid" ]
then
	echo "notary_http.py is already running" 
	exit 1
else
	echo "starting notary.http.py"
	date=`date`
	echo "notary_http.py started from script at $date" >> logs/webserver.log
	cd Perspectives-Server
	python notary_http.py notary.sqlite notary.priv >> ../logs/webserver.log 2>&1 &
fi 
