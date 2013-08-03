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
Import data from a file to the notary database.
Can be used to seed a notary database from another notary's list of services.

File is expected to be a list of tuples, one per line.
Tuples look like:
  (servicename:port, servicetype, rsakey, starttime, endtime)

e.g.
  (domain.com:443,2, aa:bb:cc:dd:ee:ff, 123, 456)

If you have a large number of records to insert (i.e. millions)
you may want to run this *without* echoing database statements,
both to improve speed and to avoid memory issues.
"""

import sys
import os
import re
import time
import argparse

from notary_db import ndb

DEFAULT_INFILE = "-"

def import_records(infile):
	"""Read a file of tuples and extract service and observation data."""

	print "Reading records from '{0}'.".format(infile.name)

	lines = infile.readlines()
	infile.close()

	services = {}
	observations = []
	num_lines = 0
	num_invalid_lines = 0

	# tuples will be formatted like this:
	# (domain.com:443,2, aa:bb:cc:dd:ee:ff, 123, 456)
	#TODO: get correct regex for URLs
	valid_tuple = re.compile("^ *\(([\w\-:,.]+), *([0-9a-fA-F:]+), *(\d+), *(\d+)\) *$")


	for line in lines:

		# remember: ALL INPUT IS EVIL!
		# test each line before passing to the database.
		if (valid_tuple.match(line)):
			match = valid_tuple.match(line)
			service = str(match.group(1))
			key = str(match.group(2))
			start = int(match.group(3))
			end = int(match.group(4))

			services[service] = True
			observations.append((service, key, start, end))

		# ignore comments and blank lines
		elif ((not line.startswith('#')) and (line not in ['\n', '\r\n'])):
			# TODO: could print to file
			#print >> sys.stderr, "Invalid tuple '{0}'".format(line.strip())
			num_invalid_lines +=1

		num_lines += 1
		if (num_lines) % 100000 == 0:
			print "Finished reading {0} lines...".format(num_lines)

	service_count = len(services)
	if (service_count > 0):
		print "Found {0} services. Adding to database.".format(service_count)
		ndb.insert_bulk_services(services.keys())
	else:
		print "No services found."
	print "Found {0} invalid lines.".format(num_invalid_lines)

	if not args.services_only:
		print "Found %s observations. Adding to database." % len(observations)
		#TODO: need to get the service_ids after services are inserted
		for (service, key, start, end) in observations:
			ndb.insert_observation(service, key, start, end)


parser = argparse.ArgumentParser(parents=[ndb.get_parser()], description=__doc__,
	formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('input_file', type=argparse.FileType('r'), nargs='?', default=DEFAULT_INFILE,
			help="File to read from. Use '-' to read from stdin (which is the default).")
parser.add_argument('--services-only', '-s', action='store_true', default=False,
			help="Only import services, not observations.")

args = parser.parse_args()
# pass ndb the args so it can use any relevant ones from its own parser
ndb = ndb(args)
import_records(args.input_file)

