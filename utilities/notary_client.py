import urllib
from xml.dom.minidom import parseString
import struct
import base64
from subprocess import *
import time 
import os 
import tempfile 
import sys
import traceback  
from M2Crypto import BIO, RSA, EVP


if len(sys.argv) != 4 and len(sys.argv) != 5: 
	print "usage: %s <service-id> <notary-server> <notary-port> [notary-pubkey]" % sys.argv[0]
	exit(1)  

service_id = sys.argv[1]
host = service_id.split(":")[0] 
port = service_id.split(":")[1].split(",")[0] 
service_type = service_id.split(",")[1]

notary_server = sys.argv[2]
notary_port = int(sys.argv[3]) 

notary_pub_key = None

if len(sys.argv) == 5: 
	notary_pub_key_file = sys.argv[4] 
	notary_pub_key = open(notary_pub_key_file,'r').read() 

# querying the notaries over the HTTP webservice interface
url = "http://%s:%s?host=%s&port=%s&service_type=%s" % (notary_server, notary_port, host,port,service_type)
print "\nFetching '%s'" % url

try: 
	url_file = urllib.urlopen(url)
	xml_text = url_file.read()
	code = url_file.getcode()
	if code != 200: 
		print "Notary server returned error code: %s" % code
		exit(1) 
except Exception, e:
	print "Exception contacting notary server:" 
	traceback.print_exc(e)
	exit(1) 

# if you want to see the XML format, uncomment the line below 
# keys are represented by their MD5 hash.  This is still secure, as MD5 pre-image 
# resistence is not broken 
# Each key is associated with one or more 'timespans', which represent blocks of 
# time when that notary observed only that key. 
print 50 * "-"
print "XML Response:" 
print xml_text

notary_reply = parseString(xml_text).documentElement

# most of the code below is for verifying the signature on the data returned by the notary
# we need to parse the XML and convert it to the binary format that is required for 
# verifying the signature.  

packed_data = ""

keys = notary_reply.getElementsByTagName("key")
for k in keys:
        timespans = k.getElementsByTagName("timestamp")
        num_timespans = len(timespans)
        head = struct.pack("BBBBB", (num_timespans >> 8) & 255, num_timespans & 255, 0, 16,3)
        fingerprint = k.getAttribute("fp")
        fp_bytes = ""
	for hex_byte in fingerprint.split(":"):
                fp_bytes += struct.pack("B", int(hex_byte,16))
	ts_bytes = ""
        for ts in timespans:
                ts_start = int(ts.getAttribute("start"))
                ts_end  = int(ts.getAttribute("end"))
                ts_bytes += struct.pack("BBBB", ts_start >> 24 & 255,
                                                   ts_start >> 16 & 255,
                                                   ts_start >> 8 & 255,
                                                   ts_start & 255)
                ts_bytes += struct.pack("BBBB", ts_end >> 24 & 255,
                                                   ts_end >> 16 & 255,
                                                   ts_end >> 8 & 255,
                                                   ts_end & 255)
	packed_data =(head + fp_bytes + ts_bytes) + packed_data   


packed_data = service_id +  struct.pack("B",0) + packed_data

print 50 * "-"
print "Results:" 

if notary_pub_key:
	sig_raw = base64.standard_b64decode(notary_reply.getAttribute("sig")) 
	bio = BIO.MemoryBuffer(notary_pub_key)
	rsa_pub = RSA.load_pub_key_bio(bio)
	pubkey = EVP.PKey()
	pubkey.assign_rsa(rsa_pub)

	pubkey.reset_context(md='md5')
	pubkey.verify_init()
	pubkey.verify_update(packed_data)
	if not pubkey.verify_final(sig_raw):
		print "Signature verify failed.  Results are not valid"
		exit(1)  
else: 
	print "Warning: no public key specified, not verifying notary signature" 


# now just print everything out
# a real perspectives client would check the consistency of results returned from 
# multiple notaries and test the 'duration' of that agreement over time to determine
# if the a certificate is valid  
keys = notary_reply.getElementsByTagName("key")
for k in keys:
        timespans = k.getElementsByTagName("timestamp")
        fingerprint = k.getAttribute("fp")
	print "Key = %s" % fingerprint
        for ts in timespans:
                ts_start = int(ts.getAttribute("start"))
                ts_end  = int(ts.getAttribute("end"))
		print "\tstart: %s" % time.ctime(ts_start) 
		print "\tend  : %s" % time.ctime(ts_end) 
