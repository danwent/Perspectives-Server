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

"""
A lightweight SSL scanner that does not invoke openssl at all.
Instead it executes the initial steps of the SSL handshake directly
using a TCP socket and parses the data itself.
"""

import argparse
import binascii
import errno
import hashlib
import socket
import struct
import sys
import time
import traceback


USE_SNI = False # Use server name indication: See section 3.1 of http://www.ietf.org/rfc/rfc4366.txt
SLEEP_LEN_SEC = 0.2

class SSLScanTimeoutException(Exception): 
	pass

class SSLAlertException(Exception): 
	
	def __init__(self,value): 
		self.value = value

def read_data(s,data_len, timeout_sec): 
	buf_str = ""
	start_time = time.time()
	while(True): 
		try:
			buf_str += s.recv(data_len - len(buf_str))
			if len(buf_str) == data_len:
				break
		except socket.error, e:
			if not is_nonblocking_exception(e): 
				raise e 
		if time.time() - start_time > timeout_sec: 
			raise SSLScanTimeoutException("timeout in read_data")
		time.sleep(SLEEP_LEN_SEC)
	return buf_str

def send_data(s, data, timeout_sec): 
	start_time = time.time() 
	while(True): 
		try:
			s.send(data)
			break 
		except socket.error, e: 
			if is_nonblocking_exception(e): 
				if time.time() - start_time > timeout_sec: 
					raise SSLScanTimeoutException("timeout in send_data")
				time.sleep(SLEEP_LEN_SEC)
			else: 
				raise e

def is_nonblocking_exception(e): 
	try: 
		return e.args[0] == errno.EAGAIN or \
		       e.args[0] == errno.EINPROGRESS or \
		       e.args[0] == errno.EALREADY 
	except: 
		return False
	
def do_connect(s, host, port, timeout_sec): 
	start_time = time.time() 
	while(True): 
		try:
			s.connect((host, port))
			break 
		except socket.error, e:
			if e.args[0] == errno.EISCONN: 
				break
			if is_nonblocking_exception(e):
				if time.time() - start_time > timeout_sec: 
					raise SSLScanTimeoutException("timeout in do_connect")
				time.sleep(SLEEP_LEN_SEC) 
			else: 
				raise e

def read_record(sock,timeout_sec): 
	rec_start = read_data(sock,5,timeout_sec)
	if len(rec_start) != 5: 
		raise Exception("Error: unable to read start of record")

	(rec_type, ssl_version, tls_version, rec_length) = struct.unpack('!BBBH',rec_start)
	rest_of_rec = read_data(sock,rec_length,timeout_sec)
	if len(rest_of_rec) != rec_length: 
		raise Exception("Error: unable to read full record")
	return (rec_type, rest_of_rec)

def get_all_handshake_protocols(rec_data):
	protos = [] 
	while len(rec_data) > 0: 
		t, b1,b2,b3 = struct.unpack('!BBBB',rec_data[0:4])
		l = (b1 << 16) | (b2 << 8) | b3
		protos.append((t, rec_data[4: 4 + l]))
		rec_data = rec_data[4 + l:]
	return protos 

# rfc 2246 says the server cert is the first one
# in the chain, so ignore everything else 
def get_server_cert_from_protocol(proto_data): 
	proto_data = proto_data[3:] # get rid of 3-bytes describing length of all certs
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

def attempt_observation_for_service(service, timeout_sec):

		dns, port = service.split(",")[0].split(":")
		# if we want to try SNI, do such a scan but if that
		# scan fails with an SSL alert, retry with a non SNI request
		if USE_SNI and dns[-1:].isalpha(): 
			try: 
				return run_scan(dns,port,timeout_sec,True)
			except SSLAlertException: 
				pass

		return run_scan(dns,port,timeout_sec,False) 
		
def run_scan(dns, port, timeout_sec, sni_query): 
	try: 	
		if sni_query:
			# only do SNI query for DNS names, per RFC
			client_hello_hex = get_sni_client_hello(dns)
		else: 
			client_hello_hex = get_standard_client_hello()

		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.setblocking(0) 
		do_connect(sock, dns, int(port),timeout_sec)
		client_hello = binascii.a2b_hex(client_hello_hex)
		send_data(sock, client_hello,timeout_sec)
	
		fp = None
		start_time = time.time() 
		while not fp: 
			t,rec_data = read_record(sock,timeout_sec)
			if t == 22: # handshake message
				all_hs_protos = get_all_handshake_protocols(rec_data) 
				for p in all_hs_protos: 
					if p[0] == 11: 
						# server certificate message
						fp = get_server_cert_from_protocol(p[1])
						break
			elif t == 21: # alert message
				raise SSLAlertException(rec_data) 
	
			if not fp: 
				time.sleep(SLEEP_LEN_SEC)
				if time.time() - start_time > timeout_sec: 
					break
		try: 
			sock.shutdown(socket.SHUT_RDWR) 
		except: 
			pass
		if not fp: 
			raise SSLScanTimeoutException("timeout waiting for data")
		sock.close()
		return fp 

	# make sure we always close the socket, but still propogate the exception
	except Exception, e: 
		try: 
			sock.close()
		except: 
			pass
		raise e

def get_standard_client_hello(): 
	return "8077010301004e0000002000003900003800003500001600001300000a0700c000003300003200002f0300800000050000040100800000150000120000090600400000140000110000080000060400800000030200800000ff9c82ce1e4bc89df2c726b7cebe211ef80a611945d140834eede5674b597be487" 
	

def get_twobyte_hexstr(intval): 
	return "%0.2X" % (intval & 0xff00) + "%0.2X" % (intval & 0xff)

def get_threebyte_hexstr(intval): 
	return "%0.2X" % (intval & 0xff0000) + "%0.2X" % (intval & 0xff00) + "%0.2X" % (intval & 0xff) 

def get_hostname_extension(hostname): 
	
	hex_hostname = binascii.b2a_hex(hostname)
	hn_len = len(hostname) 
	return "0000" + get_twobyte_hexstr(hn_len + 5) +  get_twobyte_hexstr(hn_len + 3) + \
				"00" + get_twobyte_hexstr(hn_len) + hex_hostname

def get_sni_client_hello(hostname): 
	hn_extension = get_hostname_extension(hostname)
	all_extensions = hn_extension 
	the_rest = "03014d786109055e4736b93b63c371507f824c2d0f05a25b2d54b6b52a1e43c2a52c00002800390038003500160013000a00330032002f000500040015001200090014001100080006000300ff020100" + get_twobyte_hexstr(len(all_extensions)/2) + all_extensions 
	proto_len = (len(the_rest) / 2)
	rec_len = proto_len + 4
	return "160301" + get_twobyte_hexstr(rec_len) + "01" + get_threebyte_hexstr(proto_len) + the_rest 


if __name__ == "__main__":

	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('service',
			help="A service name of the form 'host:port' - e.g. github.com:443.")

	args = parser.parse_args()
	service = args.service
	try:
 
		fp = attempt_observation_for_service(service, 10)
		print "Successful scan complete: '%s' has key '%s' " % (service,fp)
	except:
		print >> sys.stderr, "Error scanning for %s" % (service)
		traceback.print_exc(file=sys.stderr)
		
