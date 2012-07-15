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

import sqlite3
import sys

if len(sys.argv) != 2: 
  print "usage: <db-file>"
  exit(1)

conn = sqlite3.connect(sys.argv[1])
conn.execute('''create table observations 
	(service_id text, key text, start integer, end integer)''') 
conn.execute('''create index sid_index on observations (service_id)''')
conn.execute('''create index sid_key_end_index on observations (service_id,key,end)''')
conn.commit()
conn.close()
