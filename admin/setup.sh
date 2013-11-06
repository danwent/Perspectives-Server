#!/bin/bash

# perform intial setup for a notary server

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$dir"/_common_functions.sh

# create log directory
do_setup

# the database and key pair are automatically created by the notary if necessary

# setup cronjobs
add_cron_job()
{
	time_string=$1
	command_string=$2

	(crontab -l ; echo "$time_string $command_string" ) | crontab -
}

replace_cron_job()
{
	time_string=$1
	command_string=$2

	# keep all lines that don't match this command,
	# so the command is updated/replaced if called multiple times
	# (i.e. we won't add duplicates)
	( crontab -l | grep -v "$command_string" ) | crontab -
	add_cron_job "$time_string" "$command_string"
}

replace_cron_job "5 1,13 * * *" "$dir/start_scan.sh"
replace_cron_job "@reboot" "$dir/start_webserver.sh"
add_cron_job "*/5 * * * *" "$dir/start_webserver.sh"
