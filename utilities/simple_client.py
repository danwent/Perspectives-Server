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

import sys
import traceback  
from client_common import verify_notary_signature, notary_reply_as_text,fetch_notary_xml 

if len(sys.argv) != 4 and len(sys.argv) != 5: 
	print "usage: %s <service-id> <notary-server> <notary-port> [notary-pubkey]" % sys.argv[0]
	exit(1)  


notary_pub_key = None
if len(sys.argv) == 5: 
	notary_pub_key_file = sys.argv[4] 
	notary_pub_key = open(notary_pub_key_file,'r').read() 

try: 
	code, xml_text = fetch_notary_xml(sys.argv[2],int(sys.argv[3]), sys.argv[1])
	if code == 404: 
		print "Notary has no results"
	elif code != 200: 
		print "Notary server returned error code: %s" % code
except Exception, e:
	print "Exception contacting notary server:" 
	traceback.print_exc(e)
	exit(1) 

print 50 * "-"
print "XML Response:" 
print xml_text

print 50 * "-"

if notary_pub_key:
	if not verify_notary_signature(xml_text, notary_pub_key):
		print "Signature verify failed.  Results are not valid"
		exit(1)  
else: 
	print "Warning: no public key specified, not verifying notary signature" 

print "Results:" 

print notary_reply_as_text(xml_text) 
