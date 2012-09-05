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

from util import keygen, crypto
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

	def __init__(self):
		parser = argparse.ArgumentParser(parents=[ndb.get_parser(), keygen.get_parser()],
			description=self.__doc__, version=self.VERSION,
			epilog="If the database schema or public/private keypair do not exist they will be automatically created on launch.")
		portgroup = parser.add_mutually_exclusive_group()
		portgroup.add_argument('--webport', '-p', default=self.DEFAULT_WEB_PORT,
			help="Port to use for the web server. Ignored if --envport is specified. Default: \'%(default)s\'.")
		portgroup.add_argument('--envport', '-e', action='store_true', default=False,
			help="Read which port to use from the environment variable '" + self.ENV_PORT_KEY_NAME + "'. Using this will override --webport. Default: \'%(default)s\'")
		parser.add_argument('--echo-screen', action='store_true', default=False,
			help='Send web server output to stdout rather than a log file.')


		args = parser.parse_args()

		# pass ndb the args so it can use any relevant ones from its own parser
		self.ndb = ndb(args)


		(pub_name, priv_name) = keygen.generate_keypair(args.private_key)
		self.notary_priv_key= open(priv_name,'r').read()
		self.notary_public_key = open(pub_name,'r').read()
		print "Using public key " + pub_name + " \n" + self.notary_public_key

		self.create_static_index()

		self.web_port = self.DEFAULT_WEB_PORT
		if(args.envport):
			self.web_port = int(os.environ[self.ENV_PORT_KEY_NAME])

		self.active_threads = 0 
		self.args = args

	def create_static_index(self):
		"""Create a static index page."""
		# right now this is VERY simple - copy the template file and insert some variables.
		STATIC_TEMPLATE = "static_template.html"

		template = os.path.join(self.STATIC_DIR, STATIC_TEMPLATE)
		f = open(template,'r')
		lines = str(f.read())
		f.close()

		lines = lines.replace('<!-- ::VERSION:: -->', "- version %s" % self.VERSION)
		lines = lines.replace('<!-- ::PUBLIC_KEY:: -->', self.notary_public_key)

		index = os.path.join(self.STATIC_DIR, self.STATIC_INDEX)
		f = open (index, 'w')
		print >> f, lines
		f.close()

	def get_xml(self, host, port, service_type):
		"""
		Query the database and build a response containing any known keys for the given service.
		"""

		service = str(host + ":" + port + "," + service_type)

		print "Request for '%s'" % service
		sys.stdout.flush()
		obs = self.ndb.get_observations(service)
		timestamps_by_key = {}
		keys = []

		num_rows = 0 
		for (name, key, start, end) in obs:
			num_rows += 1 
			if key not in keys:
				timestamps_by_key[key] = []
				keys.append(key)
			timestamps_by_key[key].append((start, end))

		if num_rows == 0: 
			# rate-limit on-demand probes
			if self.active_threads < 10: 
				print "on demand probe for '%s'" % service
				t = OnDemandScanThread(service, 10 , self, self.args)
				t.start()
			else: 
				print "Exceeded on demand threshold, not probing '%s'" % service
			# return 404, assume client will re-query
			raise cherrypy.HTTPError(404)
	
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
		return top_element.toprettyxml() 

	@cherrypy.expose
	def index(self, host=None, port=None, service_type=None):
		if (host == None and port == None and service_type == None):
			# probably a visitor that doesn't know what this server is for.
			# serve a static explanation page
			path = os.path.join(cherrypy.request.app.config['/']['tools.staticfile.root'], self.STATIC_INDEX)
			return cherrypy.lib.static.serve_file(path)
		elif (host == None or port == None or service_type == None):
			raise cherrypy.HTTPError(400)

		if (service_type not in notary_common.SERVICE_TYPES):
			raise cherrypy.HTTPError(404)
			
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
		try:
			fp = attempt_observation_for_service(self.sid, self.timeout_sec)

			# create a new db instance, since we're on a new thread
			# pass through any args we have so we'll connect to the same database in the same way
			db = ndb(self.args)

			notary_common.report_observation_with_db(db, self.sid, fp)
		except Exception, e:
			traceback.print_exc(file=sys.stdout)

		self.server_obj.active_threads -= 1




# create an instance here so command-line args will be automatically passed and parsed
# before we start the web server
notary = NotaryHTTPServer()

# PATCH: cherrypy has problems binding to the port on hosted server spaces
# https://bitbucket.org/cherrypy/cherrypy/issue/1100/cherrypy-322-gives-engine-error-when
# use this workaround until 1100 is available for release and we can upgrade
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

