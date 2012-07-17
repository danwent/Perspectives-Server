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
Scan a list of services and print results.
To run scans and update results in a network notary database instead,
see threaded_scanner.py.
"""

import os
import sys
import time
import subprocess
import argparse

# sub-modules to use for the actual scanning work.
# they should be in the path.
SSL_SCAN="ssl_scan_openssl.py"
SSH_SCAN="ssh_scan_openssh.py"

SSH_TYPE = "1"
SSL_TYPE = "2"

DEFAULT_SCANS = 10
DEFAULT_WAIT = 20


def start_scan_probe(sid):
  host_and_port, service_type = sid.split(",")
  if service_type == SSL_TYPE:
    first_arg = SSL_SCAN
  elif service_type == SSH_TYPE:
    first_arg = SSH_SCAN
  else:
    print >> sys.stderr, "ERROR: invalid service_type for '%s'" % sid
    return

  nul_f = open(os.devnull,'w')
  return subprocess.Popen(["python", first_arg, sid], stdout=nul_f , stderr=subprocess.STDOUT )



parser = argparse.ArgumentParser(description=__doc__)

parser.add_argument('service_id_file', type=argparse.FileType('r'),
			help="""File that contains a list of service names - one per line.
			Use '-' to read from stdin (e.g. to pass a list from a script like list_services.py).
			Services take the form of 'host:port,servicetype' - where servicetype is """ + SSL_TYPE +
			""" for ssl or """ + SSH_TYPE + """ for ssh.""")
parser.add_argument('--max-sim', '--max', '-m', nargs='?', default=DEFAULT_SCANS, const=DEFAULT_SCANS, type=int,
			help="Maximun number of scans to run at once. Default: %(default)s.")
parser.add_argument('--timeout', '--wait', '-w', nargs='?', default=DEFAULT_WAIT, const=DEFAULT_WAIT, type=int,
			help="Maximum number of seconds each scan will wait (asychronously) for results before giving up. Default: %(default)s.")

args = parser.parse_args()
max_sim = args.max_sim
timeout_sec = args.timeout
f = args.service_id_file

to_probe = [ line.rstrip() for line in f ]

total_count = len(to_probe)
active_sids = {}
done = False
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
    active_sids[sid] = (start_scan_probe(sid), time.time())
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
