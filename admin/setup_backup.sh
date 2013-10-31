
if [ $# != 2 ] 
then 
	echo "usage: <git-remote-server> <repo-name>" 
	exit 1
fi 

# setup backup 
if ! [ -f ~/.ssh/id_rsa ]
then 
	echo "Generating new SSH key"
	ssh-keygen -t rsa
	echo "SSH public key:" 
	cat ~/.ssh/id_rsa.pub
fi 
 

if ! [ -d notary_backup ]  
then 
	mkdir notary_backup
	cd notary_backup 
	git init
	git remote add origin $1:$2.git
	git config user.name "$2"
	git config user.email "<none>"
	git pull origin master # in case this is a rebuild
fi 


