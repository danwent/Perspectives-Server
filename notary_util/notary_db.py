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
import argparse
import os
import sys


from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine import create_engine
from sqlalchemy.orm import sessionmaker, relationship, backref
from sqlalchemy.exc import IntegrityError
from sqlalchemy import Column, Integer, String, Index, ForeignKey


# class to base ORM classes on
ORMBase = declarative_base()

# Notary database schema defined for our ORM.
# Track observations about internet server certificates.
class Services(ORMBase):
	"""
	A server that accepts secure connections.
	Service names take the form 'host:port,servicetype' - e.g. github.com:443,2
	"""
	__tablename__ = 't_services'
	service_id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False, unique=True)

class Observations(ORMBase):
	"""
	The time ranges observed for each key used by a service.
	"""
	__tablename__ = 't_observations'
	service_id = Column(Integer, ForeignKey('t_services.service_id'), primary_key=True)
	key = Column(String, primary_key=True)			#certificate key supplied by a service - e.g. aa:bb:cc:dd:00
	start = Column(Integer) 						#unix timestamp - number of seconds since the epoch. The first time we saw a key for a given service.
	end = Column(Integer)							#another unix timestamp.  The most recent time we saw a key for a given service.

	services = relationship("Services", backref=backref('t_observations', order_by=service_id))

# create indexes to speed up queries
Index('ix_services_name', Services.name)
Index('ix_observations_end', Observations.end)
Index('ix_observations_service_id_key_end', Observations.service_id, Observations.key, Observations.end)



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
	DEFAULT_ECHO = 0

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
						dbtype=DEFAULT_DB_TYPE,
						dbecho=DEFAULT_ECHO):
		"""
		Initialize a new ndb object.

		The actual initialization work is done here to hide the details
		of the extra steps we take inside __init__.
		"""

		if (dbtype in self.SUPPORTED_DBS):

			self.DB_PASSWORD = ''

			# sqlite doesn't support usernames, passwords, or host.
			# since our connstr takes four parameters,
			# strip out username, password, and host for sqlite databases;
			# otherwise sqlite will create a new db file named
			# 'dbuserpassworddbhost' rather than connecting
			# to the intended database.
			if (dbtype == 'sqlite'):
				dbuser = ''
				dbhost = ''
			else:
				try:
					self.DB_PASSWORD = os.environ[self.DB_PASSWORD_FIELD]
				except KeyError:
					# maybe the db has no password.
					# let the caller decide and handle it.
					pass

			if (dbecho):
				dbecho = True

			# set up sqlalchemy objects
			self.db = create_engine(self.SUPPORTED_DBS[dbtype]['connstr'] % (dbuser, self.DB_PASSWORD, dbhost, dbname), echo=dbecho)
			self.conn = self.db.connect()
			ORMBase.metadata.create_all(self.db)
			Session = sessionmaker(bind=self.db)
			self.session = Session()

		else:
			errmsg = "'%s' is not a supported database type" % dbtype
			print >> sys.stderr, errmsg
			raise Exception(errmsg)


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
		dbgroup.add_argument('--dbecho', '--db-echo', nargs='?',
			# use default 0 but const 1 so we get the expected behaviour if the argument is passed with no parameter.
			default=self.DEFAULT_ECHO, const=1,
			metavar='0/1', type=int,
			help='Echo all SQL statements and other database messages to stdout. If passed with no value echo defaults to true.')

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

	# actual data methods follow

	def get_all_services(self):
		"""Get all service names."""
		return self.session.query(Services.name).all()

	def get_newest_services(self, end_limit):
		"""Get service names with an observation newer than end_limit."""
		return self.session.query(Services.name).join(Observations).\
			filter(Observations.end > end_limit)

	def get_oldest_services(self, end_limit):
		"""Get service names with a MOST RECENT observation that is older than end_limit."""
		return self.session.query(Services).join(Observations).filter(\
			~Services.name.in_(\
				self.get_newest_services(end_limit))).\
			values(Services.name)

	def insert_service(self, service_name):
		"""Add a new Service to the database."""
		# if this is too slow we could add bulk insertion
		srv = self.session.query(Services).filter(Services.name == service_name).first()

		if (srv == None):
			srv = Services(name = service_name)
			self.session.add(srv)
			self.session.commit()

		return srv

	def get_all_observations(self):
		"""Get all observations."""
		return self.session.query(Services).join(Observations).\
			order_by(Services.name).\
			values(Services.name, Observations.key, Observations.start, Observations.end)

	def get_observations(self, service):
		"""Get all observations for a given service."""
		return self.session.query(Services).join(Observations).\
			filter(Services.name == service).\
			values(Services.name, Observations.key, Observations.start, Observations.end)

	def insert_observation(self, service, key, start_time, end_time):
		"""Insert a new Observation about a service/key pair."""
		srv = self.insert_service(service)

		try:
			newob = Observations(service_id=srv.service_id, key=key, start=start_time, end=end_time)
			self.session.add(newob)
			self.session.commit()
		except IntegrityError:
			print "Error: Observation for (%s, %s) already present. If you want to update it call that function instead. Ignoring." % (service, key)
			self.session.rollback()

	def update_observation_end_time(self, service, fp, old_end_time, new_end_time):
		"""Update the end time for a given Observation."""
		curtime = int(time.time())

		if (new_end_time == None):
			new_end_time = curtime
		if (old_end_time == None):
			old_end_time = curtime

		ob = self.session.query(Observations).join(Services)\
			.filter(Services.name == service)\
			.filter(Observations.key == fp)\
			.filter(Observations.end == old_end_time).first()
		if (ob != None):
			ob.end = new_end_time
			self.session.commit()
		else:
			print >> sys.stderr, "Attempted to update the end time for service '%s' key '%s',\
				but no records for it were found! This is really bad; code shouldn't be here." % (service, fp)
