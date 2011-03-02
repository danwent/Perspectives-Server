#   This file is part of the Perspectives Notary Server
#
#   Copyright (C) 2011 Dan Wendlandt
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, version 2 of the License.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
import os
import re
import time 
import sqlite3
from file_analyzer import run_analyzer, NotaryFileAnalyzer

class SQLiteImportAnalyzer(NotaryFileAnalyzer): 
 	
	def __init__(self, filename):
		self.conn = sqlite3.connect(filename)
		self.num_services = 0

	def on_service(self, service_id):
		self.num_services += 1
		if self.num_services % 1000 == 0: 
			print "%s services seen" % self.num_services  		
		self.service_id = service_id
		# create null key entry for service with no observations.  This is useful when
		# bootstrapping a notary database from the list of service-ids from another notary
		ret = self.conn.execute("insert into observations values (?,NULL,NULL,NULL)", 
			 (self.service_id,))

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


