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

from __future__ import print_function

import argparse
from contextlib import contextmanager
import logging
import os
import re
import threading
import time
import ConfigParser

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine import create_engine
from sqlalchemy.event import listen
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, backref, validates
from sqlalchemy.pool import Pool
from sqlalchemy.exc import IntegrityError, ProgrammingError, OperationalError, ResourceClosedError
from sqlalchemy.schema import CheckConstraint, UniqueConstraint
from sqlalchemy.sql import select, and_, func
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
	service_id = Column(Integer, nullable=False, primary_key=True)
	name = Column(String, nullable=False, unique=True)

class Observations(ORMBase):
	"""
	The time ranges observed for each key used by a service.
	"""
	__tablename__ = 't_observations'
	observation_id = Column(Integer, nullable=False, primary_key=True)
	service_id = Column(Integer, ForeignKey('t_services.service_id'), nullable=False)
	key = Column(String, nullable=False)	#md5 certificate key supplied by a service - e.g. aa:bb:cc:dd:00
	start = Column(Integer, nullable=False)	#unix timestamp - number of seconds since the epoch. The first time we saw a key for a given service.
	end = Column(Integer, nullable=False)	#another unix timestamp.  The most recent time we saw a key for a given service.

	__table_args__ = (
		UniqueConstraint('service_id', 'key', 'start'),
		UniqueConstraint('service_id', 'key', 'end'),
		CheckConstraint('start >= 0'),
		CheckConstraint('"end" >= 0'),
		CheckConstraint('start <= "end"'),
		)

	services = relationship("Services", backref=backref('t_observations', order_by=service_id))

	# add validation for individual fields, in case the database itself cannot.
	@validates('start')
	def validates_start(self, key, start):
		"""Validate the 'start' field when creating a new Observation."""
		if (start < 0):
			raise ValueError('Observation start time cannot be < 0 (attempted to use {0})'.format(start))
		return start

	@validates('end')
	def validates_end(self, key, end):
		"""Validate the 'end' field when creating a new Observation."""
		if (end < 0):
			raise ValueError('Observation end time cannot be < 0 (attempted to use {0})'.format(end))
		return end

	def validate(self):
		"""
		Check whether an Observation is a valid record that can be inserted in the database,
		and raise an exception if it is not.
		Keeping the code inside one function makes it easy to call from any insert or update methods.

		This function contains logic that cannot be run inside sqlalchemy @validates functions -
		either because it operates on multiple fields and requires the object to be completely instantiated,
		or for some other reason.
		"""
		if (self.end < self.start):
			raise ValueError('Observation end time must be >= start time (attempted to use start {0} and end {1})'.format(
				self.start, self.end))


# create indexes to speed up queries
Index('ix_services_name', Services.name)
Index('ix_observations_end', Observations.end)
Index('ix_observations_service_id_key_end', Observations.service_id, Observations.key, Observations.end)


class EventTypes(ORMBase):
	"""
	Various types of events we may be interested in tracking while a notary server runs.
	"""
	# see the ndb class and ndb.init_event_types()
	# for a list of possible event types
	__tablename__ = 't_event_types'
	event_type_id = Column(Integer, nullable=False, primary_key=True)
	name = Column(String, nullable=False, unique=True)

class Metrics(ORMBase):
	"""
	A log of interesting events that happen while a notary server runs. Mainly used for diagnostic or performance tracking.
	"""
	__tablename__ = 't_metrics'
	event_id = Column(Integer, nullable=False, primary_key=True)
	event_type_id = Column(Integer, ForeignKey('t_event_types.event_type_id'), nullable=False)
	date = Column(Integer, nullable=False) # unix timestamp - number of seconds since the epoch.
	comment = Column(String) # anything worth noting. do NOT track ip address or any private/personally identifiable information.

# purposely don't create any indexes on metrics tables -
# we want writing data to be as fast as possible.
# analysis can be done later on a copy of the data so it doesn't slow down the actual notary machine.


def ratelimited(max_per_second=1):
	"""
	Decorate a function, only allowing it to be called every so often.
	"""
	# we could make this available to other modules if it would be useful.

	min_interval = 1.0 / float(max_per_second)
	warn_every = 10 # seconds

	def decorate(func):
		last_called = [0.0]
		last_warned = [0.0]
		num_skips = [0]

		def rate_limited_function(*args, **kargs):
			curtime = time.clock()
			elapsed = curtime - last_called[0]
			left_to_wait = min_interval - elapsed

			if left_to_wait <= 0:
				# return the actual function so it can be called
				ret = func(*args, **kargs)
				last_called[0] = curtime

				# we want to note in the logs that some calls were skipped,
				# while not printing the log too often -
				# that would slow down the system and defeat the purpose of rate limiting.
				if ((curtime - last_warned[0] >= warn_every) and (num_skips[0] > 0)):
					logging.warning("Skipped %s calls to '%s()' in %s seconds." % (num_skips[0], func.__name__, warn_every))
					last_warned[0] = curtime
					num_skips[0] = 0
			else:
				# ignore the function call and continue
				ret = lambda: True
				num_skips[0] += 1
			return ret
		return rate_limited_function
	return decorate


class ndb(object):
	"""
	Notary database interface - create and interact with database tables.

	Currently this class is only intended to be called by modules that
	extend its argparser. i.e.

	parser = argparse.ArgumentParser(parents=[ndb.get_parser() ...])
	# ...
	args = parser.parse_args()
	ndb = ndb(args)
	"""

	# add more connection info here if you need that type of db
	# TODO: also supported: mysql, oracle, mssql, and firebird
	SUPPORTED_DBS = {'sqlite': {'defaultdbname': 'notary.sqlite',
								'defaultusername': '', #not used by sqlite
								'defaulthostname': '',
								'connstr': 'sqlite:///%s%s%s%s'},
					'postgresql': {'postgresql': 'perspectives-notary',
								'defaultusername': 'notaryrunner',
								'defaulthostname': 'localhost',
								'connstr': 'postgresql://%s:%s@%s/%s'}
					}
	DEFAULT_DB_TYPE = 'sqlite'
	DB_URL_FIELD = 'DATABASE_URL'
	DB_PASSWORD_FIELD = 'NOTARY_DB_PASSWORD'
	DEFAULT_ECHO = 0

	# store config in this directory,
	# so all modules that use the database can use it
	NOTARY_CONFIG_FILE = \
		os.path.join(os.path.dirname(os.path.realpath(__file__)), 'notary.db.config')
	CONFIG_SECTION = 'NotaryDB'

	EVENT_TYPE_NAMES = ['GetObservationsForService', 'ScanForNewService', 'ProbeLimitExceeded',
		'ServiceScanStart', 'ServiceScanStop', 'ServiceScanFailure', 'CacheHit', 'CacheMiss',
		'OnDemandServiceScanFailure', 'EventTypeUnknown']
	EVENT_TYPES = {}
	METRIC_PREFIX = "NOTARY_METRIC"

	# if the scanner does not run regularly and consistently,
	# blindly updating an observation's end time
	# could incorrectly fill in a large block of time
	# where we may have no proof that the key was seen.
	# thus put a cap on how far back we will alter data.

	# allowing updates within this window still allows the notary
	# to show a continual block of data, with some wiggle room for
	# the scan not running *exactly* every 24 hours
	# (e.g. the scan may start every 24 hours but sites may be updated in a random order)
	OBSERVATION_UPDATE_LIMIT = 60 * 60 * 48 # 2 days

	_conn_count_lock = threading.Lock()
	_open_connections = 0

	def __init__(self, args):
		"""
		Initialize a new ndb object.

		Some extra work is done here to make it easier for callers to import this module.
		"""

		# sanity/safety check:
		# filter the args and send only those that are relevant to __actual_init().
		# this makes it simple for callers that extend our argparser to use us
		# (i.e. by just calling 'ndb = ndb(args)')
		# but ensures we pass only the correct parameters,
		# so there are no errors.
		good_args = ndb.__filter_args(vars(args))

		if ('read_config_file' in good_args and good_args['read_config_file']):
			good_args = self._set_config_args()

		self.__actual_init(**good_args)

	# note: keep these arg names the same as the argparser args - see __filter_args()
	# we supply default values so everything can be passed as a named argument.
	def __actual_init(self, dburl=False,
						dbname=SUPPORTED_DBS[DEFAULT_DB_TYPE]['defaultdbname'],
						dbuser=SUPPORTED_DBS[DEFAULT_DB_TYPE]['defaultusername'],
						dbhost=SUPPORTED_DBS[DEFAULT_DB_TYPE]['defaulthostname'],
						dbtype=DEFAULT_DB_TYPE,
						dbecho=DEFAULT_ECHO,
						write_config_file=False, read_config_file=False,
						metricsdb=False, metricslog=False):
		"""
		Initialize a new ndb object.

		The actual initialization work is done here to hide the details
		of the extra steps we take inside __init__.
		"""

		connstr = ''
		self._Session = None
		self.metricsdb = metricsdb
		self.metricslog = metricslog

		if (dbecho):
			dbecho = True

		# TODO: ALL INPUT IS EVIL
		# regex check these variables
		if (dburl):
			try:
				connstr = os.environ[self.DB_URL_FIELD]
			except KeyError:
				raise KeyError("There is no environment variable named '%s'" % (self.DB_URL_FIELD))
		elif (dbtype in self.SUPPORTED_DBS):

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

			connstr = self.SUPPORTED_DBS[dbtype]['connstr'] % (dbuser, self.DB_PASSWORD, dbhost, dbname)

		else:
			errmsg = "'%s' is not a supported database type" % dbtype
			logging.error(errmsg)
			raise Exception(errmsg)

		# set up sqlalchemy objects
		self.db = create_engine(connstr, echo=dbecho)

		self._Session = scoped_session(sessionmaker(bind=self.db))

		# in most cases we expect callers to handle any exceptions that get thrown here.
		# we still want to make sure the error is logged, however.
		# for now we only check that (self._Session != None) in a few places that may be called accidentally,
		# since callers really shouldn't be calling methods if the database couldn't connect.
		# we could add more checks if that's warranted.
		try:
			ORMBase.metadata.create_all(self.db)
		except Exception as e:
			logging.error("Database error: '%s'. Could not connect to database! Please check your database status. " % (str(e)))
			if (self.DB_PASSWORD_FIELD not in os.environ):
				logging.error("The environment variable '{0}' does not exist. Did you mean to specify a database password?".format(self.DB_PASSWORD_FIELD))
			raise

		listen(Pool, 'checkout', self._on_connection_checkout)
		listen(Pool, 'checkin', self._on_connection_checkin)

		# cache data used when logging metrics
		self.__init_event_types()

		if (write_config_file):
			self._write_db_config(locals())


	def __init_event_types(self):
		"""Create entries in the EventTypes table, if necessary, and store their IDs in the EVENT_TYPES dictionary."""

		# if we're using metrics, caching these values now
		# saves us from having to look up the ID every time we insert a metric record.

		if self.is_metrics_enabled():
			with self.get_session() as session:
				for name in self.EVENT_TYPE_NAMES:
					try:
						evt = session.query(EventTypes).filter(EventTypes.name == name).first()

						if (evt == None):
							evt = EventTypes(name=name)
							session.add(evt)
							session.commit()

						self.EVENT_TYPES[name] = evt.event_type_id

					except ProgrammingError as e:
						logging.error("Error creating Event type '%s': '%s'." % (name, e))
						session.rollback()
						if (self.metricsdb):
							self.metricsdb = False
							logging.error("Cannot log performance metrics to a database without event types - metrics will be disabled.")
							break

	def __del__(self):
		"""Clean up any remaining database connections."""

		if (self.get_connection_count() != 0):
			logging.error("{0} database connections remain open! This may indicate a programming error - please use 'with ndb.get_session:' to manage your session scope.".format(
				self.get_connection_count()))

		if ((hasattr(self, '_Session')) and (self._Session != None)):
			try:
				self._Session.close_all()
				self._Session.remove()
				del self._Session
			except Exception as e:
				logging.error("Error closing database sessions in destructor: '%s'" % (e))

		if (hasattr(self, 'db')):
			self.db.dispose()
			del self.db

	@classmethod
	def get_parser(self):
		"""
		Get a parser object with the correct arguments for the ndb class.
		Can be used by calling modules that need to connect to a notary database to build their own parser on top.
		"""

		# IMPORTANT: For every switch here, add a named argument by the same name to __actual_init().
		# See __filter_args()for details.
		# Several other modules use us to connect to notary databases.
		# We let them access and extend our arg parser so we can keep the code in one place.
		# Note: do not use 'None' as a default for aguments: it interferes with _set_config_args().

		if __name__ == '__main__':
			parser = argparse.ArgumentParser(description=self.__doc__)
		else:
			# don't specify description or epilogue so the module that includes us can write their own.
			parser = argparse.ArgumentParser(add_help=False)
		dbgroup = parser.add_argument_group('optional database arguments')

		# dburl: unfortunately argparse doesn't make it easy to make one switch mutually exclusive from multiple other switches,
		# so we'll just document the behavior and enforce it in code.

		# if desired we could allow an optional parameter to pass in the name of the env var.
		# if so we should check it for valid characters; probably [A-Z_]
		dbgroup.add_argument('--dburl', action='store_true', default=False,
			help="Read database connection info from the environment variable '" + self.DB_URL_FIELD + "'.\
				If present this switch will override all other database connection switches. Default: \'%(default)s\'")
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
			help='Echo all SQL statements and other database messages to stdout. Not recommended for production use as this generates a lot of log data. If passed with no value echo defaults to true.')
		dbgroup.add_argument('--write-config-file', '--wcf', action='store_true', default=False,
			help='After successfully connecting, save all database arguments to a config file.')
		dbgroup.add_argument('--read-config-file', '--rcf', action='store_true', default=False,
			help='Load all database arguments from the config file. Arguments specified on the command line will override those found in the file.')
		metricgroup = parser.add_mutually_exclusive_group()
		metricgroup.add_argument('--metricsdb', '--dbmetrics', action='store_true', default=False,
			help="Track information about various notary events, to help diagnose performance and health, and save info in the notary database.\
			 See docs/metrics.txt for a detailed explanation. Default: \'%(default)s\'")
		metricgroup.add_argument('--metricslog', '--logmetrics', action='store_true', default=False,
			help="Track information about various notary events, and print info to stdout with the prefix '" + self.METRIC_PREFIX + "'. \
			 See docs/metrics.txt for a detailed explanation. Default: \'%(default)s\'")

		return parser

	@classmethod
	def __filter_args(self, argsdict):
		"""
		Filter a dictionary of arguments and return only ones that are applicable to ndb.

		The ndb class is instantiated from many different places,
		many of which extend the ndb argparser.
		If the ndb argparser changes (e.g. a future version adds a new argument)
		it is annoying and too much work to update all of the calls to ndb.__init__().
		Thus we use this function internally to filter incoming args
		and make sure that only the parameters applicable to ndb are used.
		"""
		valid_args = ndb.__actual_init.func_code.co_varnames[:ndb.__actual_init.func_code.co_argcount]
		d = dict((key, val) for key, val in argsdict.iteritems() if key in valid_args)

		if 'self' in d:
			del d['self']

		return d

	def _write_db_config(self, args):
		"""Write all ndb args to the config file."""

		good_args = ndb.__filter_args(args)

		# don't store keys related to config actions
		del good_args['write_config_file']
		del args['read_config_file']

		# print a header to make file purpose clear
		with open(self.NOTARY_CONFIG_FILE, 'w') as f:
			print("# Network notary database configuration settings -", file=f)
			print("# for easy sharing of db configs between tools.", file=f)
			print("# Run `python notary_http.py --help` for more info.\n", file=f)

		config = ConfigParser.SafeConfigParser()
		config.add_section(self.CONFIG_SECTION)
		for k, v in good_args.iteritems():
			config.set(self.CONFIG_SECTION, k, str(v))

		with open(self.NOTARY_CONFIG_FILE, 'a') as configfile:
			config.write(configfile)

		print("Notary database config saved in %s." % self.NOTARY_CONFIG_FILE)

	def _read_db_config(self):
		"""Read ndb args from the config file and return as a list."""

		config = ConfigParser.SafeConfigParser()
		config.read(self.NOTARY_CONFIG_FILE)
		try:
			items = config.items(self.CONFIG_SECTION)
			return items
		except ConfigParser.NoSectionError:
			logging.error("Could not read config file. Please write one with --write-config-file before reading")
			return ()

	def _set_config_args(self):
		"""Sanitize and set up ndb arguments read from a config file."""

		print("Reading config data from %s." % self.NOTARY_CONFIG_FILE)
		temp_args = self._read_db_config()
		good_args = {}


		# remember: ALL INPUT IS EVIL!
		# do some safety checking on config file arguments,
		# as well as basic type identification
		# before we try to use them for anything.

		valid_key = re.compile("^\w+$")
		none = re.compile("^None$")
		true = re.compile("^True$")
		false = re.compile("^False$")
		valid_int = re.compile("^\d+$")

		for k, v in temp_args:
			if (valid_key.match(k)):
				key = str(valid_key.match(k).group(0))

				if (none.match(v)):
					value = None
				elif (true.match(v)):
					value = True
				elif (false.match(v)):
					value = False
				elif (valid_int.match(v)):
					value = int(valid_int.match(v).group(0))
				else:
					value = str(v)

				good_args[key] = value


		# make command line args override config file args:
		# we need a way to differentiate switches passed on the command line
		# from those that were simply assigned their defaults.
		# thus: get a dict of all the possible arg names
		possible_args = vars(ndb.get_parser().parse_args(list()))

		# and set all of the values to None
		for key in possible_args:
			possible_args[key] = None

		# now create a new parser and forcibly set all of the defaults to None.
		noneparser = ndb.get_parser()
		noneparser.set_defaults(**possible_args)

		# calling parse_args() will now use None for the defaults
		# instead of the regular defaults,
		# so we can tell the difference between arguments using default values
		# and arguments that have been specified on the command line.
		cl_args = vars(noneparser.parse_args())

		for key in cl_args:
			if (cl_args[key] != None):
				good_args[key] = cl_args[key]

		return good_args

	@contextmanager
	def get_session(self):
		"""
		Open a session with the database. *ALL* callers should use this to create new sessions,
		and use a 'with' statement to make sure the session is properly closed afterward.

		For example:

			with self.ndb.get_session() as session:
				database_obs = self.ndb.foo(session)
				#... do some work here with database objects

			#continue with rest of non-database code.

		Every function that returns database records requires a session as a function parameter.
		Create one as above and pass it in, so sessions can be properly scoped and managed.

		Do not access the session object directly.
		Do not try to close your own session.
		Let the ndb's contextmanager handle session closing.

		Any database changes that are partially completed but not committed will be rolled back
		if an exception is raised.
		"""
		session = self._Session()
		try:
			yield session
		except:
			session.rollback()
			raise
		finally:
			session.close()


	def _on_connection_checkout(self, dbapi_connection, connection_record, connection_proxy):
		"""Count when a connection is checked out of the connection pool."""
		with self._conn_count_lock:
			self._open_connections += 1

	def _on_connection_checkin(self, dbapi_connection, connection_record):
		"""Count when a connection is checked back in to the connection pool."""
		with self._conn_count_lock:
			self._open_connections -= 1

	def get_connection_count(self):
		"""Return the count of open database connections."""
		return self._open_connections

	@contextmanager
	def _get_connection(self):
		"""
		Open a raw connection with the database using the SQLAlchemy core, rather than the ORM.
		Queries that are read-only or do not manipulate any records
		may be much faster using this type of connection,
		as raw connections avoid the overhead of ORM objects.
		"""
		conn = self.db.connect()
		try:
			yield conn
		finally:
			conn.close()


	# actual data methods follow

	def count_services(self):
		"""Return a count of the service records."""
		with self._get_connection() as conn:
			return conn.execute(select([func.count(Services.service_id)])).first()[0]

	def get_all_service_names(self):
		"""Get all service names."""
		# use raw SQL mode so we don't incur the extra overhead of ORM objects.
		# the results of this function are not being updated; only read
		with self._get_connection() as conn:
			# TODO: could do a windowed amount if too big
			return conn.execute(select([Services.name])).fetchall()

	def get_newest_service_names(self, end_limit):
		"""Get service names with an observation newer than end_limit."""
		with self._get_connection() as conn:
			return self._get_newest_service_names(conn, end_limit)

	def _get_newest_service_names(self, conn, end_limit):
		"""Get service names with an observation newer than end_limit."""
		# internal function so we don't have to open a separate database connection
		return conn.execute(select([Services.name]).where(\
				and_(Services.service_id == Observations.service_id,\
				Observations.end > end_limit\
				))).fetchall()

	def get_oldest_service_names(self, end_limit):
		"""Get service names with a MOST RECENT observation that is older than end_limit."""
		with self._get_connection() as conn:
			return conn.execute(select([Services.name]).where(\
				and_(Services.service_id == Observations.service_id,\
				~Services.name.in_(self._get_newest_service_names(conn, end_limit))\
				))).fetchall()

	def insert_service(self, session, service_name):
		"""Add a new Service to the database, and return the Service object."""
		#TODO: could overload to also have insert services and return nothing, not requiring a session.
		srv = session.query(Services).filter(Services.name == service_name).first()

		if (srv == None):
			srv = Services(name=service_name)
			try:
				session.add(srv)
				session.commit()
			except (ProgrammingError, IntegrityError, OperationalError) as e:
				logging.error("Error inserting service '%s': '%s'" % (service_name, e))
				srv = None

		return srv

	def insert_bulk_services(self, services):
		"""
		Add multiple Services to the database at once.
		This is much faster than adding them one record at a time.

		'services': a list of service names.
		"""
		if len(services) < 1:
			logging.error("Could not add services - no services in list.")
			return

		with self._get_connection() as conn:
			try:
				# select duplicates that already exist in the database
				dupes = conn.execute(select([Services.name], Services.name.in_(services))).fetchall()

				# convert dupes to dictionary so we can easily test against them
				dupes_dict = dict((dup[0], True) for dup in dupes)

				# remove any entries that already exist in the database
				# so that inserting bulk records doesn't throw an IntegrityError.
				# At the same time, modify entries to be dictionaries
				# with the correct key/value mapping to be used in a bulk insert.
				# doing this at the same time saves us from looping through the list twice.
				services = [{'name': service_name} for service_name in services
					if service_name not in dupes_dict]

				# any services left in the list will be new entries
				if (len(services)) > 0:
					conn.execute(Services.__table__.insert(), services)

			except IntegrityError as e:
				logging.error("Error adding bulk services: '{0}'".format(e))

		return

	#######
	def count_observations(self):
		"""Return a count of the observation records."""
		with self._get_connection() as conn:
			return conn.execute(select([func.count(Observations.observation_id)])).first()[0]

	def get_all_observations(self, session):
		"""Get all observations in the database."""
		return session.query(Services).join(Observations).\
			order_by(Services.name).\
			values(Services.name, Observations.key, Observations.start, Observations.end)

	def get_observations(self, session, service):
		"""Get all observations for a given service."""
		try:
			return session.query(Services).join(Observations).\
				filter(Services.name == service).\
				values(Services.name, Observations.key, Observations.start, Observations.end)
		except Exception as e:
			logging.error("Error getting observations: '%s'" % (e))
			# re-raise the error so the caller definitely knows something bad happened,
			# as opposed to there being no observation records
			raise

	def _insert_observation(self, service, key, start_time, end_time):
		"""Insert a new Observation about a service/key pair."""
		with self.get_session() as session:
			srv = self.insert_service(session, service)
			if (srv != None):
				try:
					newob = Observations(service_id=srv.service_id, key=key, start=start_time, end=end_time)
					newob.validate()
					session.add(newob)
					session.commit()
				except (ProgrammingError, IntegrityError, OperationalError, ValueError) as e:
					logging.error("Error committing observation on key '%s' for service '%s': '%s'" % (key, service, e))
			# else error already logged by previous function

	def _update_observation_end_time(self, service, fp, old_end_time, new_end_time):
		"""
		Update the end time for a given Observation.
		External callers shouldn't use this - call report_observation() instead.
		"""
		curtime = int(time.time())

		if (new_end_time == None):
			new_end_time = curtime
		if (old_end_time == None):
			old_end_time = curtime

		try:
			with self.get_session() as session:
				ob = session.query(Observations).join(Services)\
					.filter(Services.name == service)\
					.filter(Observations.key == fp)\
					.filter(Observations.end == old_end_time).first()
				if (ob != None):
					if (new_end_time <= ob.end):
						raise ValueError('New end time must be > current end time. (attempted to use new end time {0})'.format(
							new_end_time))
					ob.validate()
					ob.end = new_end_time
					session.commit()
				else:
					logging.error("Attempted to update the end time for service '%s' key '%s',\
						but no records for it were found! This is really bad; code shouldn't be here." % (service, fp))
		except (OperationalError, ValueError) as e:
			logging.error("Error committing observation on key '%s' for service '%s': '%s'" % (fp, service, e))

	def report_observation(self, service, fp):
		"""
		Insert or update an Observation record.
		All callers should use this instead of calling _insert or _update directly,
		to ensure entries are valid.
		"""

		cur_time = int(time.time())
		most_recent_time_by_key = {}
		most_recent_key = None
		most_recent_time = 0

		try:
			with self.get_session() as session:
				obs = self.get_observations(session, service)

				# calculate the most recently seen key
				# TODO: there has got to be a more efficient way to do this with a query
				for (service, key, start, end) in obs:
					if key not in most_recent_time_by_key or end > most_recent_time_by_key[key]:
						most_recent_time_by_key[key] = end

					for k in most_recent_time_by_key:
						if most_recent_time_by_key[k] > most_recent_time:
							most_recent_key = k
							most_recent_time = most_recent_time_by_key[k]
		except Exception as e:
			# error already reported by get_observations()
			return

		if most_recent_key == fp: # "fingerprint"
			# this key matches the most recently seen key before this observation.
			# just update the observation 'end' time.
			if ((cur_time - most_recent_time) <= self.OBSERVATION_UPDATE_LIMIT):
				self._update_observation_end_time(service, fp, most_recent_time, cur_time)
			else:
				# too many days have passed. don't update this observation -
				# that could fill in a LOT of data we haven't observed.
				# instead just create a new record.
				self._insert_observation(service, fp, cur_time, cur_time)
		else:
			# the key has changed or no observations exist yet for this service.
			# add a new entry for this key with start and end set to the current time
			self._insert_observation(service, fp, cur_time, cur_time)
			if ((most_recent_key != None) and ((cur_time - most_recent_time) <= self.OBSERVATION_UPDATE_LIMIT)):
				# if there was a previous key that ended within the time cutoff, update its end time.
				self._update_observation_end_time(service, most_recent_key, most_recent_time, cur_time - 1)

	def is_metrics_enabled(self):
		"""Retun true if the metrics tracking system is currently running, false otherwise."""
		if (self.metricsdb or self.metricslog):
			return True
		return False

	# rate limit metrics so spamming queries doesn't take down the system.
	# TODO: we could group metrics up to report in one big transaction, or use a background worker
	@ratelimited(1)
	def report_metric(self, event_type, comment=""):
		"""Record a metric event in the database or the log."""
		if self.is_metrics_enabled():
			if (event_type not in self.EVENT_TYPES):
				logging.error("Unknown event type '%s'. Please check your call to report_metric()." % event_type)
				self.report_metric('EventTypeUnknown', str(event_type) + "|" + str(comment))
			else:
				if (self.metricsdb):
					# wrap metric write attempts in a try/catch block so errors don't bring down the server
					try:
						with self.get_session() as session:
							metric = Metrics(event_type_id=self.EVENT_TYPES[event_type],\
								date=int(time.time()), comment=str(comment))
							session.add(metric)
							session.commit()
					except (ProgrammingError, OperationalError, ResourceClosedError, AttributeError) as e:
						# ResourceClosedError can happen when the database is under heavy load
						logging.error("Error committing metric: '%s'. Was trying to log the following metric: %s %s " % 
							e, event_type, comment)
				else:
					self.__print_metric(event_type, comment)

	def __print_metric(self, event_type, comment):
		"""Print metric to stdout. External callers should use report_metric() instead."""
		print("%s|%s|%s|%s" % (self.METRIC_PREFIX, event_type, int(time.time()), str(comment)))

if __name__ == "__main__":
	args = ndb.get_parser().parse_args()
