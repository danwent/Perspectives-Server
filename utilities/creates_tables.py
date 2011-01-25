import sqlite3
import sys

if len(sys.argv) != 2: 
  print "usage: <db-file>"
  exit(1)

conn = sqlite3.connect(sys.argv[1])
conn.execute('''create table observations 
	(service_id text, key text, start integer, end integer)''') 
conn.execute('''create index sid_index on observations (service_id)''')
conn.commit()
conn.close()
