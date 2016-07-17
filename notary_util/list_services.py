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
Print a list of service names from a network notary database, one per line.
Data can be filtered based on the last time the notary successfully observed
a key from each service.
"""

from __future__ import print_function

import sys
import time
import argparse

from notary_db import ndb


DAYS_META_NAME = 'Days'
DEFAULT_DAYS = 10
DEFAULT_OUTFILE = "-"

def print_ids(outfile, ids):
	"""Print all of the ids to the given file."""
	for (name) in ids:
		# print as string instead of tuple, to make it easier to use elsewhere
		print(name[0], file=outfile)

def get_parser():
	"""Return an argument parser for this module."""
	parser = argparse.ArgumentParser(parents=[ndb.get_parser()],
	description=__doc__,
	epilog="This module can be used to generate a list of all services considered 'live' or 'dead'.")

	parser.add_argument('output_file', type=argparse.FileType('w'), nargs='?', default=DEFAULT_OUTFILE,
				help="File to write data to. Use '-' to write to stdout. Writing to stdout is the default if no file is given.")
	listgroup = parser.add_mutually_exclusive_group()
	listgroup.add_argument('--all', '-a', action='store_true', default=False,
				help="List all services. This is the default if no action is specified.")
	listgroup.add_argument('--newer', '--newest', '--new', metavar=DAYS_META_NAME, type=int, nargs='?', default=None, const=DEFAULT_DAYS,
				help="Only list services with an observation newer than '%s' days. Default: %s." % (DAYS_META_NAME, DEFAULT_DAYS))
	listgroup.add_argument('--older', '--oldest', '--old', metavar=DAYS_META_NAME, type=int, nargs='?', default=None, const=DEFAULT_DAYS,
				help="Only list services with a MOST RECENT observation that is older than than '%s' days. Default: %s." % (DAYS_META_NAME, DEFAULT_DAYS))
	return parser

def main(db, output_file=DEFAULT_OUTFILE, list_all=True, list_newer=False, list_older=False):
	"""Run the main program."""
	# set a default action
	if (list_all == False and list_newer == None and list_older == None):
		list_all = True

	ids = None

	if list_all:
		ids = db.get_all_service_names()
	else:
		cur_time = int(time.time())

		if list_older:
			ids = db.get_oldest_service_names(int(cur_time - (3600 * 24 * list_older)))
		else:
			ids = db.get_newest_service_names(int(cur_time - (3600 * 24 * list_newer)))

	if (ids != None):
		if output_file == sys.stdout:
			print_ids(output_file, ids)
		else:
			with output_file as f:
				print_ids(output_file, ids)

if __name__ == "__main__":
	args = get_parser().parse_args()
	# pass ndb the args so it can use any relevant ones from its own parser
	db = ndb(args)
	main(db, args.output_file, args.all, args.newer, args.older)
