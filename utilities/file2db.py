import sys
import os
import re
import time 
import sqlite3

# analyzer methods will be called in file order 
def run_analyzer(fname, analyzer): 
    f = open(fname, 'r')
    analyzer.start()
    while True:
	# per-host
	line = f.readline()
	if len(line) == 0:
		break
	assert(line.startswith("Start Host:")) 
	service_id = line.split("'")[1]
	analyzer.on_service(service_id) 

	while True:
		# per-key  
		line = f.readline()
		if line.startswith("End Host"):
			break 
		# otherwise, must be a key 
		key_arr = line.split()
		analyzer.on_key(key_arr[0], key_arr[2]) 
		
		while True: 
			line = f.readline()
			if len(line.strip()) == 0:
				# done with key
				break 
			line2 = f.readline() 
			analyzer.on_observation(line.split()[1], 
						line2.split()[1])
	 
	
    analyzer.end()


class SQLiteImportAnalyzer: 
 	
	def __init__(self, filename):
		self.conn = sqlite3.connect(filename)

	def start(self): 
		pass 

	def on_service(self, service_id):  		
		self.service_id = service_id

	def on_key(self, key_type, key_hash): 
		self.cur_key = key_hash 

	def on_observation(self, start_ts,end_ts): 
		ret = self.conn.execute("insert into observations values (?,?,?,?)", 
			(self.service_id, self.cur_key, start_ts, end_ts))
	
	def end(self): 
		self.conn.commit()	
		self.conn.close()
		

if len(sys.argv) != 3: 
  print "usage: <obs-file> <db-file>"
  exit(1)

a1 = SQLiteImportAnalyzer(sys.argv[2])
run_analyzer(sys.argv[1], a1) 


