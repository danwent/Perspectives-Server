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
import traceback  
from client_common import verify_notary_signature, notary_reply_as_text,fetch_notary_xml, parse_http_notary_list

if len(sys.argv) != 3 and len(sys.argv) != 4: 
	print "usage: %s <service-id> <notary-list-file> [text|xml]" % sys.argv[0]
	exit(1)  

output_type = "text"
if len(sys.argv) == 4: 
	output_type = sys.argv[3] 

sid = sys.argv[1]
server_list = parse_http_notary_list(sys.argv[2]) 

for s in server_list: 
	try:
		s["results"] = None
		server = s["host"].split(":")[0]
		port = s["host"].split(":")[1]
		code, xml_text = fetch_notary_xml(server,int(port), sid)
		if code == 404: 
			pass
		if code != 200: 
			print "'%s' returned error code: %s" % (s["host"],code)
		elif not verify_notary_signature(sid, xml_text, s["public_key"]):
			print "Signature from '%s' failed, ignoring results" % s["host"]
		else: 
			# results are good
			s["results"] = xml_text
			
	except Exception, e:
		print "Exception contacting notary server:" 
		traceback.print_exc(e)

if output_type == "text": 
	for s in server_list: 
		print 50 * "*"
		print "Results for notary server '%s'" % s["host"]
		if s["results"] is None: 
			print "<No notary results>" 
		else: 
			print notary_reply_as_text(s["results"])
elif output_type == "xml":
	for s in server_list: 
		print 50 * "*"
		if s["results"] is None: 
			print "<No notary results>" 
		else: 
			print notary_reply_as_text(s["results"])
else:
	print "Unknown output type '%s'" % output_type
 
	
