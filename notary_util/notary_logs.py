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

"""Common notary log functions."""

import errno
import os

LOG_DIR = 'logs'

def get_log_dir():
	"""Return the absolute path to the logs directory."""
	return os.path.join(os.path.dirname(os.path.abspath(__file__)),
		'..',
		LOG_DIR)

def get_log_file(filename):
	"""Return the absolute path to a log file inside the logs directory."""
	create_log_dir()
	return os.path.join(get_log_dir(), filename)

def create_log_dir():
	"""Create the log directory if it doesn't exist."""
	create_dir(get_log_dir())

def create_dir(path):
	"""Create a directory if it doesn't exist."""
	# use try/except here to avoid a race condition when checking for existence
	try:
		os.makedirs(path)
	except OSError as e:
		if (os.path.exists(path) and not os.path.isdir(path)):
			print >> sys.stderr, "ERROR: Could not create log directory '{0}': a file with that name already exists.".format(path)
			exit(1)
		elif e.errno != errno.EEXIST:
			raise

if __name__ == "__main__":
	pass
