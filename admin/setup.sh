#!/bin/bash 

if [[ $1 == "help" || $1 == "--help" || $1 == "-h" ]] 
then 
	echo "usage: [seed-db-dump>]" 
	exit 1
fi 

if ! [ -d logs ] 
then 
	mkdir logs
fi 

# setup DB file and notary keys 
cd Perspectives-Server

if ! [ -f notary.sqlite ]
then
	python utilities/create_tables.py notary.sqlite
	if ! [ -z "$1" ]
	then 
		grep "Start Host\|End Host" ../$1 > no_keys.txt
		python utilities/file2db.py no_keys.txt notary.sqlite
	fi
fi 

if ! [ -f notary.priv ] 
then
	bash utilities/create_key_pair.sh notary.priv notary.pub
fi 

cd ..

# setup crontab
crontab psv-admin/crontab_content

