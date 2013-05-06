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
Scan a list of services and update Observation records in the notary database.
For running scans without connecting to the database see util/simple_scanner.py.
"""

import sys
import time 
import traceback 
import threading
import argparse
import errno

import notary_common
from notary_db import ndb

# TODO: HACK
# add ..\util to the import path so we can import ssl_scan_sock
import os
sys.path.insert(0,
	os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from util.ssl_scan_sock import attempt_observation_for_service, SSLScanTimeoutException, SSLAlertException


DEFAULT_SCANS = 10
DEFAULT_WAIT = 20
DEFAULT_INFILE = "-"

# TODO: more fine-grained error accounting to distinguish different failures
# (dns lookups, conn refused, timeouts).  Particularly interesting would be
# those that fail or hang after making some progress, as they could indicate
# logic bugs

class ScanThread(threading.Thread): 

	def __init__(self, sid, global_stats,timeout_sec, sni):
		self.sid = sid
		self.global_stats = global_stats
		self.global_stats.active_threads += 1
		threading.Thread.__init__(self)
		self.timeout_sec = timeout_sec
		self.sni = sni
		self.global_stats.threads[sid] = time.time() 
		self.timeout_exc = SSLScanTimeoutException() 
		self.alert_exc = SSLAlertException("foo")

	def get_errno(self, e): 
		try: 
			return e.args[0]
		except: 
			return 0 # no error

	def record_failure(self, e,): 
		stats.failures += 1
		ndb.report_metric('ServiceScanFailure', str(e))
		if type(e) == type(self.timeout_exc): 
			stats.failure_timeouts += 1
			return
		if type(e) == type(self.alert_exc): 
			stats.failure_ssl_alert += 1
			return

		err = self.get_errno(e) 
		if err == errno.ECONNREFUSED or err == errno.EINVAL:
			stats.failure_conn_refused += 1
		elif err == errno.EHOSTUNREACH or err == errno.ENETUNREACH: 
			stats.failure_no_route += 1
		elif err == errno.ECONNRESET: 
			stats.failure_conn_reset += 1
		elif err == -2 or err == -3 or err == -5 or err == 8: 
			stats.failure_dns += 1
		else: 	
			stats.failure_other += 1 
			print "Unknown error scanning '%s'\n" % self.sid
			traceback.print_exc(file=sys.stdout)

	def run(self): 
		try: 
			fp = attempt_observation_for_service(self.sid, self.timeout_sec, self.sni)
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
		self.failure_ssl_alert = 0
		self.failure_other = 0 
	

def record_observations_in_db(res_list): 
	if len(res_list) == 0: 
		return
	try: 
		for r in res_list: 
			notary_common.report_observation_with_db( \
						ndb, r[0], r[1])
	except:
		# TODO: we should probably retry here 
		print "DB Error: Failed to write res_list of length %s" % \
					len(res_list)
		traceback.print_exc(file=sys.stdout)



parser = argparse.ArgumentParser(parents=[ndb.get_parser()],
description=__doc__)

parser.add_argument('service_id_file', type=argparse.FileType('r'), nargs='?', default=DEFAULT_INFILE,
			help="File that contains a list of service names - one per line. Will read from stdin by default.")
parser.add_argument('--scans', '--scans-per-sec', '-s', nargs='?', default=DEFAULT_SCANS, const=DEFAULT_SCANS, type=int,
			help="How many scans to run per second. Default: %(default)s.")
parser.add_argument('--timeout', '--wait', '-w', nargs='?', default=DEFAULT_WAIT, const=DEFAULT_WAIT, type=int,
			help="Maximum number of seconds each scan will wait (asychronously) for results before giving up. Default: %(default)s.")
parser.add_argument('--sni', action='store_true', default=False,
			help="use Server Name Indication. See section 3.1 of http://www.ietf.org/rfc/rfc4366.txt.\
			Default: \'%(default)s\'")
parser.add_argument('--verbose', '-v', default=False, action='store_true',
			help="Verbose mode. Print more info about each scan.")

args = parser.parse_args()

# pass ndb the args so it can use any relevant ones from its own parser
ndb = ndb(args)

res_list = [] 
stats = GlobalStats()
rate = args.scans
timeout_sec = args.timeout
f = args.service_id_file
start_time = time.time()
localtime = time.asctime( time.localtime(start_time) )

# read all service names to start;
# otherwise the database can lock up
# if we're accepting data piped from another process
all_sids = [ line.rstrip() for line in f ]

print "Starting scan of %s service-ids at: %s" % (len(all_sids), localtime)
print "INFO: *** Timeout = %s sec  Scans-per-second = %s" % \
    (timeout_sec, rate) 
ndb.report_metric('ServiceScanStart', "ServiceCount: " + str(len(all_sids)))

for sid in all_sids:  
	try: 
		# ignore non SSL services
		# TODO: use a regex instead
		if sid.split(",")[1] == notary_common.SSL_TYPE:
			stats.num_started += 1
			t = ScanThread(sid,stats,timeout_sec,args.sni)
			t.start()
 
		if (stats.num_started % rate) == 0: 
			time.sleep(1)
			record_observations_in_db(res_list) 
			res_list = [] 
			so_far = int(time.time() - start_time)
			if (args.verbose):
				print "%s seconds passed.  %s complete, %s " \
					"failures.  %s Active threads" % \
					(so_far, stats.num_completed,
						stats.failures, stats.active_threads)
				print "  details: timeouts = %s, " \
					"ssl-alerts = %s, no-route = %s, " \
					"conn-refused = %s, conn-reset = %s,"\
					"dns = %s, other = %s" % \
					(stats.failure_timeouts,
					stats.failure_ssl_alert,
					stats.failure_no_route,
					stats.failure_conn_refused,
					stats.failure_conn_reset,
					stats.failure_dns,
					stats.failure_other)
				sys.stdout.flush()

		if stats.num_started  % 1000 == 0: 
			if (args.verbose):
				print "long running threads"
				cur_time = time.time()
				for sid in stats.threads.keys():
					spawn_time = stats.threads.get(sid,cur_time)
					duration = cur_time - spawn_time
					if duration > 20:
						print "'%s' has been running for %s" %\
						 (sid,duration)
				sys.stdout.flush()

	except IndexError:
		print >> sys.stderr, "Service '%s' has no index [1] after splitting on ','.\n" % (sid)
	except KeyboardInterrupt: 
		exit(1)	

# finishing the for-loop means we kicked-off all threads, 
# but they may not be done yet.  Wait for a bit, if needed.
giveup_time = time.time() + (2 * timeout_sec) 
while stats.active_threads > 0: 
	time.sleep(1)
	if time.time() > giveup_time: 
		break

# record any observations made since we finished the
# main for-loop			
record_observations_in_db(res_list) 
ndb.close_session()

duration = int(time.time() - start_time)
localtime = time.asctime( time.localtime(start_time) )
print "Ending scan at: %s" % localtime
print "Scan of %s services took %s seconds.  %s Failures" % \
	(stats.num_started,duration, stats.failures)
ndb.report_metric('ServiceScanStop')
exit(0) 
