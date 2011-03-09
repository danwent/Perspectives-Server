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

import sys
import time 
import socket
import struct
import sys
import notary_common 
import traceback 
import threading
import sqlite3
import errno
from ssl_scan_sock import attempt_observation_for_service, SSLScanTimeoutException

# TODO: more fine-grained error accounting to distinguish different failures
# (dns lookups, conn refused, timeouts).  Particularly interesting would be
# those that fail or hang after making some progress, as they could indicate
# logic bugs


class ScanThread(threading.Thread): 

	def __init__(self, sid, global_stats,timeout_sec): 
		self.sid = sid
		self.global_stats = global_stats
		self.global_stats.active_threads += 1
		threading.Thread.__init__(self)
		self.timeout_sec = timeout_sec
		self.global_stats.threads[sid] = time.time() 

	def get_errno(self, e): 
		try: 
			return e.args[0]
		except: 
			return 0 # no error

	def record_failure(self, e,): 
		stats.failures += 1
		if type(e) == type(SSLScanTimeoutException()): 
			stats.failure_timeouts += 1
			return

		err = self.get_errno(e) 
		if err == errno.ECONNREFUSED:
			stats.failure_conn_refused += 1
		elif err == errno.EHOSTUNREACH or err == errno.ENETUNREACH: 
			stats.failure_no_route += 1
		elif err == errno.ECONNRESET: 
			stats.failure_conn_reset += 1
		elif err == -2 or err == -3: 
			stats.failure_dns += 1
		else: 	
			stats.failure_other += 1 
			print "Unknown error scanning '%s'" % self.sid 
			traceback.print_exc(file=sys.stdout)

	def run(self): 
		try: 
			fp = attempt_observation_for_service(self.sid, self.timeout_sec)
			res_list.append((self.sid,fp))
		except Exception, e:
			self.record_failure(e) 

		self.global_stats.num_completed += 1
		self.global_stats.active_threads -= 1
		
		del self.global_stats.threads[self.sid]

class GlobalStats(): 

	def __init__(self): 
		self.failures = 0
		self.num_completed = 0
		self.active_threads = 0 
		self.num_started = 0 
		self.threads = {} 

		# individual failure counts
		self.failure_timeouts = 0
		self.failure_no_route = 0
		self.failure_conn_refused = 0
		self.failure_conn_reset = 0
		self.failure_dns = 0 
		self.failure_other = 0 
	
if len(sys.argv) != 5: 
  print >> sys.stderr, "ERROR: usage: <notary-db> <service_id_file> <scans-per-sec> <timeout sec> " 
  sys.exit(1)

notary_db=sys.argv[1]
if sys.argv[2] == "-": 
	f = sys.stdin
else: 
	f = open(sys.argv[2])

res_list = [] 
stats = GlobalStats()
rate = int(sys.argv[3])
timeout_sec = int(sys.argv[4]) 
start_time = time.time()
localtime = time.asctime( time.localtime(start_time) )
print "Starting scan at: %s" % localtime
print "INFO: *** Timeout = %s sec  Scans-per-second = %s" % \
    (timeout_sec, rate) 

# read all sids to start, otherwise sqlite locks up 
# if you start scanning before list_services_ids.py is not done
all_sids = [ line.rstrip() for line in f ]

for sid in all_sids:  
	try: 	
		if sid.split(",")[1] == "2": 
			stats.num_started += 1
			t = ScanThread(sid,stats,timeout_sec)
			t.start()
 
		if (stats.num_started % rate) == 0: 
			time.sleep(1)
			conn = sqlite3.connect(notary_db)
			for r in res_list: 
				notary_common.report_observation_with_conn(conn, r[0], r[1]) 
			conn.commit()
			conn.close() 
			res_list = [] 
			so_far = int(time.time() - start_time)
			print "%s seconds passed.  %s complete, %s failures.  %s Active threads" % \
				(so_far, stats.num_completed, 
					stats.failures, stats.active_threads)
			print "failure details: timeouts = %s, no-route = %s, conn-refused = %s, conn-reset = %s, dns = %s, other = %s" % \
				(stats.failure_timeouts,
				stats.failure_no_route,
				stats.failure_conn_refused,
				stats.failure_conn_reset,
				stats.failure_dns, 
				stats.failure_other)
			sys.stdout.flush()

		if stats.num_started  % 1000 == 0: 
			print "long running threads" 
			cur_time = time.time() 
			for sid in stats.threads.keys(): 
				duration = cur_time - stats.threads.get(sid,cur_time)
				if duration > 20: 
					print "'%s' has been running for %s" % (sid,duration) 
			sys.stdout.flush()

	except KeyboardInterrupt: 
		exit(1)	

if stats.active_threads > 0: 
	time.sleep(2 * timeout_sec)

duration = int(time.time() - start_time)
localtime = time.asctime( time.localtime(start_time) )
print "Ending scan at: %s" % localtime
print "Scan of %s services took %s seconds.  %s Failures" % (stats.num_started,duration, stats.failures)
exit(0) 

