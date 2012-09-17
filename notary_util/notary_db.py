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

import argparse
import os
import platform
import re
import sys
import time
import ConfigParser

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.engine import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, relationship, backref
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


class EventTypes(ORMBase):
	"""
	Various types of events we may be interested in tracking while a notary server runs.
	"""
	# see the ndb class and ndb.init_event_types()
	# for a list of possible event types
	__tablename__ = 't_event_types'
	event_type_id = Column(Integer, primary_key=True)
	name = Column(String, nullable=False, unique=True)

class Metrics(ORMBase):
	"""
	A log of interesting events that happen while a notary server runs. Mainly used for diagnostic or performance tracking.
	"""
	__tablename__ = 't_metrics'
	event_id = Column(Integer, primary_key=True)
	event_type_id = Column(Integer, ForeignKey('t_event_types.event_type_id'))
	machine_id = Column(Integer, ForeignKey('t_machines.machine_id'))
	date = Column(Integer) # unix timestamp - number of seconds since the epoch.
	comment = Column(String) # anything worth noting. do NOT track ip address or any private/personally identifiable information.

# purposely don't create any indexes on metrics tables -
# we want writing data to be as fast as possible.
# analysis can be done later on a copy of the data so it doesn't slow down the actual notary machine.

class Machines(ORMBase):
	"""
	Computers that run notary software.
	"""
	__tablename__ = 't_machines'
	machine_id = Column(Integer, primary_key=True)
	name = Column(String)



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

	EVENT_TYPE_NAMES=['GetObservationsForService', 'ScanForNewService', 'ProbeLimitExceeded',
		'ServiceScanStart', 'ServiceScanStop', 'ServiceScanKeyUpdated',
		'ServiceScanPrevKeyUpdated', 'ServiceScanFailure', 'CacheHit', 'CacheMiss',
		'OnDemandServiceScanFailure', 'EventTypeUnknown']
	EVENT_TYPES={}
	MACHINES={}
	METRIC_PREFIX = "NOTARY_METRIC"

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

		if (good_args['read_config_file']):
			good_args = self.set_config_args()

		self.__actual_init__(**good_args)

	# note: keep these arg names the same as the argparser args - see filter_args()
	# we supply default values so everything can be passed as a named argument.
	def __actual_init__(self, dburl=False,
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

		# TODO: ALL INPUT IS EVIL
		# regex check these variables
		if (dburl):
			connstr = os.environ[self.DB_URL_FIELD]
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
			print >> sys.stderr, errmsg
			raise Exception(errmsg)

		if (dbecho):
			dbecho = True

		# set up sqlalchemy objects
		self.db = create_engine(connstr, echo=dbecho)
		ORMBase.metadata.create_all(self.db)
		self.Session = scoped_session(sessionmaker(bind=self.db))
		self.__init_event_types__()
		self.metricsdb = metricsdb
		self.metricslog = metricslog

		# cache the machine name for logging metrics
		self.__init_machine_names__()

		if (write_config_file):
			self.write_db_config(locals())


	def __init_event_types__(self):
		"""Create entries in the EventTypes table, if necessary, and store their IDs in the EVENT_TYPES dictionary."""

		# if we're using metrics, caching these values now
		# saves us from having to look up the ID every time we insert a metric record.

		# __init__ happens in its own thread, so create and remove a local Session
		session = self.Session()
		for name in self.EVENT_TYPE_NAMES:
			try:
				evt = session.query(EventTypes).filter(EventTypes.name == name).first()

				if (evt == None):
					evt = EventTypes(name = name)
					session.add(evt)
					session.commit()

				self.EVENT_TYPES[name] = evt.event_type_id

			except Exception, e:
				print >> sys.stderr, "Error creating Event type '%s': '%s'" % (name, e)
				session.rollback()
		self.Session.remove()

	def __init_machine_names__(self):
		"""Create entries in the Machines table, if necessary, and store their IDs in the MACHINES dictionary."""

		machine_name = platform.node()
		self.machine_name = machine_name

		# if we're using metrics, caching these values now
		# saves us from having to look up the ID every time we insert a metric record.

		# __init__ happens in its own thread, so create and remove a local Session
		session = self.Session()
		try:
			machine = session.query(Machines).filter(Machines.name == machine_name).first()

			if (machine == None):
				machine = Machines(name = machine_name)
				session.add(machine)
				session.commit()

			self.MACHINES[machine_name] = machine.machine_id

		except Exception, e:
			print >> sys.stderr, "Error creating Machine name '%s': '%s'" % (machine_name, e)
			session.rollback()

		self.Session.remove()

	def __del__(self):
		"""Clean up any remaining database connections."""

		if ((hasattr(self, 'Session')) and (self.Session != None)):
			try:
				self.Session.close_all()
				self.Session.remove()
				del self.Session
			except Exception, e:
				print >> sys.stderr, "Error closing database connection: '%s'" % (e)

		self.db.dispose()
		del self.db

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
			help='Echo all SQL statements and other database messages to stdout. If passed with no value echo defaults to true.')
		dbgroup.add_argument('--write-config-file', '--wcf', action='store_true', default=False,
			help='After successfully connecting, save all database arguments to a config file.')
		dbgroup.add_argument('--read-config-file', '--rcf', action='store_true', default=False,
			help='Load all database arguments from the config file. Arguments specified on the command line will override those found in the file.')
		metricgroup = parser.add_mutually_exclusive_group()
		metricgroup.add_argument('--metricsdb', action='store_true', default=False,
			help="Track information about various notary events, to help diagnose performance and health, and save info in the notary database.\
			 See docs/metrics.txt for a detailed explanation. Default: \'%(default)s\'")
		metricgroup.add_argument('--metricslog', action='store_true', default=False,
			help="Track information about various notary events, and print info to stdout with the prefix '" + self.METRIC_PREFIX + "'. \
			 See docs/metrics.txt for a detailed explanation. Default: \'%(default)s\'")

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

	def write_db_config(self, args):
		"""Write all ndb args to the config file."""

		good_args = ndb.filter_args(args)

		# don't store keys related to config actions
		del good_args['write_config_file']
		del args['read_config_file']

		# print a header to make file purpose clear
		with open(self.NOTARY_CONFIG_FILE, 'w') as f:
			print >> f, "# Network notary database configuration settings -"
			print >> f, "# for easy sharing of db configs between tools."
			print >> f, "# Run `python notary_http.py --help` for more info.\n"

		config = ConfigParser.SafeConfigParser()
		config.add_section(self.CONFIG_SECTION)
		for k, v in good_args.iteritems():
			config.set(self.CONFIG_SECTION, k, str(v))

		with open(self.NOTARY_CONFIG_FILE, 'a') as configfile:
			config.write(configfile)

		print "Notary database config saved in %s." % self.NOTARY_CONFIG_FILE

	def read_db_config(self):
		"""Read ndb args from the config file and return as a list."""

		config = ConfigParser.SafeConfigParser()
		config.read(self.NOTARY_CONFIG_FILE)
		try:
			items = config.items(self.CONFIG_SECTION)
			return items
		except ConfigParser.NoSectionError:
			print >> sys.stderr, "Could not read config file. Please write one with --write-config-file before reading"
			return ()

	def set_config_args(self):
		"""Sanitize and set up ndb arguments read from a config file."""

		print "Reading config data from %s." % self.NOTARY_CONFIG_FILE
		temp_args = self.read_db_config()
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

	def close_session(self):
		"""
		Clean up the session after any caller is done using results.
		Call this after any SQL method to make sure database connections are not left open.
		"""
		if ((hasattr(self, 'Session')) and (self.Session != None)):
			try:
				self.Session.remove()
			except Exception as e:
				print >> sys.stderr, "Error closing database connection: '%s'" % (e)


	# actual data methods follow

	def get_all_services(self):
		"""Get all service names."""
		return self.Session().query(Services.name).all()

	def get_newest_services(self, end_limit):
		"""Get service names with an observation newer than end_limit."""
		return self.Session().query(Services.name).join(Observations).\
			filter(Observations.end > end_limit)

	def get_oldest_services(self, end_limit):
		"""Get service names with a MOST RECENT observation that is older than end_limit."""
		return self.Session().query(Services).join(Observations).filter(\
			~Services.name.in_(\
				self.get_newest_services(end_limit))).\
			values(Services.name)

	def insert_service(self, service_name):
		"""Add a new Service to the database."""
		# if this is too slow we could add bulk insertion
		session = self.Session()
		srv = session.query(Services).filter(Services.name == service_name).first()

		if (srv == None):
			srv = Services(name = service_name)
			session.add(srv)
			session.commit()

		return srv

	def get_all_observations(self):
		"""Get all observations."""
		return self.Session().query(Services).join(Observations).\
			order_by(Services.name).\
			values(Services.name, Observations.key, Observations.start, Observations.end)

	def get_observations(self, service):
		"""Get all observations for a given service."""
		return self.Session().query(Services).join(Observations).\
			filter(Services.name == service).\
			values(Services.name, Observations.key, Observations.start, Observations.end)

	def insert_observation(self, service, key, start_time, end_time):
		"""Insert a new Observation about a service/key pair."""
		srv = self.insert_service(service)

		try:
			session = self.Session()
			newob = Observations(service_id=srv.service_id, key=key, start=start_time, end=end_time)
			session.add(newob)
			session.commit()
		except IntegrityError:
			print >> sys.stderr, "IntegrityError: Observation for (%s, %s) already present. If you want to update it call that function instead. Ignoring." % (service, key)
			session.rollback()
		finally:
			self.Session.remove()

	def update_observation_end_time(self, service, fp, old_end_time, new_end_time):
		"""Update the end time for a given Observation."""
		curtime = int(time.time())

		if (new_end_time == None):
			new_end_time = curtime
		if (old_end_time == None):
			old_end_time = curtime

		session = self.Session()
		ob = session.query(Observations).join(Services)\
			.filter(Services.name == service)\
			.filter(Observations.key == fp)\
			.filter(Observations.end == old_end_time).first()
		if (ob != None):
			ob.end = new_end_time
			session.commit()
		else:
			print >> sys.stderr, "Attempted to update the end time for service '%s' key '%s',\
				but no records for it were found! This is really bad; code shouldn't be here." % (service, fp)
		self.Session.remove()

	def report_metric(self, event_type, comment=""):
		"""Add a metric event to the metrics table."""
		if (self.metricsdb or self.metricslog):
			if (event_type not in self.EVENT_TYPES):
				print >> sys.stderr, "Unknown event type '%s'. Please check your call to report_metric()." % event_type
				self.report_metric('EventTypeUnknown', str(event_type) + "|" + str(comment))
			else:
				if (self.metricsdb):
					# note: if we need even more speed we could try spawing this on its own thread
					session = self.Session()
					try:
						metric = Metrics(event_type_id=self.EVENT_TYPES[event_type], machine_id=self.MACHINES[self.machine_name],\
							date=int(time.time()), comment=str(comment))
						session.add(metric)
						session.commit()
					except Exception, e:
						print >> sys.stderr, "Error committing metric: '%s'" % e
						session.rollback()
					finally:
						self.Session.remove()
				elif (self.metricslog):
					print "|%s|%s|%s|%s|%s" % (self.METRIC_PREFIX, self.machine_name, event_type, int(time.time()), str(comment))
