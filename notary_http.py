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

from __future__ import print_function

import argparse
import logging
import os
import re
import struct
import sys
import threading 
import traceback 
from xml.dom.minidom import getDOMImplementation

import cherrypy

from notary_util import notary_common
from notary_util import notary_logs
from notary_util.notary_db import ndb
from util import crypto, cache
from util.keymanager import keymanager
from util.ssl_scan_sock import attempt_observation_for_service, SSLScanTimeoutException, SSLAlertException

class NotaryHTTPServer(object):
	"""
	Network Notary server for the Perspectives project
	( http://perspectives-project.org/ )
	Collect and share information on website certificates from around the internet.
	"""

	# Attempt to version meaningfully, following semver.org:
	# Given a version number MAJOR.MINOR.PATCH, increment the:
	# MAJOR version when you make large architectural changes,
	# MINOR version when you add functionality in a backwards-compatible manner
	# PATCH version when you make backwards-compatible bug fixes.
	VERSION = "3.4.1"

	DEFAULT_WEB_PORT=8080
	ENV_PORT_KEY_NAME='PORT'
	STATIC_DIR = "notary_static"
	STATIC_INDEX = "index.html"
	LOG_FILE = 'webserver.log'

	CACHE_EXPIRY = 60 * 60 * 12 # seconds. see doc/advanced_notary_configuration.txt

	def __init__(self):
		parser = argparse.ArgumentParser(parents=[keymanager.get_parser(), ndb.get_parser()],
			description=self.__doc__, version=self.VERSION,
			epilog="If the database schema does not exist it will be automatically created on launch.")
		portgroup = parser.add_mutually_exclusive_group()
		portgroup.add_argument('--webport', '-p', default=self.DEFAULT_WEB_PORT, type=int,
			help="Port to use for the web server. Ignored if --envport is specified. Default: \'%(default)s\'.")
		portgroup.add_argument('--envport', '-e', action='store_true', default=False,
			help="Read which port to use from the environment variable '" + self.ENV_PORT_KEY_NAME + "'. Using this will override --webport. Default: \'%(default)s\'")
		parser.add_argument('--echo-screen', '--echoscreen', '--screenecho', '--screen-echo',\
			action='store_true', default=False,
			help='Send web server output to stdout rather than a log file.')
		parser.add_argument('--sni', action='store_true', default=False,
			help="Use Server Name Indication when scanning sites. See section 3.1 of http://www.ietf.org/rfc/rfc4366.txt.\
			 Default: \'%(default)s\'")
		parser.add_argument('--logfile', action='store_true', default=False,
			help="Log to a file on disk rather than standard out.\
			A rotating set of {0} logs will be used, each capturing up to {1} bytes.\
			File will written to {2}\
			Default: \'%(default)s\'".format(
				notary_logs.LOGGING_BACKUP_COUNT,
				notary_logs.LOGGING_MAXBYTES,
				notary_logs.get_log_file(self.LOG_FILE)))

		cachegroup = parser.add_mutually_exclusive_group()
		cachegroup.add_argument('--memcache', '--memcached', action='store_true', default=False,
			help="Use memcache to cache observation data, to increase performance and reduce load on the notary database.\
				Cached info expires after " + str(self.CACHE_EXPIRY / 3600) + " hours. " + cache.Memcache.get_help())
		cachegroup.add_argument('--memcachier', action='store_true', default=False,
			help="Use memcachier to cache observation data. " + cache.Memcachier.get_help())
		cachegroup.add_argument('--redis', action='store_true', default=False,
			help="Use redis to cache observation data. " + cache.Redis.get_help())
		cachegroup.add_argument('--pycache', default=False, const=cache.Pycache.CACHE_SIZE,
			nargs='?', metavar=cache.Pycache.get_metavar(),
			help="Use RAM to cache observation data on the local machine only.\
			If you don't use any other type of caching, use this! " + cache.Pycache.get_help())

		parser.add_argument('--cache-only', action='store_true', default=False,
			help="When retrieving data, *only* read from the cache - do not read any database records. Default: %(default)s")

		parser.add_argument('--cache-expiry', '--cache-duration',\
			default=self.CACHE_EXPIRY, type=self.cache_duration,
			metavar="CACHE_EXPIRY[Ss|Mm|Hh]",
			help="Expire cache entries after this many seconds / minutes / hours. " +\
			"Hours is the default time unit if none is provided. " +\
			"The default client settings ignore notary results that have not been updated in the past 48 hours, " +\
			"so you may want your (scan frequency + scan duration + cache expiry) to be <= 48 hours. Default: " +\
			str(self.CACHE_EXPIRY / 3600) + " hours.")

		# socket_queue_size and thread_pool use the cherrypy defaults,
		# but we hardcode them here rather than refer to the cherrypy variables directly
		# just in case the cherrypy architecture changes.
		parser.add_argument('--socket-queue-size', '--socket-queue',\
			default=5, type=self.positive_integer,
			help="The maximum number of queued connections. Must be a positive integer. Default: %(default)s.")

		parser.add_argument('--thread-pool-size', '--thread-pool', '--threads',\
			default=10, type=self.positive_integer,
			help="The number of worker threads to start up in the pool. Must be a positive integer. Default: %(default)s.")

		args = parser.parse_args()
		notary_logs.setup_logs(args.logfile, self.LOG_FILE)

		# pass ndb the args so it can use any relevant ones from its own parser
		try:
			self.ndb = ndb(args)
		except Exception as e:
			self.ndb = None
			logging.error("Database error: '%s'" % (str(e)))

		# same for keymanager
		km = keymanager(args)
		(self.notary_public_key, self.notary_priv_key) = km.get_keys()
		if (self.notary_public_key == None or self.notary_priv_key == None):
			logging.error("Could not get public and private keys.")
			exit(1)

		self.web_port = self.DEFAULT_WEB_PORT
		if (args.envport):
			if (self.ENV_PORT_KEY_NAME in os.environ):
				self.web_port = int(os.environ[self.ENV_PORT_KEY_NAME])
			else:
				raise ValueError("--envport option specified but no '%s' variable exists." % \
					(self.ENV_PORT_KEY_NAME))
		elif (args.webport):
			self.web_port = args.webport

		self.cache = None
		if (args.memcache):
			self.cache = cache.Memcache()
		elif (args.memcachier):
			self.cache = cache.Memcachier()
		elif (args.redis):
			self.cache = cache.Redis()
		elif (args.pycache):
			self.cache = cache.Pycache(args.pycache)

		notary_logs.create_log_dir()

		self.use_sni = args.sni
		self.create_static_index()
		self.args = args

		print("Using public key\n" + self.notary_public_key)


	# function to help with argument validation.
	# we name this 'positive_integer' because argparse will print messages
	# that include the function name on error, such as:
	# "error: .. invalid positive_integer value: '1.3'".
	# if the function name helps the user understand what type of argument they must supply
	# this may be less confusing.
	def positive_integer(self, value):
		"""Convert value to a positive integer, or raise an exception if we cannot."""
		ivalue = int(value)
		if ivalue < 1:
			raise argparse.ArgumentTypeError("'{0}' is not a positive integer.".format(value))
		return ivalue

	def cache_duration(self, value):
		"""Validate cache duration time, or raise an exception if we cannot."""
		# let the user specify durations in seconds, minutes, or hours
		if (re.search("[^0-9SsMmHh]+", value) != None):
			raise argparse.ArgumentTypeError("Invalid cache duration '{0}'.".format(value))

		# remove non-numeric characters
		duration = value.translate(None, 'SsMmHh')
		duration = int(duration)

		time_units = 0
		if (re.search("[Ss]", value)):
			time_units += 1
		if (re.search("[Mm]", value)):
			time_units += 1
			duration *= 60
		if (re.search("[Hh]", value)):
			time_units += 1
			duration *= 3600

		if (time_units > 1):
			raise argparse.ArgumentTypeError("Only specify one of [S|M|H] for cache duration.")
		elif (time_units == 0):
			duration *= 3600 # assume hours by default

		if (duration < 1):
			raise argparse.ArgumentTypeError("Cache duration must be at least 1 second.")

		return duration

	def _create_status_row(self, name, enabled, description):
		"""Generate the HTML to display one particular server option."""

		css_class = 'td-status-off'
		status_text = 'Off'

		if (enabled):
			css_class = 'td-status-on'
			status_text = 'On'

		return "<tr><td>{0}</td><td class='{1}'>{2}</td><td>{3}</td></tr>\n".format(\
			name, css_class, status_text, description)

	def create_static_index(self):
		"""Create a static index page."""
		# right now this is VERY simple - copy the template file and insert some variables.
		STATIC_TEMPLATE = "static_template.html"

		template = os.path.join(self.STATIC_DIR, STATIC_TEMPLATE)
		with open(template,'r') as t:
			lines = str(t.read())

		options = ""


		# performance metrics
		metrics_name = "Performance Metrics"
		metrics_text = 'This notary does not track any performance-related metrics.'

		if ((self.ndb) and (self.ndb.metricsdb or self.ndb.metricslog)):
			# TODO: add link to FAQ on website once it is up.
			metrics_text = 'This notary tracks a small number of performance-related metrics to help its owner keep things running smoothly.\
			 This does not affect your privacy in any way.\
			 For details see <a href="http://perspectives-project.org">http://perspectives-project.org</a>.'
			options += self._create_status_row(metrics_name, True, metrics_text)
		else:
			options += self._create_status_row(metrics_name, False, metrics_text)

		# SNI scanning
		# Note: this assumes that if you set --sni for server on-demand scans that it is *also*
		# set for routine scanning. We do not currently verify that though -
		# it's up to the server owner to maintain.
		sni_name = 'Server Name Indication'
		sni_text = "This notary does not use Server Name Indication when scanning websites."

		if (self.use_sni):
			sni_text = 'This notary uses <a href="https://en.wikipedia.org/wiki/Server_Name_Indication">Server Name Indication</a> when scanning websites.'
			options += self._create_status_row(sni_name, True, sni_text)
		else:
			options += self._create_status_row(sni_name, False, sni_text)


		lines = lines.replace('<!-- ::VERSION:: -->', "- version %s" % self.VERSION)
		lines = lines.replace('<!-- ::PUBLIC_KEY:: -->', self.notary_public_key)
		lines = lines.replace('<!-- ::OPTIONS:: -->', options)

		index = os.path.join(self.STATIC_DIR, self.STATIC_INDEX)
		with open (index, 'w') as i:
			print(lines, file=i)

	def get_xml(self, host, port, service_type):
		"""Fetch the xml response for a given service."""

		service = str(host + ":" + port + "," + service_type)

		if (self.cache):
			try:
				cached_service = self.cache.get(service)
				if (cached_service != None):
					self.ndb.report_metric('CacheHit', service)
					return cached_service
				else:
					self.ndb.report_metric('CacheMiss', service)
			except Exception as e:
				logging.error("Error getting service from cache: %s\n" % (e))

		#TODO: don't reference session directly
		if (not self.args.cache_only and self.ndb and (self.ndb._Session != None)):
			return self.calculate_service_xml(service, service_type)
		else:
			logging.error("Database is not available to retrieve data, and data not in the cache.\n")
			raise cherrypy.HTTPError(503) # 503 Service Unavailable

	def calculate_service_xml(self, service, service_type):
		"""
		Query the database and build a response containing any known keys for the given service.
		"""

		self.ndb.report_metric('GetObservationsForService', service)
		obs = None
		timestamps_by_key = {}
		keys = []
		num_rows = 0

		try:
			# TODO: can we grab this all in one query instead of looping?
			with self.ndb.get_session() as session:
				obs = self.ndb.get_observations(session, service)
				if (obs != None):
					for (name, key, start, end) in obs:
						num_rows += 1
						if key not in keys:
							timestamps_by_key[key] = []
							keys.append(key)
						timestamps_by_key[key].append((start, end))
		except Exception as e:
			# error already logged inside get_observations.
			# we can also see InterfaceError or AttributeError when looping through observation records
			# if the database is under heavy load.
			raise cherrypy.HTTPError(503) # 503 Service Unavailable

		if num_rows == 0: 
			# rate-limit on-demand probes
			global scan_semaphore
			global scan_sites
			global scan_sites_lock

			if (scan_semaphore.acquire(False)):
				do_scan = False
				with scan_sites_lock:
					if (service not in scan_sites):
						# only scan a given site with one thread at a time
						scan_sites[service] = True
						do_scan = True

				if (do_scan):
					t = OnDemandScanThread(service, 10 , self.use_sni, self, self.ndb)
					t.start()
					# report the metrics *after* launching so the scanning thread can get started
					self.ndb.report_metric('ScanForNewService', service)
				else:
					scan_semaphore.release()
			else: 
				self.ndb.report_metric('ProbeLimitExceeded', "CurrentProbleLimit: " + str(PROBE_LIMIT) + " Service: " + service)
			# return 404, assume client will re-query
			raise cherrypy.HTTPError(404) # 404 Not Found
	
		dom_impl = getDOMImplementation() 
		new_doc = dom_impl.createDocument(None, "notary_reply", None) 
		top_element = new_doc.documentElement
		top_element.setAttribute("version","1") 
		top_element.setAttribute("sig_type", "rsa-md5") 
	
		packed_data = ""

		# create an XML response that we'll send back to the client
		for k in keys:
			key_elem = new_doc.createElement("key")
			key_elem.setAttribute("type", notary_common.SERVICE_TYPES[service_type])
			key_elem.setAttribute("fp", k)
			top_element.appendChild(key_elem)
			num_timespans = len(timestamps_by_key[k])
			head = struct.pack("BBBBB", (num_timespans >> 8) & 255, num_timespans & 255, 0, 16,3)

			fp_bytes = ""
			for hex_byte in k.split(":"):
				fp_bytes += struct.pack("B", int(hex_byte,16))

			ts_bytes = ""
			for ts in sorted(timestamps_by_key[k], key=lambda t_pair: t_pair[0]):
				ts_start = ts[0]
				ts_end  = ts[1]
				ts_elem = new_doc.createElement("timestamp")
				ts_elem.setAttribute("end",str(ts_end))
				ts_elem.setAttribute("start", str(ts_start))
				key_elem.appendChild(ts_elem) 
				ts_bytes += struct.pack("BBBB", ts_start >> 24 & 255,
											   ts_start >> 16 & 255,
											   ts_start >> 8 & 255,
											   ts_start & 255)
				ts_bytes += struct.pack("BBBB", ts_end >> 24 & 255,
											   ts_end >> 16 & 255,
											   ts_end >> 8 & 255,
											   ts_end & 255)
			packed_data =(head + fp_bytes + ts_bytes) + packed_data   
	
		packed_data = service.encode() + struct.pack("B", 0) + packed_data
		sig = crypto.sign_content(packed_data, self.notary_priv_key)
		top_element.setAttribute("sig",sig)
		xml = top_element.toprettyxml()

		if (self.cache != None):
			self.cache.set(service, xml, expiry=self.args.cache_expiry)

		return xml

	def scan_finished(self, service):
		"""Clean up any state used for on-deman scans."""
		global scan_semaphore
		global scan_sites
		global scan_sites_lock

		with scan_sites_lock:
			if service in scan_sites:
				del scan_sites[service]
		scan_semaphore.release()

	@cherrypy.expose
	def index(self, host=None, port=None, service_type=None, **invalid_params):
		if(len(invalid_params) > 0):
			# invalid_params will catch any other parameters sent to the web server.
			# if we have any it's an invalid request.
			raise cherrypy.HTTPError(400) # 400 Bad Request

		if (host == None and port == None and service_type == None):
			# probably a visitor that doesn't know what this server is for.
			# serve a static explanation page
			path = os.path.join(cherrypy.request.app.config['/']['tools.staticfile.root'], self.STATIC_INDEX)
			return cherrypy.lib.static.serve_file(path)

		if (service_type == None):
			service_type = notary_common.SSL_TYPE

		if (port == None and (service_type in notary_common.PORTS)):
			port = str(notary_common.PORTS[service_type])

		if (host == None or host == '' or port == None or \
			service_type not in notary_common.SERVICE_TYPES):
			raise cherrypy.HTTPError(400) # 400 Bad Request
			
		cherrypy.response.headers['Content-Type'] = 'text/xml'
		return self.get_xml(host, port, service_type)


class OnDemandScanThread(threading.Thread): 

	def __init__(self, sid, timeout_sec, use_sni, server_obj, db):
		self.sid = sid
		self.timeout_sec = timeout_sec
		self.use_sni = use_sni
		self.server_obj = server_obj
		self.db = db
		threading.Thread.__init__(self)

	def __del__(self):
		"""Clean up after scanning."""
		del self.db

	def run(self): 

		try:
			fp = attempt_observation_for_service(self.sid, self.timeout_sec, self.use_sni)
			if (fp != None):
				self.db.report_observation(self.sid, fp)
			# else error already logged
			# TODO: add internal blacklisting to remove sites that don't exist or stop working.
		except (ValueError, SSLScanTimeoutException, SSLAlertException) as e:
			self.db.report_metric('OnDemandServiceScanFailure', self.sid + " " + str(e))
			logging.error("Error scanning '{0}' - {1}".format(self.sid, e))
		except Exception as e:
			self.db.report_metric('OnDemandServiceScanFailure', self.sid + " " + str(e))
			traceback.print_exc(file=sys.stdout)
		finally:
			self.server_obj.scan_finished(self.sid)


# track locks at the module level so we only use them once across all cherrypy threads
PROBE_LIMIT = 10 # simultaneous scans for new services
scan_semaphore = threading.BoundedSemaphore(PROBE_LIMIT)
scan_sites = {}
scan_sites_lock = threading.Lock()


# create an instance here so command-line args will be automatically passed and parsed
# before we start the web server
notary = NotaryHTTPServer()

# PATCH: cherrypy has problems binding to the port on hosted server spaces
# https://bitbucket.org/cherrypy/cherrypy/issue/1100/cherrypy-322-gives-engine-error-when
# TODO use this workaround until 1100 is available for release and we can upgrade
from cherrypy.process import servers
def fake_wait_for_occupied_port(host, port): return
servers.wait_for_occupied_port = fake_wait_for_occupied_port

# do not log any information about clients.
# if we don't override this function,
# access information is still logged when screen echoing is turned on.
def fake_access(): return
cherrypy.log.access = fake_access

cherrypy.config.update({ 'server.socket_port' : notary.web_port,
			 'server.socket_host' : "0.0.0.0",
			 'server.socket_queue_size': notary.args.socket_queue_size,
			 'server.thread_pool': notary.args.thread_pool_size,
			 'request.show_tracebacks' : False,  
			 # IMPORTANT PRIVACY SETTINGS!
			 # we do *not* want to record any information about clients
			 'log.access_file' : None,
			 # disable all locations of logging request headers
			 'server.log_request_headers': False,
			 'cherrypy.lib.cptools.log_request_headers': False,
			 'tools.log_headers.on': False,
			 # end of privacy settings
			 'log.error_file' : '{0}/{1}'.format(notary_logs.get_log_dir(), notary.LOG_FILE),
			 'log.screen' : False } ) 

if (notary.args.echo_screen):
	cherrypy.config.update({
			 'log.error_file' : None,
			 'log.screen' : True } )

static_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), notary.STATIC_DIR)
notary_config = { '/': {'tools.staticfile.root' : static_root,
						'tools.staticdir.root' : static_root }}

app = cherrypy.tree.mount(notary, '/', config=notary_config)
app.merge("notary.cherrypy.config")

if hasattr(cherrypy.engine, "signal_handler"):
	cherrypy.engine.signal_handler.subscribe()
if hasattr(cherrypy.engine, "console_control_handler"):
	cherrypy.engine.console_control_handler.subscribe()
cherrypy.engine.start()
cherrypy.engine.block()

