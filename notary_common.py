import time 
import sqlite3 

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

	cur_time = int(time.time()) 

	conn = sqlite3.connect(notary_db_file)
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
	conn.commit()
	conn.close() 


