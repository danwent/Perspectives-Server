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

# library that helps you write code that analyzes a notary database dumped
# in the standard textfile format.  Create a class that sub-classes NotaryFileAnalyzer
# and call 'run_analyzer' with the name of a database dump file and an instance of the
# analyzer class

class NotaryFileAnalyzer: 
	
	def start(self): 
		pass 

	def on_service(self, service_id):
		pass

	def on_key(self, key_type, key_hash): 
		pass 

	def on_observation(self, start_ts,end_ts): 
		pass 
	
	def end(self): 
		pass

# analyzer methods will be called in file order 
def run_analyzer(fname, analyzer): 
    f = open(fname, 'r')
    analyzer.start()
    while True:
	# per-host
	line = f.readline()
	if len(line) == 0:
		break
	assert(line.startswith("Start Host:")) 
	service_id = line.split("'")[1]
	analyzer.on_service(service_id) 

	while True:
		# per-key  
		line = f.readline()
		if line.startswith("End Host"):
			break 
		# otherwise, must be a key 
		key_arr = line.split()
		if(len(key_arr) != 3): 
			print "Error: While parsing '%s', expected key or " \
				"'End Host', but got '%s'" % \
				(service_id, line)
		analyzer.on_key(key_arr[0], key_arr[2]) 
		
		while True: 
			line = f.readline()
			if len(line.strip()) == 0:
				# done with key
				break 
			line2 = f.readline() 
			analyzer.on_observation(line.split()[1], 
						line2.split()[1])
	 
	
    analyzer.end()

