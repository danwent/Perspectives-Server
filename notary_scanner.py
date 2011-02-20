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

import os
import sys
import time 
import notary_common

   
if len(sys.argv) != 5: 
  print >> sys.stderr, "ERROR: usage: <notary-db> <service_id_file> <max simultaneous> <timeout sec> " 
  sys.exit(1)

notary_db=sys.argv[1]
if sys.argv[2] == "-": 
	f = sys.stdin
else: 
	f = open(sys.argv[2])

to_probe = [ line.rstrip() for line in f ] 

total_count = len(to_probe)
active_sids = {}
done = False
max_sim = int(sys.argv[3])
timeout_sec = int(sys.argv[4]) 
failure_count = 0
start_time = time.time()
print >> sys.stderr, "INFO: *** Starting scan of %s services at %s" % \
    (total_count,time.ctime())
print >> sys.stderr, "INFO: *** Timeout = %s sec  Max-Simultaneous = %s" % \
    (timeout_sec, max_sim) 

num_completed = 0
while True:
  while( len(active_sids) < max_sim and len(to_probe) > 0): 
    l = len(to_probe)
    if (l % 1000 == 0): 
      print >> sys.stderr, "INFO: %s probes remaining" % l
      sys.stdout.flush()
      sys.stderr.flush()
    sid = to_probe.pop()
    #probe_start = time.time()
    active_sids[sid] = (notary_common.start_scan_probe(sid, notary_db), time.time()) 
    #print "started probe for '%s' at %s (took %s)" % (sid, int(time.time() - start_time), time.time() - probe_start)

  if(len(active_sids) == 0): 
    break # all done
    
  now = time.time() 
  print "# %s seconds elapsed, %s active, %s complete, %s failures" % (int(now - start_time), len(active_sids), num_completed, failure_count)
  for sid,(p,t) in active_sids.items():
    code = p.poll()
    if code != None:
      if code != 0: 
        print >> sys.stderr, "WARNING: failed: %s %s" % (sid,code)
        failure_count += 1
      p.wait() # apparently this is needed on FreeBSD?
      num_completed += 1
      del active_sids[sid]
    else:
      run_time = now - t
      if run_time > timeout_sec:
	print "timeout for: '%s'" % sid
        #os.kill(p.pid,9) 
	p.kill() # requires python 2.6
	time.sleep(1.0) 

  time.sleep(0.5)

duration = time.time() - start_time
print >> sys.stderr, "INFO: *** Finished scan at %s. Scan took %s seconds" % (time.ctime(), duration) 
print >> sys.stderr, "INFO: *** %s of %s probes failed" % (failure_count, total_count)
