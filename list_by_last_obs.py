#!@python_EXEC@

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


if len(sys.argv) != 4:
  print >> sys.stderr, "ERROR: usage: <notary-db-file> <older|newer> <days>"
  exit(1)

is_older = True
if sys.argv[2] == "newer":
	is_older = False
	
cur_time = int(time.time()) 
threshold_sec = int(int(time.time()) - (3600 * 24 * int(sys.argv[3])))

conn = sqlite3.connect(sys.argv[1])
cur = conn.cursor()

if is_older: 
	cur.execute("select distinct service_id from observations where service_id not in (select distinct service_id from observations where end > %s)" % threshold_sec)
else: 
	cur.execute("select distinct service_id from observations where end > %s" %threshold_sec)
	
for row in cur:
	print row[0] 
