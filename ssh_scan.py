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


from subprocess import *
import re
import sys
import tempfile
import os
import notary_common 

if len(sys.argv) != 3:
	print >> sys.stderr, "ERROR: usage: <service-id> <notary-db-file>"
	exit(1)

service_id = sys.argv[1]
dns_and_port = service_id.split(",")[0]
dns_name, port = dns_and_port.split(":")
	
fname = tempfile.mktemp()

# this sucks, because for any host that is unreachable,
# we will try once per key type.
# Also, if the server uses multiple types of keys, it will only
# record the first one.
# We tolerate this for now because the number of ssh machines is
# small and we plan on phasing it out anyway
for key_type in ("rsa","dsa","rsa1"):
	fd = open(fname,'w')
	p1 = Popen(["ssh-keyscan", "-t", key_type, "-p", port, dns_name ],
		stdin=file("/dev/null", "r"), stdout=fd, stderr=None)
	p1.wait()
	if p1.returncode != 0:
		print >> sys.stderr, "ERROR: error fetching ssh '%s' key for %s" % (key_type,dns_and_port)
		continue

	p2 = Popen(["ssh-keygen","-l","-f", fname],
		stdin=file("/dev/null", "r"), stdout=PIPE, stderr=None)
	output = p2.communicate()[0].strip()
	p2.wait()

	if p2.returncode != 0:
		print >> sys.stderr, "ERROR: error fetching ssh key of type '%s' for '%s'" % (key_type,dns_and_port)
		continue

	fp = output.split()[1]
	fp_regex = re.compile("^[a-f0-9]{2}(:([a-f0-9]){2}){15}$")
	if not fp_regex.match(fp):
		print >> sys.stderr, "ERROR: invalid fingerprint '%s'" % output
		continue
	
	notary_common.report_observation(sys.argv[2], service_id, fp) 
	print "Successful scan complete: '%s' has key '%s' " % (service_id,fp)
	break

os.remove(fname)
