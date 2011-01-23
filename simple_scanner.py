#!@python_EXEC@

import os
import sys
from subprocess import Popen,PIPE,STDOUT 
import time 
import notary_common


SSL_SCAN="ssl_scan.py" 
SSH_SCAN="ssh_scan.py"

def start_probe(sid, notary_db): 
  host_and_port, service_type = sid.split(",")
  if service_type == "2": 
    first_arg = SSL_SCAN 
  elif service_type == "1": 
    first_arg = SSH_SCAN 
  else: 
    print >> sys.stderr, "ERROR: invalid service_type for '%s'" % sid
    return  
  return Popen(["python", first_arg, sid, notary_db ] , stdout=PIPE, stderr=STDOUT, shell=False)
   
if len(sys.argv) != 5: 
  print >> sys.stderr, "ERROR: usage: <notary-db> <service_id_file> <max simultaneous> <timeout sec> " 
  sys.exit(1)

notary_db=sys.argv[1]
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

while True:
  while( len(active_sids) < max_sim ): 
    l = len(to_probe)
    if (l == 0):
      break
    if (l % 1000 == 0): 
      print >> sys.stderr, "INFO: %s probes remaining" % l
    sid = to_probe.pop()
    active_sids[sid] = (start_probe(sid, notary_db), time.time()) 

  if(len(active_sids) == 0): 
    break # all done
    
  now = time.time() 
  for sid,(p,t) in active_sids.items():
    code = p.poll()
    if code != None:
      if code != 0: 
        print >> sys.stderr, "WARNING: failed: %s %s" % (sid,code)
        failure_count += 1
      p.wait() # apparently this is needed on FreeBSD?
      del active_sids[sid]
    else:
      run_time = now - t
      if run_time > timeout_sec:
        os.kill(p.pid,9) # p.kill() required python 2.6
  sys.stdout.flush()
  sys.stderr.flush()
  time.sleep(1)

duration = time.time() - start_time
print >> sys.stderr, "INFO: *** Finished scan at %s. Scan took %s seconds" % (time.ctime(), duration) 
print >> sys.stderr, "INFO: *** %s of %s probes failed" % (failure_count, total_count)
