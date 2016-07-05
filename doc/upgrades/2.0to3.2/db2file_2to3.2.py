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
Export Observation data from a version 2x notary database into
the format for a version 3x database.
"""

from __future__ import print_function

import argparse
import os
import sys
import time

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String


DEFAULT_OUTFILE = "-"
DEFAULT_DB = 'notary.sqlite'

SSH_TYPE = "1"
SSL_TYPE = "2"
SERVICE_TYPES = {SSH_TYPE: "ssh",
				 SSL_TYPE: "ssl"}


# class to base ORM classes on
ORMBase = declarative_base()

class Observations(ORMBase):
	"""
	Version 2x schema observations
	"""
	__tablename__ = 'observations'
	service_id = Column(String, primary_key=True)
	key = Column(String)
	start = Column(Integer)
	end = Column(Integer)


class ndb2x:
	"""
	This is a pared-down version of the notary database class
	solely so we can export our data.
	Don't use this for production deployment!
	"""

	def __init__(self, dbname):
		"""Connect to the database."""
		self.db = create_engine('sqlite:///' + dbname)
		self.Session = sessionmaker(bind=self.db)

	def __del__(self):
		"""Clean up any remaining database connections."""

		if ((hasattr(self, 'Session')) and (self.Session != None)):
			try:
				self.Session.close_all()
				del self.Session
			except Exception as e:
				print("Error closing database connection: '%s'" % ((e)), file=sys.stderr)

		self.db.dispose()
		del self.db

	def get_all_observations(self):
		"""Get all observations."""
		return self.Session().query(Observations).\
			order_by(Observations.service_id).\
			values(Observations.service_id, Observations.key, Observations.start, Observations.end)



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
				print("processed %s service-ids" % num_sids)
			if old_sid is not None:
				_print_sid_info(old_sid, key_to_obs)
			key_to_obs = {}
			old_sid = sid

		if key not in key_to_obs:
			key_to_obs[key] = []
		key_to_obs[key].append((start, end))

		_print_sid_info(sid, key_to_obs)

def _print_sid_info(sid, key_to_obs):
	"""Print all of the keys for a single service."""
	s_type = sid.split(",")[1]

	if (s_type not in SERVICE_TYPES):
		return

	with open(output_file, 'a') as f:
		print("", file=f)
		print("Start Host: '%s'" % sid, file=f)
		key_type_text = SERVICE_TYPES[s_type]
		for key in key_to_obs:
			if key is None:
				continue
			print("%s key: %s" % (key_type_text,key), file=f)
			for ts in key_to_obs[key]:
				print("start:\t%s - %s" % (ts[0],time.ctime(ts[0])), file=f)
				print("end:\t%s - %s" % (ts[1],time.ctime(ts[1])), file=f)
			print("", file=f)
		print("End Host", file=f)

def print_tuples(obs):
	"""Print output in a simple tuple format, one record per line. This makes it easy to import the data somewhere else."""

	# note: lines starting with '#' should be ignored by the importer.

	output = [] # use list appending for better performance than string concatenation
	output.append("# Export of network notary version 2.x Observations from %s" %args.dbname)
	output.append("# %s\n" % time.ctime())
	for (service, key, start, end) in obs:
		output.append("(%s, %s, %s, %s)" % (service, key, start, end))

	with open(output_file, 'a') as f:
		for line in output:
			print(line + '\n', file=f)





parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--dbname', '--db-name', '-n', default=DEFAULT_DB,
			help='Name of database to connect to. Default: \'%(default)s\'')
parser.add_argument('output_file', type=argparse.FileType('w'), nargs='?', default=DEFAULT_OUTFILE,
			help="File to write data to. Use '-' to write to stdout. Writing to stdout is the default.")
formats = parser.add_mutually_exclusive_group()
formats.add_argument('--tuples', '--tup', action='store_true',
			help=print_tuples.__doc__ + " This is the default.")
formats.add_argument('--long', action='store_true',
			help=print_long_output.__doc__)


args = parser.parse_args()

if not os.path.exists(args.dbname):
	raise ValueError("Database '%s' does not exist." % (args.dbname,))
	exit(1)

ndb = ndb2x(args.dbname)

output_file = args.output_file
obs = ndb.get_all_observations()

if (args.long):
	print_long_output(obs)
else:
	print_tuples(obs)

