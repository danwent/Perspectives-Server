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

"""
An SSL scanner that uses openssl.
"""

import argparse
import logging
import os
import re
from subprocess import Popen, PIPE
import sys

# By default, we do not probe using TLS 'Server Name Indication' (SNI)
# as it was only compiled into openssl by default since 0.9.8j .
# If you have a version of openssl with SNI support, change the value of
# this variable, as your notary probing will be more accurate.
USE_SNI = False


# note: timeout is ignored for now
def attempt_observation_for_service(service, timeout):
	dns_and_port = service.split(",")[0]
	dns = dns_and_port.split(":")[0]

	cmd1_args = ["openssl","s_client","-connect", dns_and_port ]
	if (USE_SNI):
		cmd1_args += [ "-servername", dns ]
	p1 = Popen(cmd1_args, stdin=file(os.devnull, "r"), stdout=PIPE, stderr=None)
	p2 = Popen(["openssl","x509","-fingerprint","-md5", "-noout"],
		stdin=p1.stdout, stdout=PIPE, stderr=None)
	output = p2.communicate()[0].strip()
	p1.wait()
	p2.wait()

	if p2.returncode != 0:
		raise Exception("ERROR: Could not fetch/decode certificate for '%s'" % dns_and_port)

	fp_regex = re.compile("^MD5 Fingerprint=[A-F0-9]{2}(:([A-F0-9]){2}){15}$")
	if not fp_regex.match(output):
		raise Exception("ERROR: invalid fingerprint '%s'" % output)

	return output.split("=")[1].lower()


if __name__ == "__main__":

	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('service',
			help="A service name of the form 'host:port' - e.g. github.com:443.")

	args = parser.parse_args()
	service = args.service

	try:
		fp = attempt_observation_for_service(service, 10)
		print "Successful scan complete: '%s' has key '%s' " % (service,fp)
	except Exception as e:
		print "Error scanning for %s" % service
		logging.exception(e)

