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

from subprocess import *
import re
import sys
import notary_common 

# By default, we do not probe using TLS 'Server Name Indication' (SNI) 
# as it was only compiled into openssl by default since 0.9.8j .  
# If you have a version of openssl with SNI support, change the value of
# this variable, as your notary probing will be more accurate.
USE_SNI = False 

if len(sys.argv) != 3 and len(sys.argv) != 2:
	print >> sys.stderr, "ERROR: usage: <service-id> [notary-db-file>]"
	exit(1)

service_id = sys.argv[1]
dns_and_port = service_id.split(",")[0]
dns = dns_and_port.split(":")[0] 

cmd1_args = ["openssl","s_client","-connect", dns_and_port ] 
if (USE_SNI): 
	cmd1_args += [ "-servername", dns ]  
p1 = Popen(cmd1_args, stdin=file("/dev/null", "r"), stdout=PIPE, stderr=None)
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

if len(sys.argv) == 3: 
	notary_common.report_observation(sys.argv[2], service_id, fp) 
else: 
	print "INFO: no database specified, not saving observation"

print "Successful scan complete: '%s' has key '%s' " % (service_id,fp)
