#!/bin/bash 

logdir=../logs

if ! [ -d $logdir ]
then 
	mkdir $logdir
fi 

# on launch the database and key pair are automatically created if necessary

# setup crontab
crontab crontab_content

