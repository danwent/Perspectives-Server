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
Separate the database details from any code that wants to talk to the database.

This allows us to drop in any database without changing code,
and keeps things modular for easier refactoring.
"""

import time
import sqlite3
import argparse


class ndb:
	"""
	Notary database interface - create and interact with database tables.

	Currently this class is only intended to be called by modules that
	extend its argparser. i.e.

	parser = argparse.ArgumentParser(parents=[ndb.get_parser() #...
	# ...
	args = parser.parse_args()
	ndb = ndb(args)
	"""

	# add more connection info here if you need that type of db
	# TODO: also supported: postgresql, mysql, oracle, mssql, and firebird
	SUPPORTED_DBS = {'sqlite': {'defaultdbname': 'notary.sqlite',
								'defaultusername': '', #not used by sqlite
								'defaulthostname': '',
								'connstr': 'sqlite:///%s%s%s%s'}
					}
	DEFAULT_DB_TYPE = 'sqlite'
	DB_PASSWORD_FIELD = 'NOTARY_DB_PASSWORD'

	def __init__(self, args):
		"""
		Initialize a new ndb object.

		Some extra work is done here to make it easier for callers to import this module.
		"""

		# sanity/safety check:
		# filter the args and send only those that are relevant to __actual_init__.
		# this makes it simple for callers that extend our argparser to use us
		# (i.e. by just calling 'ndb = ndb(args)')
		# but ensures we pass only the correct parameters,
		# so there are no errors.
		good_args = ndb.filter_args(vars(args))
		self.__actual_init__(**good_args)

	# note: keep these arg names the same as the argparser args - see filter_args()
	# we supply default values so everything can be passed as a named argument.
	def __actual_init__(self, dbname=SUPPORTED_DBS[DEFAULT_DB_TYPE]['defaultdbname'],
						dbuser=SUPPORTED_DBS[DEFAULT_DB_TYPE]['defaultusername'],
						dbhost=SUPPORTED_DBS[DEFAULT_DB_TYPE]['defaulthostname'],
						dbtype=DEFAULT_DB_TYPE):
		"""
		Initialize a new ndb object.

		The actual initialization work is done here to hide the details
		of the extra steps we take inside __init__.
		"""

		self.db_file = dbname
		self.conn = None
		self.cur = None


	@classmethod
	def get_parser(self):
		"""
		Get a parser object with the correct arguments for the ndb class.
		Can be used by calling modules that need to connect to a notary database to build their own parser on top.
		"""

		# Several other modules use us to connect to notary databases.
		# We let them access and extend our arg parser so we can keep the code in one place.
		# Note: do not use 'None' as a default for aguments: it interferes with set_config_args().

		parser = argparse.ArgumentParser(add_help=False) #don't specify description or epilogue so the module that includes us can write their own.
		dbgroup = parser.add_argument_group('optional database arguments')
		dbgroup.add_argument('--dbtype', '--db-type', '-t', default=self.DEFAULT_DB_TYPE,
			choices=self.SUPPORTED_DBS.keys(),
			help='Type of database to use. Must be one of {' + ", ".join(self.SUPPORTED_DBS.keys()) + '}. Default: \'%(default)s\'')
		dbgroup.add_argument('--dbname', '--db-name', '-n', default=self.SUPPORTED_DBS[self.DEFAULT_DB_TYPE]['defaultdbname'],
			help='Name of database to connect to. Default: \'%(default)s\'')
		dbgroup.add_argument('--dbhost', '--db-host', '-o', default=self.SUPPORTED_DBS[self.DEFAULT_DB_TYPE]['defaulthostname'],
			help='Machine that hosts the database. Default: \'%(default)s\'')
		dbgroup.add_argument('--dbuser', '--db-user', '-u', default=self.SUPPORTED_DBS[self.DEFAULT_DB_TYPE]['defaultusername'],
			help="User account to connect with. Default: \'%(default)s\'. The password for this account is read from the environment variable '" + 
				self.DB_PASSWORD_FIELD + "', so you never have to store it in code.")

		return parser

	@classmethod
	def filter_args(self, argsdict):
		"""
		Filter a dictionary of arguments and return only ones that are applicable to ndb.

		The ndb class is instantiated from many different places,
		many of which extend the ndb argparser.
		If the ndb argparser changes (e.g. a future version adds a new argument)
		it is annoying and too much work to update all of the calls to ndb.__init__().
		Thus we use this function internally to filter incoming args
		and make sure that only the parameters applicable to ndb are used.
		"""
		valid_args = ndb.__actual_init__.func_code.co_varnames[:ndb.__actual_init__.func_code.co_argcount]
		d = dict((key, val) for key, val in argsdict.iteritems() if key in valid_args)

		if 'self' in d:
			del d['self']

		return d


	def get_conn(self):
		if (self.conn == None):
			self.conn = sqlite3.connect(db_file)
		return self.conn

	def get_cursor(self):
		if (self.cur == None):
			self.cur = gen_conn.cursor()
		return self.cur

	def get_all_observations():
		"""Get all observations."""
		return self.get_cursor().execute("select * from observations where key not NULL")

	def get_observations(service_id):
		"""Get all observations for a given service."""
		return self.get_cursor().execute("select * from observations where service_id = ? and key not NULL", (service_id,))

	def insert_observation(service_id, key, start_time, end_time):
		"""Insert a new Observation about a service/key pair."""
		self.get_cursor().execute("insert into observations (service_id, key, start, end) values (?,?,?,?)",
			(service_id, key, start_time, end_time))

	def update_observation_end_time(service_id, fp, old_end_time, new_end_time):
		"""Update the end time for a given Observation."""
		self.get_cursor.execute("update observations set end = ? where service_id = ? and key = ? and end = ?",
			(new_end_time, service_id, fp, most_recent_time))