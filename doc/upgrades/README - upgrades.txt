This directory contains step-by-step instructions on upgrading your Perspectives server from one version to another. If you are setting up a new server from scratch you can ignore all of this.



Upgrading a notary generally consists of two steps:
1) sync the new code
2) upgrade the database

Syncing the code is usually simple (just 'git pull'), while upgrading the database may take several steps.


Version increases that require database changes each have their own folder here. If you are upgrading across one of those versions, follow the steps in each folder in sequence.

For example, to upgrade from version 2.0 to the current version, follow these steps:
1. All steps in '2.0to3.2'
2. All steps in '3.2toCurrent'


If your version numbers are not listed here, you don't need to do anything. Simply sync code with 'git pull', and restart your server.


If you have questions or need help please contact us as described in the README! We are happy to help.
