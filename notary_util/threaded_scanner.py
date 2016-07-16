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

from __future__ import print_function

import argparse
import errno
import logging
import os
import sys
import threading
import time

import notary_common
import notary_logs
from notary_db import ndb

# TODO: HACK
# add ..\util to the import path so we can import ssl_scan_sock
sys.path.insert(0,
	os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from util.ssl_scan_sock import attempt_observation_for_service, SSLScanTimeoutException, SSLAlertException

DEFAULT_SCANS = 10
DEFAULT_WAIT = 20
DEFAULT_INFILE = "-"
LOGFILE = "scanner.log"

stats = None
results = None

class ResultStore(object):
	"""
	Store and retrieve observation results in a thread-safe way.
	"""
	def __init__(self):
		self.results = []
		self.lock = threading.Lock()

	def add(self, result):
		"""
		Add a result to the set.
		"""
		with self.lock:
			self.results.append(result)

	def get(self):
		"""
		Return the list of existing results
		and empty the set.
		"""
		# use a lock so we don't lose any results
		# between retrieving the current set
		# and adding new ones
		with self.lock:
			# copy existing results so we can clear the list
			results_so_far = list(self.results)
			self.results = []
			return results_so_far

class ScanThread(threading.Thread): 
	"""
	Scan a remote service and retrieve the fingerprint for its TLS certificate.
	"""
	def __init__(self, db, sid, global_stats, timeout_sec, sni):
		self.db = db
		self.sid = sid
		self.global_stats = global_stats
		self.global_stats.active_threads += 1
		threading.Thread.__init__(self)
		self.timeout_sec = timeout_sec
		self.sni = sni
		self.global_stats.threads[sid] = time.time() 

	def _get_errno(self, e):
		"""
		Return the error number attached to an Exception,
		or 0 if none exists.
		"""
		try: 
			return e.args[0]
		except Exception:
			return 0 # no error

	def _record_failure(self, e):
		"""Record an exception that happened during a scan."""
		stats.failures += 1
		self.db.report_metric('ServiceScanFailure', str(e))
		if (isinstance(e, SSLScanTimeoutException)):
			stats.failure_timeouts += 1
			return
		if (isinstance(e, SSLAlertException)):
			stats.failure_ssl_alert += 1
			return
		if (isinstance(e, ValueError)):
			stats.failure_other += 1
			return

		err = self._get_errno(e)
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

	def run(self):
		"""
		Scan a remote service and retrieve the fingerprint for its TLS certificate.
		The fingerprint is appended to the global results list.
		"""
		try:
			fp = attempt_observation_for_service(self.sid, self.timeout_sec, self.sni)
			if (fp != None):
				results.add((self.sid, fp))
			else:
				# error already logged, but tally error count
				stats.failures += 1
				stats.failure_socket += 1
		except Exception, e:
			self._record_failure(e)
			logging.error("Error scanning '{0}' - {1}".format(self.sid, e))
			logging.exception(e)

		self.global_stats.num_completed += 1
		self.global_stats.active_threads -= 1
		
		if self.sid in self.global_stats.threads:
			del self.global_stats.threads[self.sid]

class GlobalStats(object):
	"""
	Count various statistics and causes of scan failures
	for later analysis.
	"""
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
		self.failure_socket = 0
		self.failure_other = 0 
	

def _record_observations_in_db(db, results):
	"""
	Record a set of service observations in the database.
	"""
	if len(results) == 0:
		return
	try:
		for r in results:
			db.report_observation(r[0], r[1])
	except Exception as e:
		# TODO: we should probably retry here 
		logging.critical("DB Error: Failed to write results of length {0}".format(
					len(results)))
		logging.exception(e)


def get_parser():
	"""Return an argument parser for this module."""
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
	parser.add_argument('--logfile', action='store_true', default=False,
				help="Log to a file on disk rather than standard out.\
				A rotating set of {0} logs will be used, each capturing up to {1} bytes.\
				File will written to {2}\
				Default: \'%(default)s\'".format(
					notary_logs.LOGGING_BACKUP_COUNT + 1,
					notary_logs.LOGGING_MAXBYTES,
					notary_logs.get_log_file(LOGFILE)))
	loggroup = parser.add_mutually_exclusive_group()
	loggroup.add_argument('--verbose', '-v', default=False, action='store_true',
				help="Verbose mode. Print more info about each scan.")
	loggroup.add_argument('--quiet', '-q', default=False, action='store_true',
				help="Quiet mode. Only print system-critical problems.")
	return parser


def main(db, service_id_file, logfile=False, verbose=False, quiet=False, rate=DEFAULT_SCANS,
		timeout_sec=DEFAULT_WAIT, sni=False):
	"""
	Run the main program.
	Scan a list of services and update Observation records in the notary database.
	"""

	global stats
	global results

	stats = GlobalStats()
	results = ResultStore()

	notary_logs.setup_logs(logfile, LOGFILE, verbose=verbose, quiet=quiet)

	start_time = time.time()
	localtime = time.asctime(time.localtime(start_time))

	# read all service names to start;
	# otherwise the database can lock up
	# if we're accepting data piped from another process
	all_sids = [line.rstrip() for line in service_id_file]

	print("Starting scan of %s service-ids at: %s" % (len(all_sids), localtime))
	print("INFO: *** Timeout = %s sec  Scans-per-second = %s" % \
	    (timeout_sec, rate))
	db.report_metric('ServiceScanStart', "ServiceCount: " + str(len(all_sids)))

	# create a thread to scan each service
	# and record results as they come in
	for sid in all_sids:
		try:
			# ignore non SSL services
			# TODO: use a regex instead
			if sid.split(",")[1] == notary_common.SSL_TYPE:
				stats.num_started += 1
				t = ScanThread(db, sid, stats, timeout_sec, sni)
				t.start()

			if (stats.num_started % rate) == 0:
				time.sleep(1)
				_record_observations_in_db(db, results.get())

				so_far = int(time.time() - start_time)
				logging.info("%s seconds passed.  %s complete, %s " \
					"failures.  %s Active threads" % \
					(so_far, stats.num_completed,
					stats.failures, stats.active_threads))
				logging.info("  details: timeouts = %s, " \
					"ssl-alerts = %s, no-route = %s, " \
					"conn-refused = %s, conn-reset = %s,"\
					"dns = %s, socket = %s, other = %s" % \
					(stats.failure_timeouts,
					stats.failure_ssl_alert,
					stats.failure_no_route,
					stats.failure_conn_refused,
					stats.failure_conn_reset,
					stats.failure_dns,
					stats.failure_socket,
					stats.failure_other))

			if stats.num_started  % 1000 == 0:
				if (verbose):
					logging.info("long running threads")
					cur_time = time.time()
					for sid in stats.threads.keys():
						spawn_time = stats.threads.get(sid, cur_time)
						duration = cur_time - spawn_time
						if duration > 20:
							logging.info("'%s' has been running for %s" %\
							 (sid, duration))

		except IndexError:
			logging.error("Service '%s' has no index [1] after splitting on ','.\n" % (sid))
		except KeyboardInterrupt:
			exit(1)

	# finishing the for-loop means we kicked-off all threads,
	# but they may not be done yet.  Wait for a bit, if needed.
	giveup_time = time.time() + (2 * timeout_sec)
	while stats.active_threads > 0:
		time.sleep(1)
		if time.time() > giveup_time:
			if stats.active_threads > 0:
				logging.error("Giving up scans after {0}. {1} threads still active!".format(
					giveup_time, stats.active_threads))
			break

	# record any observations made since we finished the
	# main for-loop
	_record_observations_in_db(db, results.get())

	duration = int(time.time() - start_time)
	localtime = time.asctime(time.localtime(start_time))
	print("Ending scan at: %s" % localtime)
	print("Scan of %s services took %s seconds.  %s Failures" % \
		(stats.num_started, duration, stats.failures))
	db.report_metric('ServiceScanStop')
	exit(0)

if __name__ == "__main__":
	args = get_parser().parse_args()
	# pass ndb the args so it can use any relevant ones from its own parser
	db = ndb(args)
	main(db, args.service_id_file, args.logfile, args.verbose, args.quiet, args.scans,
		args.timeout, args.sni)
