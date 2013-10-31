#!/bin/bash 

backupdir=../backup
dumpfile=notary_dump.txt

if ! [ -d $backupdir ]
then
	mkdir $backupdir
fi

python ../notary_util/db2file.py .$backupdir/$dumpfile
cd $backupdir
rm $dumpfile.bz2
bzip2 $dumpfile

