import urllib
from xml.dom.minidom import parseString
import struct
import base64
from subprocess import *
import time 
import os 
import tempfile 
import sys 

if len(sys.argv) != 5: 
	print "usage: %s <service-hostname> <service-port> <notary-server> <notary-port>" % sys.argv[0]
	exit(1)  

host = sys.argv[1]
port = int(sys.argv[2]) 
notary_server = sys.argv[3]
notary_port = int(sys.argv[4]) 

# this is the perspectives notary server we will contact and its public key 
# a real perspectives client would query multiple notaries
notary_pub_key="""-----BEGIN PUBLIC KEY-----
MIHKMA0GCSqGSIb3DQEBAQUAA4G4ADCBtAKBrAGXsegzE6E/6j4vgzi3NqGSn2dz
W6gRxkuAL7PB8QmRqtG9ieSQjFB6cTYvkmp7x/LtHqlr9Fa6+/mT4Ma5oKU0RpgY
MyfYnEk0iiNWG2fj4mRpTscHfcEJfKP13OGAYP1ZuHksTXSYsaKfIwiVKMLgQ/hA
FHBSCs9X+bvVMgPOiEpxZXfaynOQ3TLGYtVywLRwW5yvlRq4E9z0rtvwR1bn1hVd
JaJ2Lw7kRVMCAwEAAQ==
-----END PUBLIC KEY-----"""

# querying the notaries over the HTTP webservice interface
url = "http://%s:%s?host=%s&port=%s&service_type=2" % (notary_server, notary_port, host,port)
print "fetching '%s'" % url
xml_text = urllib.urlopen(url).read()

# if you want to see the XML format, uncomment the line below 
# keys are represented by their MD5 hash.  This is still secure, as MD5 pre-image 
# resistence is not broken 
# Each key is associated with one or more 'timespans', which represent blocks of 
# time when that notary observed only that key. 
print xml_text

notary_reply = parseString(xml_text).documentElement

# most of the code below is for verifying the signature on the data returned by the notary
# we need to parse the XML and convert it to the binary format that is required for 
# verifying the signature.  We use the openssl command line utility to verify the signature. 
(sig_fd, sig_file_name) = tempfile.mkstemp() 
sig_raw = base64.standard_b64decode(notary_reply.getAttribute("sig"))
os.write(sig_fd, sig_raw)
os.close(sig_fd)

service_id = host + ":" + str(port) + ",2" 
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

(data_fd, data_file_name) = tempfile.mkstemp() 
os.write(data_fd,packed_data)
os.close(data_fd)

(pubkey_fd, pubkey_file_name) = tempfile.mkstemp() 
os.write(pubkey_fd, notary_pub_key)
os.close(pubkey_fd)

# run openssl, specifying the temp files we've written above. 
cmd_arr = [ "openssl", "dgst", "-verify", 
	    pubkey_file_name, "-signature", 
	    sig_file_name, data_file_name ]

proc = Popen( cmd_arr , stdout=PIPE, stderr=PIPE)
retcode = proc.wait()
output = proc.communicate()[0]

# remove temp files
#os.remove(sig_file_name) 
#os.remove(data_file_name) 
#os.remove(pubkey_file_name) 

# if signature verify fails, openssl will return non-zero 
if retcode != 0: 
	print "Signature verify failed: '%s'" % output
	exit(1)  

print "Results for host = '%s' port = '%s'" % (host,port) 

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
