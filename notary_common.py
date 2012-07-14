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
import sqlite3 
import os
import subprocess

SSL_SCAN="ssl_scan_openssl.py" 
SSH_SCAN="ssh_scan_openssh.py"

def start_scan_probe(sid, notary_db): 
  host_and_port, service_type = sid.split(",")
  if service_type == "2": 
    first_arg = SSL_SCAN 
  elif service_type == "1": 
    first_arg = SSH_SCAN 
  else: 
    print >> sys.stderr, "ERROR: invalid service_type for '%s'" % sid
    return
	
  nul_f = open(os.devnull,'w') 
  return subprocess.Popen(["python", first_arg, sid, notary_db], stdout=nul_f , stderr=subprocess.STDOUT )

def parse_config(conf_fname): 
	config = {} 
	f = open(conf_fname,'r')
	for line in f: 
		try: 
			key,value = line.strip().split("=") 
			config[key] = value
		except: 
			pass
	return config

def report_observation(notary_db_file, service_id, fp): 


	conn = sqlite3.connect(notary_db_file)
	report_observation_with_conn(conn, service_id, fp)
	conn.commit()
	conn.close() 

def report_observation_with_conn(conn, service_id, fp): 
	"""Insert or update an Observation record in the notary database."""

	cur_time = int(time.time()) 
	cur = conn.cursor()
	cur.execute("select * from observations where service_id = ?", (service_id,))
	most_recent_time_by_key = {}

	most_recent_key = None
	most_recent_time = 0
	for row in cur: 
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
		conn.execute("update observations set end = ? where service_id = ? and key = ? and end = ?", 
			(cur_time, service_id, fp, most_recent_time))
	else: 
		# key has changed or no observations exist yet for this service_id.  Either way
		# add a new entry for this key with timespan start and end set to the current time
		conn.execute("insert into observations values (?,?,?,?)", 
			(service_id, fp, cur_time, cur_time))
		if fp != most_recent_key:
			# if there was a previous key, set its 'end' timespan value to be current 
			# time minus one seconds 
			conn.execute("update observations set end = ? where service_id = ? and key = ? and end = ?", 
				(cur_time - 1, service_id, most_recent_key, most_recent_time))


