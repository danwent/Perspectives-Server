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

from __future__ import print_function

import argparse
import unittest

import test_list_services
import test_notary_db
import test_pycache
import test_ssl_scan_sock

parser = argparse.ArgumentParser(description=__doc__)

if __name__ == '__main__':

	args = parser.parse_args()

	all_tests = unittest.TestSuite([
		unittest.TestLoader().loadTestsFromModule(test_list_services),
		unittest.TestLoader().loadTestsFromModule(test_notary_db),
		unittest.TestLoader().loadTestsFromModule(test_pycache),
		unittest.TestLoader().loadTestsFromModule(test_ssl_scan_sock),
	])
	unittest.TextTestRunner(verbosity=2).run(all_tests)
