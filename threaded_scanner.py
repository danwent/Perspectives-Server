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

import os
import sys
import time 
import notary_common
import socket
import binascii
import struct
import base64 
import hashlib 
import sys
import notary_common 
import traceback 
import threading
import sqlite3

# This is a lightweight version of the ssl scanner that does not invoke openssl at all.
# Instead, it executes the initial steps of the SSL handshake directly using a TCP socket
# and parses the data itself
# 
# NOTE: this scanner is still somewhat experimental


# TODO: extend this to work with Server Name Indication (http://www.ietf.org/rfc/rfc4366.txt)

# TODO: more fine-grained error accounting to distinguish different failures
# (dns lookups, conn refused, timeouts).  Particularly interesting would be those
# that fail or hang after making some progress, as they could indicate logic bugs

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
		except socket.error:
			pass 
		if time.time() - start_time > timeout_sec: 
			raise SSLScanTimeoutException("timeout in read_data")
		time.sleep(1) 
	return buf_str

def send_data(s, data, timeout_sec): 
	start_time = time.time() 
	while(True): 
		try:
			s.send(data)
			break 
		except socket.error: 
			if time.time() - start_time > timeout_sec: 
				raise SSLScanTimeoutException("timeout in send_data")
			time.sleep(1)

def do_connect(s, host, port, timeout_sec): 
	start_time = time.time() 
	while(True): 
		try:
			s.connect((host, port))
			break 
		except socket.error: 
			if time.time() - start_time > timeout_sec: 
				raise SSLScanTimeoutException("timeout in send_data")
			time.sleep(1) 

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
	
		done = False
		start_time = time.time() 
		while not done: 
			t,rec_data = read_record(sock,timeout_sec)
			if t == 22: # handshake message
				all_hs_protos = get_all_handshake_protocols(rec_data) 
				for p in all_hs_protos: 
					if p[0] == 11: 
						# server certificate message
						fp = get_server_cert_from_protocol(p[1])
						res_list.append((service_id, fp)) 	
						done = True
						break
			
			if not done: 
				time.sleep(1)
				if time.time() - start_time > timeout_sec: 
					break 
	

class ScanThread(threading.Thread): 

	def __init__(self, sid, global_stats,timeout_sec): 
		self.sid = sid
		self.global_stats = global_stats
		self.global_stats.active_threads += 1
		threading.Thread.__init__(self)
		self.timeout_sec = timeout_sec

	def run(self): 
		try: 
			attempt_observation_for_service(self.sid, timeout_sec)
		# note: separating logical here doesn't work, as many errors
		# are swallowed by the try/except blocks added to handle the
		# async sockets.  Needs more attention
		except socket.gaierror:
			stats.failures += 1
		except SSLScanTimeoutException: 
			stats.failures += 1
		except: 
			#print "Error scanning '%s'" % self.sid 
			#traceback.print_exc(file=sys.stdout)
			stats.failures += 1

		self.global_stats.num_completed += 1
		self.global_stats.active_threads -= 1

class GlobalStats(): 

	def __init__(self): 
		self.failures = 0
		self.num_completed = 0
		self.active_threads = 0 
		self.num_started = 0 

if len(sys.argv) != 5: 
  print >> sys.stderr, "ERROR: usage: <notary-db> <service_id_file> <max simultaneous> <timeout sec> " 
  sys.exit(1)

notary_db=sys.argv[1]
if sys.argv[2] == "-": 
	f = sys.stdin
else: 
	f = open(sys.argv[2])

res_list = [] 
stats = GlobalStats()
max_sim = int(sys.argv[3])
timeout_sec = int(sys.argv[4]) 
start_time = time.time()
print >> sys.stderr, "INFO: *** Timeout = %s sec  Max-Simultaneous = %s" % \
    (timeout_sec, max_sim) 

for line in f:  
	try: 	
		sid = line.rstrip() 
		if sid.split(",")[1] == "2": 
			stats.num_started += 1
			t = ScanThread(sid,stats,timeout_sec)
			t.start() 
		if (stats.num_started % max_sim) == 0: 
			time.sleep(1)
			conn = sqlite3.connect(notary_db)
			for r in res_list: 
				notary_common.report_observation_with_conn(conn, r[0], r[1]) 
			conn.commit()
			conn.close() 
			res_list = [] 
			so_far = int(time.time() - start_time)
			print "%s second passed.  %s complete, %s failures.  %s Active threads" % \
				(so_far, stats.num_completed, 
					stats.failures, stats.active_threads)
	except KeyboardInterrupt: 
		exit(1)	

if stats.active_threads > 0: 
	time.sleep(timeout_sec)

duration = int(time.time() - start_time)
print "Scan of %s services took %s seconds.  %s Failures" % (stats.num_started,duration, stats.failures)
exit(0) 

