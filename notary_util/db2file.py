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
Export Observation data from a network notary database.
"""

import time
import argparse

from notary_db import ndb


DEFAULT_OUTFILE = "-"
service_type_to_key_type = { "1" : "ssh", "2" : "ssl" } #TODO: put in notary_common


def print_long_output(obs):
	"""Print output in an expanded format, grouping keys for each service."""

	old_sid = None
	num_sids = 0

	key_to_obs  = {}
	for (service, key, start, end) in obs:
		sid = service
		if old_sid != sid:
			num_sids += 1
			if num_sids % 1000 == 0:
				print "processed %s service-ids" % num_sids
			if old_sid is not None:
				print_sid_info(old_sid, key_to_obs)
			key_to_obs = {}
			old_sid = sid

		if key not in key_to_obs:
			key_to_obs[key] = []
		key_to_obs[key].append((start, end))

		print_sid_info(sid, key_to_obs)

def print_sid_info(sid, key_to_obs):
	"""Print all of the keys for a single service."""
	s_type = sid.split(",")[1]
	
	if s_type not in service_type_to_key_type:
		return	
	
	print >> output_file, ""
	print >> output_file, "Start Host: '%s'" % sid
	key_type_text = service_type_to_key_type[s_type]
	for key in key_to_obs:
		if key is None: 
			continue 
		print >> output_file, "%s key: %s" % (key_type_text,key)
		for ts in key_to_obs[key]: 
			print >> output_file, "start:\t%s - %s" % (ts[0],time.ctime(ts[0]))
			print >> output_file, "end:\t%s - %s" % (ts[1],time.ctime(ts[1]))
		print >> output_file, ""
	print >> output_file, "End Host"

def print_tuples(obs):
	"""Print output in a simple tuple format, one record per line. This makes it easy to import the data somewhere else."""

	# note: lines starting with '#' should be ignored by the importer.

	output = [] # use list appending for better performance than string concatenation
	output.append("# Export of network notary Observations from %s" %args.dbname)
	output.append("# %s\n" % time.ctime())
	for (service, key, start, end) in obs:
		output.append("(%s, %s, %s, %s)" % (service, key, start, end))

	output = '\n'.join(output)
	print >> output_file, output



parser = argparse.ArgumentParser(parents=[ndb.get_parser()], description=__doc__)
parser.add_argument('output_file', type=argparse.FileType('w'), nargs='?', default=DEFAULT_OUTFILE,
			help="File to write data to. Use '-' to write to stdout. Writing to stdout is the default.")
formats = parser.add_mutually_exclusive_group()
formats.add_argument('--tuples', '--tup', action='store_true',
			help=print_tuples.__doc__ + " This is the default.")
formats.add_argument('--long', action='store_true',
			help=print_long_output.__doc__)


args = parser.parse_args()

# pass ndb the args so it can use any relevant ones from its own parser
ndb = ndb(args)

output_file = args.output_file
obs = ndb.get_all_observations()

if (args.long):
	print_long_output(obs)
else:
	print_tuples(obs)
