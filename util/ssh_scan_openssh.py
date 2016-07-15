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
An SSH scanner that uses ssh-keyscan.
"""
from __future__ import print_function

from subprocess import *
import argparse
import logging
import os
import re
import sys
import tempfile
import traceback


def attempt_observation_for_service(service, timeout):
	# note: timeout is ignored for now
	dns_and_port = service.split(",")[0]
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
			stdin=file(os.devnull, "r"), stdout=fd, stderr=None)
		p1.wait()
		if p1.returncode != 0:
			logging.error("Error fetching ssh '%s' key for %s" % (key_type, dns_and_port))
			continue

		p2 = Popen(["ssh-keygen","-l","-f", fname],
			stdin=file(os.devnull, "r"), stdout=PIPE, stderr=None)
		output = p2.communicate()[0].strip()
		p2.wait()

		if p2.returncode != 0:
			logging.error("Error fetching ssh key of type '%s' for '%s'" % (key_type, dns_and_port))
			continue

		fp = output.split()[1]
		fp_regex = re.compile("^[a-f0-9]{2}(:([a-f0-9]){2}){15}$")
		if not fp_regex.match(fp):
			logging.error("Invalid fingerprint '%s'" % output)
			continue
		
		return fp 

	try:
		os.remove(fname)
	except WindowsError:
		pass
	raise Exception("all key types failed") 

if __name__ == "__main__":

	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument('service',
			help="A service name of the form 'host:port' - e.g. remoteserver.com:22.")

	args = parser.parse_args()
	service = args.service

	try: 
		fp = attempt_observation_for_service(service, 10)
		print("Successful scan complete: '%s' has key '%s' " % (service, fp))
	except:
		print("Error scanning for %s" % service)
		traceback.print_exc(file=sys.stdout)
