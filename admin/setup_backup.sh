#!/bin/bash

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source $dir/_common_functions.sh

sshdir=~/.ssh
keyfile=id_rsa

if [ $# != 2 ] 
then 
	echo "usage: <git-remote-server> <repo-name>" 
	exit 1
fi 

# setup backup 
if ! [ -f $sshdir/$keyfile ]
then 
	echo "Generating new SSH key"
	ssh-keygen -t rsa
	echo "SSH public key:" 
	cat $sshdir/$keyfile.pub
fi 
 

if ! [ -d $backupdir ]
then 
	mkdir $backupdir
	cd $backupdir
	git init
	git remote add origin $1:$2.git
	git config user.name "$2"
	git config user.email "<none>"
	git pull origin master # in case this is a rebuild
fi 


