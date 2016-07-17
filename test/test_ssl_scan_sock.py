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
import unittest

# TODO: HACK
# add ..\util to the import path so we can import ssl_scan_sock
sys.path.insert(0,
	os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from util.ssl_scan_sock import attempt_observation_for_service

class SSLScanSockTestCases(unittest.TestCase):
	"""Test the standalone scanner."""

	def test_site_with_no_port(self):
		self.assertRaises(ValueError, attempt_observation_for_service, 'testsite.com', 10, False)
		self.assertRaises(ValueError, attempt_observation_for_service, 'testsite.com', 10, True)

	def test_site_with_non_numeric_port(self):
		self.assertRaises(ValueError, attempt_observation_for_service, 'testsite.com:', 10, False)
		self.assertRaises(ValueError, attempt_observation_for_service, 'testsite.com:', 10, True)
		self.assertRaises(ValueError, attempt_observation_for_service, 'testsite.com:a', 10, False)
		self.assertRaises(ValueError, attempt_observation_for_service, 'testsite.com:a', 10, True)

	# TODO: implement --dry-run mode so we can run tests without actually scanning
	#def test_valid_site(self):
	#	self.assertTrue(attempt_observation_for_service('testsite.com:443', 10, False))
	#	self.True(attempt_observation_for_service('testsite.com:443', 10, True))
