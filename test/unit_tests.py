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
Run a suite of automated unit tests against the Perspectives notary server code.
Feel free to add tests!

You may see error messages printed to stderr, but that should be evidence of code properly handling errors.
"""

import argparse
import logging
import time
import unittest

# TODO: HACK
# add ..\notary_util to the import path so we can import ndb
import sys
import os
sys.path.insert(0,
	os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from notary_util.notary_db import ndb
from util import pycache


class PyCacheTestCases(unittest.TestCase):
	"""Test the pycache module."""

	#TODO: add test cases for underlying logic and classes. e.g. the Heap class.

	def setUp(self):
		"""Make sure the cache is fresh or was cleared after the last test."""
		self.cache = pycache
		self.assertTrue(self.cache.get_cache_size() == 0)
		self.assertTrue(self.cache.get_cache_count() == 0)

	def tearDown(self):
		"""
		Clear the cache before the next test.
		(this is needed because pycache is a module)
		"""
		self.cache.clear()
		self.assertTrue(self.cache.get_cache_size() == 0)
		self.assertTrue(self.cache.get_cache_count() == 0)

	def set_key(self, key, value, expiry):
		"""Helper function."""
		self.cache.set(key, value, expiry)

	def test_added_key_uses_memory(self):
		self.cache.set_cache_size(1024)
		mem_before = self.cache.get_cache_size()
		count_before = self.cache.get_cache_count()

		self.set_key('use_mem_key', 'some test value', 100)

		mem_after = self.cache.get_cache_size()
		count_after = self.cache.get_cache_count()
		self.assertTrue(mem_after > mem_before)
		self.assertTrue(count_after > count_before)

	def test_adding_multiple_keys_uses_increasing_memory(self):
		max_mem = 1024
		self.cache.set_cache_size(max_mem * 2)
		name = 'a'

		cur_mem = 0
		prev_mem = 0
		count = 0

		while (self.cache.get_cache_size() <= max_mem):
			self.assertTrue(count == self.cache.get_cache_count())
			self.set_key(name, 'some test value', 100)
			self.assertTrue(self.cache.get_cache_size() > prev_mem)

			prev_mem = cur_mem
			cur_mem = self.cache.get_cache_size()
			count += 1
			name += 'a'

		self.assertTrue(count == self.cache.get_cache_count())
		self.assertTrue(cur_mem > max_mem)

	def test_non_positive_expiry_not_stored(self):
		self.assertRaises(ValueError, self.set_key, 'neg_expiry', 'aaaaaaa', -1)
		self.assertRaises(ValueError, self.set_key, 'neg_expiry', 'aaaaaaa', 0)

	def test_non_scalar_expiry_times(self):
		# passing non-integers should fail
		self.assertRaises(TypeError, self.set_key, ['neg_expiry', 'aaaaaaa', 100])
		self.assertRaises(TypeError, self.set_key, {'some key': 'value'})

	def test_huge_key_not_stored(self):
		"""Entries larger than the cache itself should not be stored."""
		self.cache.set_cache_size(1) # byte
		mem_before = self.cache.get_cache_size()
		count_before = self.cache.get_cache_count()

		self.cache.set('huge_key', 'a bigger string than 1 byte of memory', 100)

		mem_after = self.cache.get_cache_size()
		count_after = self.cache.get_cache_count()
		self.assertTrue(mem_after == mem_before == 0)
		self.assertTrue(count_after == count_before == 0)

	def test_entry_removed_after_expiry(self):
		self.cache.set_cache_size(1024)
		key = 'test_key'
		expiry = 1 #second
		self.set_key(key, 'val', expiry)
		time.sleep(expiry * 2)
		value = self.cache.get(key)
		self.assertTrue(value == None)



class NotaryDBTestCases(unittest.TestCase):
	"""
	Test notary database functions.

	All functions should be called, even functions that do not have explicit test conditions.
	We want to make sure they don't raise any exceptions.
	"""

	TEST_DATABASE = os.path.join(os.path.dirname(os.path.realpath(__file__)),
		'notary.unit_test.slqite')

	def __init__(self, args):

		# call base class's init to finish setup
		unittest.TestCase.__init__(self, args)

		# set up the database once for all tests
		# TODO: refactor ndb so we can pass a blank set of args
		# or a simple dictionary like {'dbecho':True, 'dbname':self.TEST_DATABASE})
		# argparse objects don't like being compared to None.
		args = ndb.get_parser().parse_args()
		args.dbname = self.TEST_DATABASE
		args.metricsdb = True
		self.ndb = ndb(args)

	def __del__(self):
		if (hasattr(self, 'ndb')):
			self.ndb.close_session()
			del self.ndb

	def tearDown(self):
		# do *not* call close_session() here -
		# that would hide errors if a function is being used incorrectly.
		# each test should know whether or not it needs to close the session afterward.
		# test the connection count to catch any improper usage.
		self.assertTrue(self.ndb.get_connection_count() == 0)

	#######

	# important SQL: used frequently by the main app
	def test_get_all_services(self):
		self.ndb.get_all_services()
		self.ndb.close_session()

	def test_get_newest_services(self):
		self.ndb.get_newest_services(0)
		self.ndb.close_session()

	def test_get_oldest_services(self):
		self.ndb.get_oldest_services(0)
		self.ndb.close_session()

	def test_report_metric(self):
		self.ndb.report_metric('CacheHit')
		self.ndb.report_metric('SomeEventNotInTheDatabase')

	def test_insert_service(self):
		service = 'insert_service_test:443,2'

		count_srv_before = self.ndb.count_services()
		self.ndb.insert_service(service)
		self.assertTrue(self.ndb.count_services() == (count_srv_before + 1))

		# inserting a service that already exists should be ignored
		count_srv_before = self.ndb.count_services()
		self.ndb.insert_service(service)
		self.assertTrue(self.ndb.count_services() == count_srv_before)

		# null values should be ignored
		self.ndb.insert_service(None)

	def test_get_observations(self):
		self.ndb.get_observations('get_obs_test:443,2')
		self.ndb.close_session()

	def test_insert_observation(self):
		service = 'insert_obs_test:443,2'
		key = 'aa:bb'
		base_start = 1
		base_end = 2

		# inserting a regular record should work
		count_obs_before = self.ndb.count_observations()
		self.ndb._insert_observation(service, key, base_start, base_end)
		self.assertTrue(self.ndb.count_observations() == (count_obs_before + 1))

		# start time == 0 should work
		count_obs_before = self.ndb.count_observations()
		self.ndb._insert_observation(service, key, 0, 100)
		self.assertTrue(self.ndb.count_observations() == (count_obs_before + 1))

		# start time < 0 should fail
		count_obs_before = self.ndb.count_observations()
		self.ndb._insert_observation(service, key, -10, 2)
		self.assertTrue(self.ndb.count_observations() == count_obs_before)

		# end time == 0 should work (use a different service name so they don't clash)
		count_obs_before = self.ndb.count_observations()
		self.ndb._insert_observation(service + 'a', key, 0, 0)
		self.assertTrue(self.ndb.count_observations() == (count_obs_before + 1))

		# end time < 0 should fail
		count_obs_before = self.ndb.count_observations()
		self.ndb._insert_observation(service, key, 1, -10)
		self.assertTrue(self.ndb.count_observations() == count_obs_before)

		# start time > end time should fail
		count_obs_before = self.ndb.count_observations()
		self.ndb._insert_observation(service, key, 15, 10)
		self.assertTrue(self.ndb.count_observations() == count_obs_before)

		# trying to insert a duplicate observation should fail
		count_obs_before = self.ndb.count_observations()
		self.ndb._insert_observation(service, key, base_start, base_end)
		self.assertTrue(count_obs_before == self.ndb.count_observations())

		# same key, same start, different end should fail
		count_obs_before = self.ndb.count_observations()
		self.ndb._insert_observation(service, key, base_start, base_end + 1)
		self.assertTrue(count_obs_before == self.ndb.count_observations())

		# same key, same end, different start should fail
		count_obs_before = self.ndb.count_observations()
		self.ndb._insert_observation(service, key, base_start + 1, base_end)
		self.assertTrue(count_obs_before == self.ndb.count_observations())

		# null values should be ignored
		self.ndb._insert_observation(None, key, 1, 2)
		self.ndb._insert_observation(service, None, 1, 2)
		self.ndb._insert_observation(service, key, None, 2)
		self.ndb._insert_observation(service, key, 1, None)

	def test_update_observation_end_time(self):
		# this function should only be called internally by the class during normal use,
		# but we still want to test it.
		srv = 'update_obs_end_time_test:443,2'
		key = 'aa:bb'
		end_time = 2

		# insert the service and observation first to make sure we get no errors
		self.ndb.insert_service(srv)
		self.ndb._insert_observation(srv, key, end_time - 1, end_time)


		# a regular update should work
		self.ndb._update_observation_end_time(srv, key, end_time, end_time + 1)

		# trying to set end time < current time should fail
		self.ndb._update_observation_end_time(srv, key, end_time + 1, end_time - 10)
		obs = self.ndb.get_observations(srv)
		ob_count = 0
		for ob in obs:
			ob_count = ob_count + 1
			self.assertTrue(ob.end == (end_time + 1))
		self.assertTrue(ob_count == 1)

		# trying to set end time == current time should fail
		self.ndb._update_observation_end_time(srv, key, end_time + 1, end_time + 1)
		obs = self.ndb.get_observations(srv)
		ob_count = 0
		for ob in obs:
			ob_count = ob_count + 1
			self.assertTrue(ob.end == (end_time + 1))
		self.assertTrue(ob_count == 1)

		# null values should be ignored
		self.ndb._update_observation_end_time(None, key, end_time, end_time)
		self.ndb._update_observation_end_time(srv, None, end_time, end_time)
		self.ndb._update_observation_end_time(srv, key, None, end_time)
		self.ndb._update_observation_end_time(srv, key, end_time, None)

	def test_report_observation(self):
		self.ndb.report_observation('report_observation_test:443,2', 'aa:bb')

	# less important SQL - used less often or in the background
	def test_count_services(self):
		count = self.ndb.count_services()
		self.assertTrue(count >= 0)

	def test_count_observations(self):
		count = self.ndb.count_observations()
		self.assertTrue(count >= 0)

	def test_get_all_observations(self):
		self.ndb.get_all_observations()
		self.ndb.close_session()

	def test_insert_bulk_services(self):
		services = ['bulkinserttest:443,2', 'bulkinserttest_2:443,2', 'bulkinserttest_3:443,2']

		count_srv_before = self.ndb.count_services()
		self.ndb.insert_bulk_services(services)
		count_srv_after = self.ndb.count_services()
		self.assertTrue(count_srv_before == (count_srv_after - len(services)))

parser = argparse.ArgumentParser(description=__doc__)

if __name__ == '__main__':

	args = parser.parse_args()

	if (os.path.exists(NotaryDBTestCases.TEST_DATABASE) and (os.path.isfile(NotaryDBTestCases.TEST_DATABASE))):
			try:
				print "Deleting test database file {0}".format(NotaryDBTestCases.TEST_DATABASE)
				os.remove(NotaryDBTestCases.TEST_DATABASE)
			except (Exception) as e:
				print >> sys.stderr, "Error deleting test database: '{0}'. WARNING - tests may not run properly.".format(e)

	test_suite = unittest.TestLoader().loadTestsFromTestCase(NotaryDBTestCases)
	unittest.main(verbosity=2)
