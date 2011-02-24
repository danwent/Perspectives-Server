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

service_type_to_key_type = { "1" : "ssh", "2" : "ssl" } 

if len(sys.argv) != 2 and len(sys.argv) != 3: 
  	print >> sys.stderr, "ERROR: usage: <notary-db-file> [output file]"
  	exit(1)

output_file = sys.stdout
if len(sys.argv) == 3: 
	output_file = open(sys.argv[2],'w')

conn = sqlite3.connect(sys.argv[1])
cur = conn.cursor()

# fancy group-by might work better, but I'm justing going
# to be lazy and load it all into memory.
print "starting select" 
cur.execute("select * from observations group by service_id")
print "done with select" 
cur_sid = None
key_to_obs  = {} 
num_sids = 0

for row in cur:
	sid = row[0]
	if cur_sid is None: 
		cur_sid = sid
	elif cur_sid != sid: 
		num_sids += 1
		if num_sids % 1000 == 0: 
			print "processed %s service-ids" % num_sids
		print >> output_file, "Start Host: '%s'" % sid
	
		key_type_text = service_type_to_key_type[cur_sid.split(",")[1]]
		for key in key_to_obs: 
			print >> output_file, "%s key: %s" % (key_type_text,key)
			for ts in key_to_obs[key]: 
				print >> output_file, "start:\t%s - %s" % (ts[0],time.ctime(ts[0]))
				print >> output_file, "end:\t%s - %s" % (ts[1],time.ctime(ts[1]))
			print >> output_file, ""
		print >> output_file, "End Host"
		cur_sid = sid
		key_to_obs = {}
 
	key = row[1]
	if key not in key_to_obs:
		key_to_obs[key] = []
	key_to_obs[key].append((row[2],row[3]))


conn.close()  
