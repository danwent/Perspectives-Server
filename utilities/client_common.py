#   This file is part of the Perspectives Notary Server
#
#   Copyright (C) 2011 Dan Wendlandt
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, version 3 of the License.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

import struct
import base64
import urllib
from M2Crypto import BIO, RSA, EVP
from xml.dom.minidom import parseString
import time 

# querying the notaries over the HTTP webservice interface
def fetch_notary_xml(notary_server, notary_port, service_id): 
	host = service_id.split(":")[0] 
	port = service_id.split(":")[1].split(",")[0] 
	service_type = service_id.split(",")[1]
	url = "http://%s:%s?host=%s&port=%s&service_type=%s" % (notary_server, notary_port, host,port,service_type)
	url_file = urllib.urlopen(url)
	xml_text = url_file.read()
	code = url_file.getcode()
	return (code,xml_text)
	
def verify_notary_signature(service_id, notary_xml_text, notary_pub_key_text): 
 
	notary_reply = parseString(notary_xml_text).documentElement
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

	sig_raw = base64.standard_b64decode(notary_reply.getAttribute("sig")) 
	bio = BIO.MemoryBuffer(notary_pub_key_text)
	rsa_pub = RSA.load_pub_key_bio(bio)
	pubkey = EVP.PKey()
	pubkey.assign_rsa(rsa_pub)

	pubkey.reset_context(md='md5')
	pubkey.verify_init()
	pubkey.verify_update(packed_data)
	return pubkey.verify_final(sig_raw)

def notary_reply_as_text(notary_xml_text): 
	t = ""
	notary_reply = parseString(notary_xml_text).documentElement
	keys = notary_reply.getElementsByTagName("key")
	for k in keys:
        	timespans = k.getElementsByTagName("timestamp")
        	fingerprint = k.getAttribute("fp")
		t += "Key = %s\n" % fingerprint
        	for ts in timespans:
                	ts_start = int(ts.getAttribute("start"))
                	ts_end  = int(ts.getAttribute("end"))
			t += "\tstart: %s\n" % time.ctime(ts_start) 
			t += "\tend  : %s\n" % time.ctime(ts_end)
	return t

# returns list of entries containing host and key as strings
def parse_http_notary_list(file_name): 
	f = open(file_name,'r') 
	notary_list = [] 
	filtered_arr = [] 
	for line in f: 
		if not line.startswith("#"): 
			filtered_arr.append(line) 
	i = 0 
	while i < len(filtered_arr): 
		notary_server = { "host" : filtered_arr[i].strip("\n") }
		i += 1

		key = ""
		if (i >= len(filtered_arr) or filtered_arr[i].find("BEGIN PUBLIC KEY") == -1):
			raise Exception("invalid notary list file, line: '%s'" % filtered_arr[i])

		key = ""
		key += filtered_arr[i]
		i +=1
		while (i < len(filtered_arr) and filtered_arr[i].find("END PUBLIC KEY") == -1): 
			key += filtered_arr[i]
			i += 1

		key += filtered_arr[i]
		i += 1 # consume the 'END PUBLIC KEY' line
		notary_server["public_key"] = key
		notary_list.append(notary_server)
	return notary_list

