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

SSH_TYPE = "1"
SSL_TYPE = "2"
SERVICE_TYPES = {SSH_TYPE: "ssh",
				 SSL_TYPE: "ssl"}


def report_observation_with_db(ndb, service, fp):
	"""Insert or update an Observation record in the notary database."""

	cur_time = int(time.time()) 
	obs = ndb.get_observations(service)
	most_recent_time_by_key = {}

	most_recent_key = None
	most_recent_time = 0

	# calculate the most recently seen key
	for (service, key, start, end) in obs:
		if key not in most_recent_time_by_key or end > most_recent_time_by_key[key]:
			most_recent_time_by_key[key] = end

		for k in most_recent_time_by_key:
			if most_recent_time_by_key[k] > most_recent_time:
				most_recent_key = k
				most_recent_time = most_recent_time_by_key[k]
	ndb.close_session()

	if most_recent_key == fp: 
		# this key matches the most recently seen key before this observation.
		# just update the observation 'end' time.
		ndb.update_observation_end_time(service, fp, most_recent_time, cur_time)
		ndb.report_metric('ServiceScanKeyUpdated', service)
	else: 
		# the key has changed or no observations exist yet for this service.
		# add a new entry for this key with start and end set to the current time
		ndb.insert_observation(service, fp, cur_time, cur_time)
		if most_recent_key != None:
			# if there was a previous key, set its 'end' timespan value to be
			# the current time minus one second (ending just before the new key)
			ndb.update_observation_end_time(service, most_recent_key, most_recent_time, cur_time -1)
			ndb.report_metric('ServiceScanPrevKeyUpdated', service)


