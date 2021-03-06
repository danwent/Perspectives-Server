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
import logging
import os
import socket
import struct
import sys
import time
import traceback


SLEEP_LEN_SEC = 0.2

class SSLScanTimeoutException(Exception): 
	pass

class SSLAlertException(Exception):

	ALERT_LEVELS = {
		1: 'Warning',
		2: 'Fatal'
	}

	# alert information transcribed from:
	#
	# RFC 5246 - TLS 1.2
	# https://tools.ietf.org/html/rfc5246#section-7.2
	#
	# RFC 4366 - TLS Extensions
	# http://tools.ietf.org/html/rfc4366#section-4
	ALERT_DESC = {
		0: 'Close Notify: the other party has closed the connection.',
		10: 'Unexpected Message: An inappropriate message was received.',
		20: 'Bad Record MAC',
		21: 'Decryption Failed',
		22: 'Record Overflow',
		30: 'Decompression Failure',
		40: 'Handshake Failure',
		41: 'No Certificate',
		42: 'Bad Certificate',
		43: 'Unsupported Certificate',
		44: 'Certificate Revoked',
		45: 'Certificate Expired',
		46: 'Certificate Unknown',
		47: 'Illegal Parameter',
		48: 'Unknown CA',
		49: 'Access Denied',
		50: 'Decode Error',
		51: 'Decrypt Error',
		60: 'Export Restriction',
		70: 'Protocol Version: The protocol version sent is recognized but not supported.',
		71: 'Insufficient Security: This server requires ciphers more secure than those supported.',
		80: 'Internal Error',
		90: 'User Canceled',
		100: 'No Renegotiation',
		110: 'Unsupported Extension',
		111: 'Certificate Unobtainable',
		112: 'Unrecognized Name: the supplied SNI name was not recognized.',
		113: 'Bad Certificate Status Response',
		114: 'Bad Certificate Hash Value'
	}
	
	def __init__(self, value):
		self.value = value

		# decipher the alert data from the TLS record
		if (len(value) > 0):
			level, desc = struct.unpack('!BB', value[0:2])
			if (level in self.ALERT_LEVELS and desc in self.ALERT_DESC):
				self.value = "{0} ({1}): Code {2} - {3}".format(\
					self.ALERT_LEVELS[level], level, desc, self.ALERT_DESC[desc])
			else:
				self.value = "Level {0}: Code {1}".format(level, desc)
		else:
			self.value = "Could not decipher SSLAlert record: '{0}'".format(value)

	def __str__(self):
		return self.value


def _read_data(s,data_len, timeout_sec):
	buf_str = ""
	start_time = time.time()
	while(True): 
		try:
			buf_str += s.recv(data_len - len(buf_str))
			if len(buf_str) == data_len:
				break
		except socket.error, e:
			if not _is_nonblocking_exception(e):
				raise
		if time.time() - start_time > timeout_sec: 
			raise SSLScanTimeoutException("timeout in _read_data after {0}s".format(timeout_sec))
		time.sleep(SLEEP_LEN_SEC)
	return buf_str

def _send_data(s, data, timeout_sec):
	start_time = time.time() 
	while(True): 
		try:
			s.send(data)
			break 
		except socket.error, e: 
			if _is_nonblocking_exception(e):
				if time.time() - start_time > timeout_sec: 
					raise SSLScanTimeoutException("timeout in _send_data after {0}s".format(timeout_sec))
				time.sleep(SLEEP_LEN_SEC)
			else: 
				raise

def _is_nonblocking_exception(e):
	try: 
		return e.args[0] == errno.EAGAIN or \
		       e.args[0] == errno.EINPROGRESS or \
		       e.args[0] == errno.EALREADY 
	except: 
		return False
	
def _do_connect(s, host, port, timeout_sec):
	start_time = time.time() 
	while(True): 
		try:
			s.connect((host, port))
			break 
		except socket.error, e:
			if e.args[0] == errno.EISCONN: 
				break
			if _is_nonblocking_exception(e):
				if time.time() - start_time > timeout_sec: 
					raise SSLScanTimeoutException("timeout in _do_connect after {0}s".format(timeout_sec))
				time.sleep(SLEEP_LEN_SEC) 
			else: 
				raise

def _read_record(sock,timeout_sec):
	"""
	Decipher a TLS record.
	Return the record type and (still packed) record data.
	"""
	rec_start = _read_data(sock,5,timeout_sec)
	if len(rec_start) != 5: 
		raise Exception("Error: unable to read start of record")

	(rec_type, ssl_version, tls_version, rec_length) = struct.unpack('!BBBH',rec_start)
	rest_of_rec = _read_data(sock,rec_length,timeout_sec)
	if len(rest_of_rec) != rec_length: 
		raise Exception("Error: unable to read full record")
	return (rec_type, rest_of_rec)

def _get_all_handshake_protocols(rec_data):
	"""
	Decipher a TLS handshake protocol record.
	Return a list of (message_type, data) tuples.
	"""
	protos = [] 
	while len(rec_data) > 0: 
		t, b1,b2,b3 = struct.unpack('!BBBB',rec_data[0:4])
		l = (b1 << 16) | (b2 << 8) | b3
		protos.append((t, rec_data[4: 4 + l]))
		rec_data = rec_data[4 + l:]
	return protos 

# rfc 2246 says the server cert is the first one
# in the chain, so ignore everything else 
def _get_server_cert_from_protocol(proto_data):
	"""
	Decipher a TLS Certificate message
	(i.e. the bytes from one message inside a handshake protocol record).
	"""
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
		
def _run_scan(dns, port, timeout_sec, sni_query):
	"""
	Perform an SSL handshake with the given server and port.
	If possible, retrieve the server's x509 certificate.
	"""
	try: 	
		if sni_query:
			# only do SNI query for DNS names, per RFC
			client_hello_hex = _get_sni_client_hello(dns)
		else: 
			client_hello_hex = _get_standard_client_hello()

		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		if os.name != "nt":
			sock.setblocking(0)
		_do_connect(sock, dns, int(port),timeout_sec)
		client_hello = binascii.a2b_hex(client_hello_hex)
		_send_data(sock, client_hello,timeout_sec)
	
		fp = None
		start_time = time.time() 
		while not fp: 
			t,rec_data = _read_record(sock,timeout_sec)
			if t == 22: # handshake message
				all_hs_protos = _get_all_handshake_protocols(rec_data)
				for p in all_hs_protos: 
					if p[0] == 11: 
						# server certificate message
						fp = _get_server_cert_from_protocol(p[1])
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
			raise SSLScanTimeoutException("timeout waiting for data after {0}s".format(timeout_sec))
		sock.close()
		return fp 

	except (socket.error, socket.herror, socket.gaierror, socket.timeout) as e:
		logging.warning("socket error for service {0}:{1}: {2}".format(dns, port, e))
	# propogate non-socket exceptions so we can better troubleshoot
	finally:
		try: 
			sock.close()
		except: 
			pass

def _get_standard_client_hello():
	return "8077010301004e0000002000003900003800003500001600001300000a0700c000003300003200002f0300800000050000040100800000150000120000090600400000140000110000080000060400800000030200800000ff9c82ce1e4bc89df2c726b7cebe211ef80a611945d140834eede5674b597be487" 
	

def _get_twobyte_hexstr(intval):
	return "%0.2X" % (intval & 0xff00) + "%0.2X" % (intval & 0xff)

def _get_threebyte_hexstr(intval):
	return "%0.2X" % (intval & 0xff0000) + "%0.2X" % (intval & 0xff00) + "%0.2X" % (intval & 0xff) 

def _get_hostname_extension(hostname):
	
	hex_hostname = binascii.b2a_hex(hostname)
	hn_len = len(hostname) 
	return "0000" + _get_twobyte_hexstr(hn_len + 5) +  _get_twobyte_hexstr(hn_len + 3) + \
				"00" + _get_twobyte_hexstr(hn_len) + hex_hostname

def _get_sni_client_hello(hostname):
	hn_extension = _get_hostname_extension(hostname)
	all_extensions = hn_extension 
	the_rest = "03014d786109055e4736b93b63c371507f824c2d0f05a25b2d54b6b52a1e43c2a52c00002800390038003500160013000a00330032002f000500040015001200090014001100080006000300ff020100" + _get_twobyte_hexstr(len(all_extensions)/2) + all_extensions
	proto_len = (len(the_rest) / 2)
	rec_len = proto_len + 4
	return "160301" + _get_twobyte_hexstr(rec_len) + "01" + _get_threebyte_hexstr(proto_len) + the_rest

def attempt_observation_for_service(service, timeout_sec, use_sni=False):

	try:
		dns, port = service.split(",")[0].split(":")
	except (ValueError):
		raise ValueError("Service '{0}' must be of the form 'host:port'".format(service))

	if not port.isdigit():
		raise ValueError("Port '{0}' must be a number.".format(port))

	# if we want to try SNI, do such a scan but if that
	# scan fails with an SSL alert, retry with a non SNI request
	if use_sni:
		if dns[-1:].isalpha():
			try:
				return _run_scan(dns,port,timeout_sec,True)
			except SSLAlertException as e:
				logging.error("Received SSL Alert during SNI scan of {0}:{1} - '{2}'.".format(dns, port, e) +\
					" Will re-run with non-SNI scan.")
		else:
			raise ValueError("Service '{0}' must be of the form 'host:port'".format(service))

	return _run_scan(dns,port,timeout_sec,False)

if __name__ == "__main__":

	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('service',
			help="a service name of the form 'host:port' - e.g. github.com:443.")
	parser.add_argument('--sni', action='store_true', default=False,
			help="use Server Name Indication. See section 3.1 of http://www.ietf.org/rfc/rfc4366.txt.\
			 Default: \'%(default)s\'")

	args = parser.parse_args()
	logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s')
	service = args.service
	try:
 
		fp = attempt_observation_for_service(service, 10, args.sni)
		if (fp != None):
			print "Successful scan complete: '%s' has key '%s' " % (service,fp)

	except (ValueError, SSLScanTimeoutException, SSLAlertException) as e:
		logging.error(e)
	except:
		logging.error("Error scanning for %s" % (service))
		traceback.print_exc(file=sys.stderr)
		
