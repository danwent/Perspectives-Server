#!/bin/bash

# common definitions and functions used by notary server admin scripts

date=`date`
logdir="logs"

server_logfile=webserver.log
server_command="python notary_http.py"

scan_logfile=scanner.log
scan_command="python notary_util/threaded_scanner.py"

backupdir=backup

do_setup()
{
	script_location="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
	cd $script_location
	cd ..
	create_logdir
}

create_logdir()
{
	if ! [ -d $logdir ]
	then
		mkdir $logdir
	fi
}

get_server_pid()
{
	_get_pid "$server_command"
}

get_scan_pid()
{
	_get_pid "$scan_command"
}

_get_pid()
{
	echo `ps -Af | grep "$1" | grep -v grep | awk '{print $2}'`
}
