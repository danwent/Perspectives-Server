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

from xml.dom.minidom import parseString, getDOMImplementation
import struct
import sys
import threading 
import traceback 
import argparse
import os

import cherrypy

from util import crypto, cache
from util.keymanager import keymanager
from notary_util.notary_db import ndb
from notary_util import notary_common
from util.ssl_scan_sock import attempt_observation_for_service, SSLScanTimeoutException

class NotaryHTTPServer:
	"""
	Network Notary server for the Perspectives project
	( http://perspectives-project.org/ )
	Collect and share information on website certificates from around the internet.
	"""

	VERSION = "pre3.1a"
	DEFAULT_WEB_PORT=8080
	ENV_PORT_KEY_NAME='PORT'
	STATIC_DIR = "notary_static"
	STATIC_INDEX = "index.html"
	PROBE_LIMIT = 10 # simultaneous scans for new services

	CACHE_EXPIRY = 60 * 60 * 24 # seconds. set this to however frequently you scan services.

	def __init__(self):
		parser = argparse.ArgumentParser(parents=[keymanager.get_parser(), ndb.get_parser()],
			description=self.__doc__, version=self.VERSION,
			epilog="If the database schema does not exist it will be automatically created on launch.")
		portgroup = parser.add_mutually_exclusive_group()
		portgroup.add_argument('--webport', '-p', default=self.DEFAULT_WEB_PORT,
			help="Port to use for the web server. Ignored if --envport is specified. Default: \'%(default)s\'.")
		portgroup.add_argument('--envport', '-e', action='store_true', default=False,
			help="Read which port to use from the environment variable '" + self.ENV_PORT_KEY_NAME + "'. Using this will override --webport. Default: \'%(default)s\'")
		parser.add_argument('--echo-screen', '--echoscreen', '--screenecho', action='store_true', default=False,
			help='Send web server output to stdout rather than a log file.')

		cachegroup = parser.add_mutually_exclusive_group()
		cachegroup.add_argument('--memcache', '--memcached', action='store_true', default=False,
			help="Use memcache to cache observation data, to increase performance and reduce load on the notary database.\
				Cached info expires after " + str(self.CACHE_EXPIRY / 3600) + " hours. " + cache.Memcache.get_help())
		cachegroup.add_argument('--memcachier', action='store_true', default=False,
			help="Use memcachier to cache observation data. " + cache.Memcachier.get_help())
		cachegroup.add_argument('--redis', action='store_true', default=False,
			help="Use redis to cache observation data. " + cache.Redis.get_help())

		args = parser.parse_args()

		# pass ndb the args so it can use any relevant ones from its own parser
		try:
			self.ndb = ndb(args)
		except Exception as e:
			self.ndb = None
			print >> sys.stderr, "Database error: '%s'" % (str(e))

		# same for keymanager
		km = keymanager(args)
		(self.notary_public_key, self.notary_priv_key) = km.get_keys()
		if (self.notary_public_key == None or self.notary_priv_key == None):
			print >> sys.stderr, "Could not get public and private keys."
			exit(1)
		print "Using public key\n" + self.notary_public_key

		self.create_static_index()

		self.web_port = self.DEFAULT_WEB_PORT
		if(args.envport):
			self.web_port = int(os.environ[self.ENV_PORT_KEY_NAME])

		self.cache = None
		if (args.memcache):
			self.cache = cache.Memcache()
		elif (args.memcachier):
			self.cache = cache.Memcachier()
		elif (args.redis):
			self.cache = cache.Redis()

		self.active_threads = 0 
		self.args = args

	def create_static_index(self):
		"""Create a static index page."""
		# right now this is VERY simple - copy the template file and insert some variables.
		STATIC_TEMPLATE = "static_template.html"

		template = os.path.join(self.STATIC_DIR, STATIC_TEMPLATE)
		with open(template,'r') as t:
			lines = str(t.read())

		metrics_class = 'td-status-off'
		metrics_status = 'Off'
		metrics_text = 'This server does not track any performance-related metrics.'

		if ((self.ndb) and (self.ndb.metricsdb or self.ndb.metricslog)):
			metrics_class = 'td-status-on'
			metrics_status = 'On'
			# TODO: add link to FAQ on website once it is up.
			metrics_text = 'This server tracks a small number of performance-related metrics to help its owner keep things running smoothly.\
			 This does not affect your privacy in any way.\
			 For details see <a href="http://perspectives-project.org">http://perspectives-project.org</a>.'


		lines = lines.replace('<!-- ::VERSION:: -->', "- version %s" % self.VERSION)
		lines = lines.replace('<!-- ::PUBLIC_KEY:: -->', self.notary_public_key)
		lines = lines.replace('<!-- ::OPTIONS_METRICS:: -->',
			"<tr><td>Performance Metrics</td><td class='%s'>%s</td><td>%s</td></tr>" % (metrics_class, metrics_status, metrics_text))

		index = os.path.join(self.STATIC_DIR, self.STATIC_INDEX)
		with open (index, 'w') as i:
			print >> i, lines

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
				print >> sys.stderr, "ERROR getting service from cache: %s\n" % (e)

		if (self.ndb and (self.ndb.Session != None)):
			return self.calculate_service_xml(service, host, port, service_type)
		else:
			print >> sys.stderr, "ERROR: Database is not available to retrieve data, and data not in the cache.\n"
			raise cherrypy.HTTPError(503) # 503 Service Unavailable

	def calculate_service_xml(self, service, host, port, service_type):
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
			obs = self.ndb.get_observations(service)
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
		finally:
			self.ndb.close_session()

		if num_rows == 0: 
			# rate-limit on-demand probes
			if self.active_threads < self.PROBE_LIMIT:
				self.ndb.report_metric('ScanForNewService', service)
				t = OnDemandScanThread(service, 10 , self, self.args)
				t.start()
			else: 
				self.ndb.report_metric('ProbeLimitExceeded', "CurrentProbleLimit: " + str(self.PROBE_LIMIT) + " Service: " + service)
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
			self.cache.set(service, xml, expiry=self.CACHE_EXPIRY)

		return xml

	@cherrypy.expose
	def index(self, host=None, port=None, service_type=None):
		if (host == None and port == None and service_type == None):
			# probably a visitor that doesn't know what this server is for.
			# serve a static explanation page
			path = os.path.join(cherrypy.request.app.config['/']['tools.staticfile.root'], self.STATIC_INDEX)
			return cherrypy.lib.static.serve_file(path)
		elif (host == None or port == None or service_type == None):
			raise cherrypy.HTTPError(400) # 400 Bad Request

		if (service_type not in notary_common.SERVICE_TYPES):
			raise cherrypy.HTTPError(404) # 404 Not Found
			
		cherrypy.response.headers['Content-Type'] = 'text/xml'
		return self.get_xml(host, port, service_type)


class OnDemandScanThread(threading.Thread): 

	def __init__(self, sid,timeout_sec,server_obj, args):
		self.sid = sid
		self.server_obj = server_obj
		self.timeout_sec = timeout_sec
		self.args = args
		threading.Thread.__init__(self)
		self.server_obj.active_threads += 1

	def run(self): 

		# create a new db instance, since we're on a new thread
		# pass through any args we have so we'll connect to the same database in the same way
		try:
			db = ndb(self.args)
		except Exception as e:
			print >> sys.stderr, "Database error: '%s'. Did not run on-demand scan." % (str(e))
			self.server_obj.active_threads -= 1
			return

		try:
			fp = attempt_observation_for_service(self.sid, self.timeout_sec)
			notary_common.report_observation_with_db(db, self.sid, fp)
		except Exception as e:
			db.report_metric('OnDemandServiceScanFailure', self.sid + " " + str(e))
			traceback.print_exc(file=sys.stdout)
		finally:
			self.server_obj.active_threads -= 1
			db.close_session()




# create an instance here so command-line args will be automatically passed and parsed
# before we start the web server
notary = NotaryHTTPServer()

# PATCH: cherrypy has problems binding to the port on hosted server spaces
# https://bitbucket.org/cherrypy/cherrypy/issue/1100/cherrypy-322-gives-engine-error-when
# TODO use this workaround until 1100 is available for release and we can upgrade
from cherrypy.process import servers
def fake_wait_for_occupied_port(host, port): return
servers.wait_for_occupied_port = fake_wait_for_occupied_port

cherrypy.config.update({ 'server.socket_port' : notary.web_port,
			 'server.socket_host' : "0.0.0.0",
			 'request.show_tracebacks' : False,  
			 'log.access_file' : None,  # default for production 
			 'log.error_file' : 'error.log', 
			 'log.screen' : False } ) 

if (notary.args.echo_screen):
	cherrypy.config.update({
			 'log.error_file' : None,
			 'log.screen' : True } )
else:
	cherrypy.config.update({
			 'log.error_file' : 'error.log',
			 'log.screen' : False } )

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

