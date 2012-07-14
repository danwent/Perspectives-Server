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
Export Observation data from a network notary database.
"""

import sys
import os
import re
import time
import sqlite3 

def print_sid_info(sid, key_to_obs): 
	s_type = sid.split(",")[1]
	
	if s_type not in service_type_to_key_type:
		return	
	
	print >> output_file, "Start Host: '%s'" % sid
	key_type_text = service_type_to_key_type[s_type]
	for key in key_to_obs:
		if key is None: 
			continue 
		print >> output_file, "%s key: %s" % (key_type_text,key)
		for ts in key_to_obs[key]: 
			print >> output_file, "start:\t%s - %s" % (ts[0],time.ctime(ts[0]))
			print >> output_file, "end:\t%s - %s" % (ts[1],time.ctime(ts[1]))
		print >> output_file, ""
	print >> output_file, "End Host"

service_type_to_key_type = { "1" : "ssh", "2" : "ssl" } 

if len(sys.argv) != 2 and len(sys.argv) != 3: 
  	print >> sys.stderr, "ERROR: usage: <notary-db-file> [output file]"
  	exit(1)

output_file = sys.stdout
if len(sys.argv) == 3: 
	output_file = open(sys.argv[2],'w')

conn = sqlite3.connect(sys.argv[1])
cur = conn.cursor()

cur.execute("select * from observations order by service_id")
old_sid = None
num_sids = 0

key_to_obs  = {} 
for row in cur:
	sid = row[0]
	if old_sid != sid: 
		num_sids += 1
		if num_sids % 1000 == 0: 
			print "processed %s service-ids" % num_sids
		if old_sid is not None: 
			print_sid_info(old_sid, key_to_obs)
		key_to_obs = {}
		old_sid = sid 
 
	key = row[1]
	if key not in key_to_obs:
		key_to_obs[key] = []
	key_to_obs[key].append((row[2],row[3]))


print_sid_info(sid, key_to_obs)
conn.close()  
