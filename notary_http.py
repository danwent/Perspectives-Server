import cherrypy
from xml.dom.minidom import parseString, getDOMImplementation
import struct
import base64
import hashlib
import sqlite3
from M2Crypto import BIO, RSA, EVP


DB_FILE="notary.sqlite"
PRIV_KEY_FILE="keys/cmu.priv" 
notary_priv_key= open(PRIV_KEY_FILE,'r').read() 


def get_xml(service_id): 
	conn = sqlite3.connect(DB_FILE)
	cur = conn.cursor()
	cur.execute("select * from observations where service_id = ?", (service_id,))
	timestamps_by_key = {}
	keys = []
	for row in cur: 
		k = row[1]
		if k not in keys: 
			timestamps_by_key[k] = []
			keys.append(k) 
		timestamps_by_key[k].append((row[2],row[3]))

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

	packed_data = service_id + struct.pack("B", 0) + packed_data 

	m = hashlib.md5()
	m.update(packed_data)
	bio = BIO.MemoryBuffer(notary_priv_key)
	rsa_priv = RSA.load_key_bio(bio)
	sig_before_raw = rsa_priv.sign(m.digest(),'md5') 
	sig = base64.standard_b64encode(sig_before_raw) 

	top_element.setAttribute("sig",sig)
	print top_element.toprettyxml() 
	return top_element.toprettyxml() 


class NotaryHTTPServer:
    def index(self, host=None, port=None, service_type=None):
	if (host == None or port == None or service_type == None): 
		raise cherrypy.HTTPError(400)
      	return get_xml(host + ":" + port + "," + service_type)
 
    index.exposed = True

cherrypy.quickstart(NotaryHTTPServer())

