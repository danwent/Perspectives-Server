import time
import sys
import traceback  
from client_common import verify_notary_signature, print_notary_reply,fetch_notary_xml, parse_http_notary_list
from generate_svg import get_svg_graph 

if len(sys.argv) != 4: 
	print "usage: %s <service-id> <notary-list-file> <len-days>" % sys.argv[0]
	exit(1)  


sid = sys.argv[1]
server_list = parse_http_notary_list(sys.argv[2]) 

for s in server_list: 
	try: 
		s["results"] = None
		server = s["host"].split(":")[0]
		port = s["host"].split(":")[1]
		code, xml_text = fetch_notary_xml(server,int(port), sid)
		if code == 200 and verify_notary_signature(sid, xml_text, s["public_key"]):
			s["results"] = xml_text
			
	except Exception, e:
		pass

print get_svg_graph(sid, server_list, int(sys.argv[3]), time.time())

