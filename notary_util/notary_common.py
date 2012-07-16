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

"""Notary utility functions called from many places."""

import time

from notary_db import ndb


def report_observation_with_db(ndb, service_id, fp):
	"""Insert or update an Observation record in the notary database."""

	cur_time = int(time.time()) 
	obs = ndb.get_observations(service_id)
	most_recent_time_by_key = {}

	most_recent_key = None
	most_recent_time = 0
	for row in obs:
		k = row[1]
		if k not in most_recent_time_by_key or row[3] > most_recent_time_by_key[k]: 
			most_recent_time_by_key[k] = row[3]

		for k in most_recent_time_by_key:
			if most_recent_time_by_key[k] > most_recent_time:
				most_recent_key = k
				most_recent_time = most_recent_time_by_key[k]  

	if most_recent_key == fp: 
		# this key was also the most recently seen key before this observation.
		# just update the observation row to set the timespan 'end' value to the 
		# current time.
		ndb.update_observation_end_time(service_id, fp, most_recent_time, cur_time)
	else: 
		# key has changed or no observations exist yet for this service_id.  Either way
		# add a new entry for this key with timespan start and end set to the current time
		ndb.insert_observation(service_id, fp, cur_time, cur_time)
		if most_recent_key != None:
			# if there was a previous key, set its 'end' timespan value to be current 
			# time minus one seconds 
			ndb.update_observation_end_time(service_id, most_recent_key, most_recent_time, cur_time -1)


