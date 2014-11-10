# Perspectives Notary API

Currently the notary software exposes one function as an API: querying for certificate information about a host.

## 1. Retrieve host information

To retrieve fingerprint or certificate information about any host, visit the notary's index page and add parameters to the URL:

* ```?host=github.com```
or
* ```?host=github.com&service_type=2&port=443```

### Arguments

The arguments are:
  * ```host:``` the domain name or IP address you want information about
  * ```service_type:``` the communication protocol you want information about.
    * type 1 is for SSH communication
    * type 2 is for SSL/TLS communication
  * ```port:``` the network port you want information about on that particular host

#### Service types

Currently the only supported ```service_type``` is ```2```, which will return SSL/TLS results.

Legacy code exists to handle ```service_type 1, SSH```, but it is not currently supported nor tested.

#### When arguments are optional:

* Notaries version 3.1 and earlier require both ```service_type``` and ```port``` to be specified.
* Notaries version 3.2 and later will default to ```service_type 2 (SSL/TLS)``` if none is specified. They will default to ```port 443``` if ```service_type``` is ```2``` and no port is specified.

See below for how to determine a notary's version information.

### Return values

The possible return values are:

1. **If a request is valid and the notary has information on that host/port/service:** the notary will return an XML document containing the certificate information it has observed.

  The document will contain:
  * A list the certificate fingerprints - or "keys" - it has seen for the given host/port/service.
  * The start and stop times for each key, given in [unix epoch time](https://en.wikipedia.org/wiki/Unix_time).
  * A signature clients can use to validate that the notary did indeed generate and sign the XML document.

  Example XML:

  	```xml
    <notary_reply sig="ATuXR6APVGup88lOIqFd38OUbBblZzVtdU2aP79AUFm0VkpMQQY5i
    22gfqdCEQMtOXrrtslWxnlsAEwV8Yjwg57E25iB1NHUr8lbEAOX5TlEFzDXejqatmBeMiloi
    7kXHesZXz0iAWqpHgLSlOqUwz6DnzKMrgWkARcNdW2nJPiSGNbX7S/uAwaKmVexaITrwWVaU
    VCsHsVgM88MgnMzfn67ofsoNUHpozbY3w==" sig_type="rsa-md5" version="1">
      <key fp="55:d8:b2:ac:fa:96:df:af:85:32:1c:0f:b2:5a:96:1d" type="ssl">
      	<timestamp end="1382022034" start="1376665224"/>
      </key>
      <key fp="c6:a0:cb:fb:53:01:82:6c:ac:d1:61:33:02:b1:64:db" type="ssl">
      	<timestamp end="1376665223" start="1371308421"/>
      	<timestamp end="1396278043" start="1382022035"/>
      </key>
      <key fp="db:66:9f:0b:1a:34:64:25:52:f6:2a:06:82:41:22:be" type="ssl">
      	<timestamp end="1396969218" start="1396278044"/>
      </key>
      <key fp="df:ef:60:0c:26:e8:cf:c7:00:3a:f4:b7:30:58:0d:07" type="ssl">
      	<timestamp end="1371308420" start="1346457600"/>
      </key>
      <key fp="fa:67:e3:c3:67:79:0d:8b:94:52:ab:21:01:32:63:34" type="ssl">
      	<timestamp end="1401721525" start="1396969219"/>
      	<timestamp end="1409670040" start="1401980739"/>
      	<timestamp end="1415545230" start="1409842951"/>
      </key>
    </notary_reply>
    ```


2. **If a request is valid but the notary has no information on that host/port/service:** the notary will return ```HTTP 404 Not Found``` and immediately run its own scan of the service. Any scan results will be added to the notary's database. Clients can then requery to view the results.

3. **If a result is invalid:** the notary will return ```HTTP 400 Bad Request```.

## Invalid requests

Any request not matching an API function will return ```HTTP 400 Bad Request```.

## Notaries under heavy load

Notaries version 3.1 or higher will return ```HTTP 503 Service Unavailable``` if any of the following situations occurs:
* The notary is unable to retrieve data for a given host/port/service, because the database is under heavy load
* The database is not available to retrieve any data, and the requested data is not in the cache (or no caching is enabled)

Clients are advised to wait a moderate amount of time (e.g. a few minutes) and requery.

## Finding a notary's version number:

To find a notary's version number visit the notary's main index page (e.g. https://heimdal.herokuapp.com/ ). Notaries of version 3 or higher should display an index page that displays their version number.

If the notary returns ```HTTP 400 Bad Request``` instead of an index page, it is likely a version 2 notary.
