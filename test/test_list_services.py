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
# add ..\notary_util to the import path
sys.path.insert(0,
	os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from notary_util import notary_db
from notary_util import list_services

class ListServicesTestCases(unittest.TestCase):
	"""
	Test the list services function.
	"""

	TEST_DATABASE = os.path.join(os.path.dirname(os.path.realpath(__file__)),
		'notary.unit_test.sqlite')

	class DBArgs():
		"""
		Simple class to create an extendable namespace.
		For passing arguments to ndb.
		"""
		pass

	def setUp(self):
		db_args = self.DBArgs()
		db_args.dbname = self.TEST_DATABASE
		db_args.metricsdb = True
		self.ndb = notary_db.ndb(db_args)

	#######

	def test_list_services_prints_to_stdout(self):
		# make sure there is at least one observation in the database to report
		self.ndb.report_observation('github.com', '00')
		list_services.main(self.ndb, sys.stdout)

	def test_list_services_prints_to_file(self):
		self.ndb.report_observation('github.com', '00')
		filename = 'test_list_file.txt'
		try:
			with open(filename, 'w') as testfile:
				list_services.main(self.ndb, testfile)
		finally:
			os.remove(filename)
