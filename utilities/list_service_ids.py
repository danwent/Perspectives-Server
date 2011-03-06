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

import sys
import os
import re
import time
import sqlite3 

# This script generates a file of services ids
# indicating when the last time the notary successfully observed
# a key from that service.  The first parameter points to the
# notary's database file.  The last two
# parameters filter the set of service ids printed based on the
# last observation date.  If 'newer'' is provided, the script will
# only print services with an observation newer than 'days' days.
# If 'older' is provided, the script will print only service ids
# with a MOST RECENT observation that is older than 'days' days.
# Thus, the script can be used to either generate a list of all services
# considered 'live' and of all services considered 'dead'.

def usage_and_exit(): 
  print >> sys.stderr, "ERROR: usage: <notary-db-file> <all|older|newer> <days>"
  exit(1)

if len(sys.argv) == 4: 
	if not (sys.argv[2] == "older" or sys.argv[2] == "newer"): 
		usage_and_exit()
	cur_time = int(time.time()) 
	threshold_sec = int(int(time.time()) - (3600 * 24 * int(sys.argv[3])))
elif len(sys.argv) == 3: 
	if not sys.argv[2] == "all": 
		usage_and_exit()
else: 
	usage_and_exit()
	

conn = sqlite3.connect(sys.argv[1])
cur = conn.cursor()

if sys.argv[2] == "all": 
	cur.execute("select distinct service_id from observations")
elif sys.argv[2] == "older": 
	cur.execute("select distinct service_id from observations where service_id not in (select distinct service_id from observations where end > ?)", [ threshold_sec ])
else: 
	cur.execute("select distinct service_id from observations where end > ?", [ threshold_sec ] )
	
for row in cur:
	print row[0] 
