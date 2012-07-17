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
"""

import time
import sqlite3


class ndb:
	"""
	Notary database interface - create and interact with database tables.
	"""

	def __init__(self, db_file):
		self.db_file = db_file
		self.conn = None
		self.cur = None

	def get_conn(self):
		if (self.conn == None):
			self.conn = sqlite3.connect(db_file)
		return self.conn

	def get_cursor(self):
		if (self.cur == None):
			self.cur = gen_conn.cursor()
		return self.cur

	def get_all_observations():
		"""Get all observations."""
		return self.get_cursor().execute("select * from observations where key not NULL")

	def get_observations(service_id):
		"""Get all observations for a given service."""
		return self.get_cursor().execute("select * from observations where service_id = ? and key not NULL", (service_id,))

	def insert_observation(service_id, key, start_time, end_time):
		"""Insert a new Observation about a service/key pair."""
		self.get_cursor().execute("insert into observations (service_id, key, start, end) values (?,?,?,?)",
			(service_id, key, start_time, end_time))

	def update_observation_end_time(service_id, fp, old_end_time, new_end_time):
		"""Update the end time for a given Observation."""
		self.get_cursor.execute("update observations set end = ? where service_id = ? and key = ? and end = ?",
			(new_end_time, service_id, fp, most_recent_time))