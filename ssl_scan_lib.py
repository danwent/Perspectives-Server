import socket
import struct 
import time
import binascii
import hashlib 
import traceback 
import sys
import errno 

# This is a lightweight version of SSL scanning that does not invoke openssl
# at all.  Instead, it executes the initial steps of the SSL handshake directly
# using a TCP socket and parses the data itself

# TODO: extend this to work with Server Name Indication
# (http://www.ietf.org/rfc/rfc4366.txt)


class SSLScanTimeoutException(Exception): 
	pass

def read_data(s,data_len, timeout_sec): 
	buf_str = ""
	start_time = time.time()
	while(True): 
		try:
			buf_str += s.recv(data_len - len(buf_str))
			if len(buf_str) == data_len:
				break
		except socket.error, e:
			if is_nonblocking_exception(e): 
				if time.time() - start_time > timeout_sec: 
					raise SSLScanTimeoutException("timeout in read_data")
			else: 
				raise e 
		time.sleep(1)
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
				time.sleep(1)
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
			if is_nonblocking_exception(e): 
				if time.time() - start_time > timeout_sec: 
					raise SSLScanTimeoutException("timeout in do_connect")
				time.sleep(1) 
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

# rfc 2246 says the server cert if the first one
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

def attempt_observation_for_service(service_id, timeout_sec): 

		dns, port = service_id.split(",")[0].split(":")
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.setblocking(0) 
		do_connect(sock, dns, int(port),timeout_sec)
		# this is just a hex-representation of a valid client hello message
		client_hello = binascii.a2b_hex("""8077010301004e0000002000003900003800003500001600001300000a0700c000003300003200002f0300800000050000040100800000150000120000090600400000140000110000080000060400800000030200800000ff9c82ce1e4bc89df2c726b7cebe211ef80a611945d140834eede5674b597be487""") 
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
			
			if not fp: 
				time.sleep(1)
				if time.time() - start_time > timeout_sec: 
					break

		sock.shutdown(socket.SHUT_RDWR) 
		sock.close()
		if not fp: 
			raise SSLScanTimeoutException("timeout waiting for data")
		return fp 	
