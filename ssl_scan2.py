#   This file is part of the Perspectives Notary Server
#
#   Copyright (C) 2011 Dan Wendlandt
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, version 2 of the License.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

import socket
import binascii
import struct
import base64 
import hashlib 
import sys
import notary_common 
import traceback 

# This is a lightweight version of the ssl scanner that does not invoke openssl at all.
# Instead, it executes the initial steps of the SSL handshake directly using a TCP socket
# and parses the data itself

# TODO: extend this to work with Server Name Indication (http://www.ietf.org/rfc/rfc4366.txt)


# generic helper to read exactly 'data_len' bytes from socket
# this call will hang until the data is read or there is an error
def read_data(s,data_len): 
	buf_str = ""
	 
	while(True): 
		buf_str += s.recv(data_len - len(buf_str))
		if len(buf_str) == data_len:
			return buf_str

def read_record(s): 
	rec_start = read_data(sock,5)
	if len(rec_start) != 5: 
		print "Error: unable to read start of record"
		exit(1) 

	(rec_type, ssl_version, tls_version, rec_length) = struct.unpack('!BBBH',rec_start)
	print "record: type = %s  length = %s" % (rec_type, rec_length)
	rest_of_rec = read_data(sock,rec_length)
	if len(rest_of_rec) != rec_length: 
		print "Error: unable to read full record"
		exit(1) 
	return (rec_type, rest_of_rec)

def get_all_handshake_protocols(rec_data):
	protos = [] 
	while len(rec_data) > 0: 
		t, b1,b2,b3 = struct.unpack('!BBBB',rec_data[0:4])
		l = (b1 << 16) | (b2 << 8) | b3
		print "handshake protocol of type %s and length %s" % (t,l) 
		protos.append((t, rec_data[4: 4 + l]))
		rec_data = rec_data[4 + l:]
	return protos 

# rfc 2246 says the server cert if the first one
# in the chain, so ignore everything else 
def get_server_cert_from_protocol(proto_data): 

	(b1,b2,b3) = struct.unpack("!BBB",proto_data[0:3])
	cert_len = (b1 << 16) | (b2 << 8) | b3
	cert = proto_data[3: 3 + cert_len]
	m = hashlib.md5() 
	m.update(cert)
	fp = ""
	digest_raw = m.digest()
	for i in range(len(digest_raw)):
		fp += binascii.b2a_hex(digest_raw[i]) + ":"
	return fp[:-1] 


if len(sys.argv) != 3 and len(sys.argv) != 2:
	print >> sys.stderr, "ERROR: usage: <service-id> [notary-db-file>]"
	exit(1)

service_id = sys.argv[1]
dns, port = service_id.split(",")[0].split(":")

try: 
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.connect((dns, int(port))) 
	# this is just a hex-representation of a valid client hello message
	client_hello = binascii.a2b_hex("""8077010301004e0000002000003900003800003500001600001300000a0700c000003300003200002f0300800000050000040100800000150000120000090600400000140000110000080000060400800000030200800000ff9c82ce1e4bc89df2c726b7cebe211ef80a611945d140834eede5674b597be487""") 
	sock.send(client_hello)
	
	done = False
	while not done: 
		t,rec_data = read_record(sock)
		if t == 22: # handshake message
			all_hs_protos = get_all_handshake_protocols(rec_data) 
			for p in all_hs_protos: 
				if p[0] == 11: 
					# server certificate message
					fp = get_server_cert_from_protocol(p[1])
					if len(sys.argv) == 3: 
						notary_common.report_observation(sys.argv[2], service_id, fp) 
					else: 
						print "INFO: no database specified, not saving observation"

					print "Successful scan complete: '%s' has key '%s' " % (service_id,fp)
					done = True
					break
	
except: 
	traceback.print_exc(file=sys.stdout)
	exit(1)
