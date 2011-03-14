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

import cherrypy
from xml.dom.minidom import parseString, getDOMImplementation
import struct
import base64
import hashlib
import sqlite3
from M2Crypto import BIO, RSA, EVP
import sys
import threading 
from ssl_scan_sock import attempt_observation_for_service, SSLScanTimeoutException
import traceback 
import notary_common 

class NotaryHTTPServer:

	def __init__(self, db_file, priv_key_file): 
		self.db_file = db_file
		self.notary_priv_key= open(priv_key_file,'r').read() 
		self.active_threads = 0 

	def get_xml(self, service_id): 
		conn = sqlite3.connect(self.db_file)
		cur = conn.cursor()
		cur.execute("select * from observations where service_id = ? and key not NULL", (service_id,))
		timestamps_by_key = {}
		keys = []

		num_rows = 0 
		for row in cur:
			num_rows += 1 
			k = row[1]
			if k not in keys: 
				timestamps_by_key[k] = []
				keys.append(k) 
			timestamps_by_key[k].append((row[2],row[3]))
		
		if num_rows == 0: 
			# rate-limit on-demand probes
			if self.active_threads < 10: 
				t = OnDemandScanThread(service_id,10,self)
				t.start()
				
			# return 404, assume client will re-query
			raise cherrypy.HTTPError(404)
	
		dom_impl = getDOMImplementation() 
		new_doc = dom_impl.createDocument(None, "notary_reply", None) 
		top_element = new_doc.documentElement
		top_element.setAttribute("version","1") 
		top_element.setAttribute("sig_type", "rsa-md5") 
	
		packed_data = ""
	
		for k in keys:
			key_elem = new_doc.createElement("key")
			key_elem.setAttribute("type","ssl")
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
	
		packed_data = service_id.encode() + struct.pack("B", 0) + packed_data 
	
		m = hashlib.md5()
		m.update(packed_data)
		bio = BIO.MemoryBuffer(self.notary_priv_key)
		rsa_priv = RSA.load_key_bio(bio)
		sig_before_raw = rsa_priv.sign(m.digest(),'md5') 
		sig = base64.standard_b64encode(sig_before_raw) 
	
		top_element.setAttribute("sig",sig)
		return top_element.toprettyxml() 

	def index(self, host=None, port=None, service_type=None):
		if (host == None or port == None or service_type == None): 
			raise cherrypy.HTTPError(400)
		cherrypy.response.headers['Content-Type'] = 'text/xml'
      		return self.get_xml(host + ":" + port + "," + service_type)
 
    	index.exposed = True


class OnDemandScanThread(threading.Thread): 

	def __init__(self, sid,timeout_sec,server_obj): 
		self.sid = sid
		self.server_obj = server_obj
		self.timeout_sec = timeout_sec
		threading.Thread.__init__(self)
		self.server_obj.active_threads += 1

	def run(self): 
		try:
			fp = attempt_observation_for_service(self.sid, self.timeout_sec)
			notary_common.report_observation(self.server_obj.db_file, self.sid, fp)
		except Exception, e:
			pass 

		self.server_obj.active_threads -= 1




if len(sys.argv) != 3:
	print "usage: <notary-database-file> <private-key-file>" 
	exit(1) 

cherrypy.config.update({ 'server.socket_port' : 8080,
			 'server.socket_host' : "0.0.0.0",
			 'request.show_tracebacks' : False,  
			 'log.access_file' : None,  # default for production 
			 'log.error_file' : 'error.log', 
			 'log.screen' : False } ) 
cherrypy.quickstart(NotaryHTTPServer(sys.argv[1], sys.argv[2]))

