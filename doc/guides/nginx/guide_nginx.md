# nginx caching for Perspectives notaries

This is a guide to using [nginx](http://nginx.org/) as a cache and proxy to improve performance of a [Perspectives Notary server](https://github.com/danwent/Perspectives-Server). Depending on your environment, you may find that nginx caching provides better performance than using the built-in notary caching.

**Important note:** we recommend using only **one** type of caching on your notary - either the built-in caching, memcached/redis caching, *or* nginx caching, but never more than one. Using more than one layer of caching may cause clients to receive out-of-date certificate information, unless you are diligent and specific about how the layers of cache interact.

## Requirements

This guide assumes you already have a Perspectives notary running on some machine, such as [on Amazon ec2 using Ubuntu](../guide_amazon.md). This guide is written for setting up nginx on a linux machine. You may need to tweak the steps for other environments (contributions for other guides are welcome).


## Setup

Log into the remote machine normally

```
>ssh -i path/to/your/key/your-private-keypair.pem ubuntu@ec2-11-22-33-44.region.compute.amazonaws.com
```

Create the directiory where the nginx cache files should be stored. e.g.:
```
>mkdir ~/nginx ~/nginx/cache
```
(change the directories for wherever you're setting your cache to record data)



### Instal nginx

```
>sudo apt-get install nginx
```

### Configure nginx

On Ubuntu, the nginx config file is found in ```/etc/nginx/nginx.conf``` .

Back up the default config file if you wish
```
>sudo mv /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup
```

Copy the config file you want to use to the correct location
```
>sudo cp doc/guides/nginx/notary.nginx.conf /etc/nginx/nginx.conf
```

Set nginx to run whenever the machine starts
```
>update-rc.d nginx defaults
```

### Launch nginx

```
>sudo /etc/init.d/nginx restart
```

### Configure CherryPy

You'll need to modify your CherryPy server to communicate with nginx. The supplied ```nginx.conf``` configuration file uses port 8081. Feel free to use any port you like - simply modify both the nginx.conf and CherryPy's behaviour.

To change the notary's internal CherryPy port, pass the ```--webport 8081``` parameter when you launch CherryPy. You may want to edit the ```admin/start_webserver.sh``` bash script and add this to the ```server_args``` string; then CherryPy will run with the correct port every time.

## Helpful commands

1. Check nginx' status:
	```
	>/etc/init.d/nginx status
	```


## Other Notes

On Ubuntu machines, nginx logs are stored in ```/var/log/nginx/error.log```. You can examine them to see if nginx encounters any errors while running.




