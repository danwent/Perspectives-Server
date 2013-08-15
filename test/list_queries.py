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
Print all possible notary SQL statements to a file.

Test script to help enumerate and evaluate notary SQL.

We want to make sure the SQL used by every query is efficient.
Enumerating all of the queries used by the server helps us examine them
so we can tell if they are running efficiently
(even if they are just examined with an 'explain query plan' or equivalent).
You can use the output of this script to evaluate SQL efficiency.

If you add a function to the ndb class please add a test case for it here.
"""

import logging
import unittest

# TODO: HACK
# add ..\notary_util to the import path so we can import ndb
import sys
import os
sys.path.insert(0,
	os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from notary_util.notary_db import ndb



class NotarySQLEnumeration(unittest.TestCase):
	"""
	Call all notary database functions to print their SQL.
	"""

	TEST_DATABASE = os.path.join(os.path.dirname(os.path.realpath(__file__)),
		'notary.sql_performance_test.slqite')
	LOG_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)),
		'notary_statements.sql')
	SQL_LOG_CHANNEL = 'sqlalchemy.engine'

	test_case_count = 0

	def __init__(self, args):

		# call base class's init to finish setup
		unittest.TestCase.__init__(self, args)

		# disable SQL logging before the database has been created.
		# this prevents logging info on table schemas and other startup info.
		logging.getLogger('sqlalchemy.engine').setLevel(logging.CRITICAL)

		# set up the database once for all tests
		# TODO: refactor ndb so we can pass a blank set of args
		# or a simple dictionary like {'dbecho':True, 'dbname':self.TEST_DATABASE})
		# argparse objects don't like being compared to None.
		args = ndb.get_parser().parse_args()
		args.dbname = self.TEST_DATABASE
		self.ndb = ndb(args)

		# now turn on sqlalchemy logging.
		# do not use the 'dbecho' flag, so we can control the formatting ourselves
		# and avoid duplicate logs. see the sqlalchemy docs for details -
		# http://docs.sqlalchemy.org/en/rel_0_8/core/engines.html#dbengine-logging 

		# format logging to print only SQL with no other info
		# (e.g. remove the timestamp and logging level)
		logging.basicConfig(format="\n>>>>>>>\n%(message)s\n<<<<<<<\n",
			filename=self.LOG_FILE, filemode='w')
		logging.getLogger(self.SQL_LOG_CHANNEL).setLevel(logging.INFO)

	def __del__(self):
		self.ndb.close_session()
		del self.ndb

	def setUp(self):
		# number each statement
		NotarySQLEnumeration.test_case_count += 1
		logging.getLogger(self.SQL_LOG_CHANNEL).info(
			"SQL Statement {0} - {1}".format(NotarySQLEnumeration.test_case_count,
			self.id()))

	def tearDown(self):
		self.ndb.close_session()
		self.assertTrue(self.ndb.get_connection_count() == 0)

	#######

	# important SQL: used frequently by the main app
	def test_get_all_services(self):
		self.ndb.get_all_services()

	def test_get_newest_services(self):
		self.ndb.get_newest_services(0)

	def test_get_oldest_services(self):
		self.ndb.get_oldest_services(0)

	def test_report_metric(self):
		self.ndb.report_metric('CacheHit')

	def test_insert_service(self):
		self.ndb.insert_service('insert_service_test:443,2')

	def test_get_observations(self):
		# TODO: can we profile this even with no obs in the db?
		self.ndb.get_observations('get_obs_test:443,2')

	def test_insert_observation(self):
		self.ndb.insert_observation('insert_obs_test:443,2', 'aa:bb', 1, 2)

	def test_update_observation_end_time(self):
		# insert the service and observation first to make sure we get no errors
		srv = 'update_obs_end_time_test:443,2'
		key = 'aa:bb'
		end_time = 2

		self.ndb.insert_service(srv)
		self.ndb.insert_observation(srv, key, end_time - 1, end_time)
		self.ndb._update_observation_end_time(srv, key, end_time, end_time + 1)

	def test_report_observation(self):
		self.ndb.report_observation('report_observation_test:443,2', 'aa:bb')

	# less important SQL - used less often or in the background
	def test_count_services(self):
		self.ndb.count_services()

	def test_count_observations(self):
		self.ndb.count_observations()

	def test_get_all_observations(self):
		self.ndb.get_all_observations()

	def test_insert_bulk_services(self):
		self.ndb.insert_bulk_services(
			['bulkinserttest:443,2', 'bulkinserttest_2:443,2', 'bulkinserttest_3:443,2'])


if __name__ == '__main__':

	if (os.path.exists(NotarySQLEnumeration.TEST_DATABASE) and (os.path.isfile(NotarySQLEnumeration.TEST_DATABASE))):
		try:
			print "Deleting test database file {0}".format(NotarySQLEnumeration.TEST_DATABASE)
			os.remove(NotarySQLEnumeration.TEST_DATABASE)
		except (Exception) as e:
			print >> sys.stderr, "Error deleting test database: '{0}'. WARNING - tests may not run properly.".format(e)

	test_suite = unittest.TestLoader().loadTestsFromTestCase(NotarySQLEnumeration)
	unittest.main(verbosity=2)

	print "SQL statements output to '{0}'.".format(NotarySQLEnumeration.LOG_FILE)
