#!@python_EXEC@

from subprocess import *
import re
import sys
import notary_common 

if len(sys.argv) != 3:
	print >> sys.stderr, "ERROR: usage: <service-id> <notary-db-file>"
	exit(1)

service_id = sys.argv[1]
dns_and_port = service_id.split(",")[0]

p1 = Popen(["openssl","s_client","-connect", dns_and_port],
		stdin=file("/dev/null", "r"), stdout=PIPE, stderr=None)
p2 = Popen(["openssl","x509","-fingerprint","-md5", "-noout"],
		stdin=p1.stdout, stdout=PIPE, stderr=None)
output = p2.communicate()[0].strip()
p1.wait()
p2.wait()

if p2.returncode != 0:
	print >> sys.stderr, "ERROR: Could not fetch/decode certificate for '%s'" % dns_and_port
	exit(1)

fp_regex = re.compile("^MD5 Fingerprint=[A-F0-9]{2}(:([A-F0-9]){2}){15}$")
if not fp_regex.match(output):
	print >> sys.stderr, "ERROR: invalid fingerprint '%s'" % output
	exit(1)

fp = output.split("=")[1].lower()
dns_name, port = dns_and_port.split(":")


notary_common.report_observation(sys.argv[2], service_id, fp) 
