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

import os
import sys
import time
import unittest

# TODO: HACK
# add ..\util to the import path
sys.path.insert(0,
	os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

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
