# Perspectives Server

**Scan, store, and serve information on website certificates.**

*Perspectives* is a browser extension that helps to verify whether your connection to any web site really is secure. It does this by checking the connection [certificate](https://en.wikipedia.org/wiki/Public_key_certificate) with multiple observers hosted around the world. For more information see: [http://www.perspectives-project.org](http://www.perspectives-project.org).

This project contains the scanner and server components of Perspectives. When run this code will scan websites, store their certificate information, and serve the information to any client that requests it.

Machines running this software are sometimes called "Perspectives Servers" or "Network Notaries"; they sign or vouch for the certificate history they have seen for each website.


## Contact
You can contact the developers or post questions for discussion on the Perspectives Dev newsgroup:

* [https://groups.google.com/group/perspectives-dev](https://groups.google.com/group/perspectives-dev)
* [perspectives-dev@googlegroups.com](mailto:perspectives-dev@googlegroups.com)

You can file bugs and send pull requests through GitHub:
* https://github.com/danwent/Perspectives-Server

## Contribute

Please visit the github page to submit changes and suggest improvements:

* https://github.com/danwent/Perspectives-Server

## Details

When run this software does three things:

1. Stores a history of websites (sometimes called "services") and certificate keys it has seen
2. Sends certificate key information for a particular site to any client that requests it (usually done via the [Perspectives browser extension](https://github.com/danwent/Perspectives))
3. Routinely scans the sites it knows about, to keep its information up to date

Installing this software and launching the server will take care of tasks 1 and 2.
To run a notary it is important to set a scheduled task (whether via crontab or some other method) to cover step 3, allowing the server to generate a history of keys for each service over time.

### API

See the [network notary API document](doc/api.md) for details.

### Technical Details

The Perspectives server implements "on-demand probing": if you query for a service that is not in the database the notary will automatically kick-off a probe for that service.
The notary will respond to the requestor with an HTTP 404, and the client should
requery to get the results. The Perspectives browser extension already does this.

The notary software currently signs data as requests are sent to clients. You can use caching on production servers to reduce this performance impact.

The only service-type that is currently fully supported is SSL/TLS (service-type 2). Code exists to handle SSH services (service-type 1), but it is not maintained nor tested.


## How to run a Perspectives server

The [guides folder](doc/guides) contains instructions for running a Perspectives server under particular environments such as Amazon EC2. Below is a general introduction.

### Prerequisites

You must install the following:

* openssl, to generate public/private RSA keys
* python 2.7 or later
* python libraries:
	* M2Crypto
	* cherrypy3
	* sqlalchemy
	* a python driver for your type of database
	(e.g. sqlite3 for sqlite, psycopg2 for postgresql, etc.)


On debian and ubuntu you can install these using:

```% apt-get install python-sqlite python-m2crypto python-cherrypy3 python-sqlalchemy```

### Setup

Creating a server is as easy as running:

```% python notary_http.py```

The server will create a new public/private key pair and a new database, if necessary, with the default options.

Run the server with ```-h``` or ```--help``` to see a list of options. For example you can specify a different type of database with ```--dbtype postgresql```.

 
### Running

Once your server is running, try asking it about a service:

```% python client/simple_client.py github.com:443,2```

You can also fetch results with a webbrowser, though you may need to 'view source'
to see the XML. Visit [http://localhost:8080/?host=github.com](http://localhost:8080/?host=github.com)


The first time you query for a particular service, it's normal to get a 404 error
(see the Technical Details section for an explanation).
Just wait a few seconds and try again.

After waiting a few seconds, test that the service has been added to the database:

```% python notary_util/list_services.py```


### Scheduled scans

Usually you do not run scans manually but rather set a scheduled task to
periodically scan all services in the database, using something like:

```% python notary_util/list_services.py | python notary_util/threaded_scanner.py```

If you are using a more complex database setup and don't want to type out the
arguments every time, you can share the database config by launching the server
with ```--write-config-file``` and then running utils with:

```% python notary_util/list_services.py --read-config-file | python notary_util/threaded_scanner.py --read-config-file```

Or, if your database info is stored as an environment variable you can use

```% python notary_util/list_services.py --dburl | python notary_util/threaded_scanner.py --dburl```


Scanning can take a long time, depending on the size of your database and the rate you
specify to threaded_scanner.py .

Here is an example crontab file to run scans twice a day (1 am and 1 pm) on all services in the database
that have been seen in the past 5 days, with a rate of 20 simultaneous probes and a timeout of 20 seconds
per probe.  It also contains an entry to restart the server if the machine reboots:

	0 1,13 * * * cd /root/Perspectives-Server && python notary_util/list_services.py | python notary_util/threaded_scanner.py
	@reboot cd /root/Perspectives-Server && python notary_http.py


## More Info

This depo contains the following directories:

	/admin			Shell scripts to help administer a running notary on unix machines.
					May or may not be needed depending on your setup.
	/client			Python modules for connecting to and querying notaries.
					Only needed for testing your notary setup.
	/doc			All documentation
	/doc/upgrades	Step-by-step instructions for upgrading a notary from
					each version to the next. Not needed if you are running
					a notary for the first time.
	/doc/guides		Guides on how to run a notary under various environments (e.g. Amazon)
	/notary_static	Location of static files served by the notary during use
	/notary_util	Python modules that depend on the notary database
	/tests			Location of test scripts, both python modules and manual tests
	/util			Python modules that do not depend on the notary database


See ```doc/advanced_notary_configuration.txt``` for tips on improving notary performance.
