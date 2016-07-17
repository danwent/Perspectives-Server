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
Ask a network notary server what keys it has seen for a particular service.
"""

from __future__ import print_function

import sys
import traceback  
import argparse

from client_common import verify_notary_signature, notary_reply_as_text,fetch_notary_xml 


DEFAULT_SERVER = 'localhost'
DEFAULT_PORT = '8080'
DEFAULT_KEYFILE = 'notary.pub'

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('service_id', default=DEFAULT_SERVER,
			help="A remote service of the form 'hostname:port,servicetype'. Use servicetype '1' for SSH or '2' for SSL.")
# don't use type=FileType for the key because we don't want argparse
# to try opening it before the program runs.
# this module should be callable without using any key at all.
parser.add_argument('--notary_pubkey', '--key', '-k', default=DEFAULT_KEYFILE, metavar='KEYFILE',
			help="File containing the notary's public key. If supplied the response signature from the notary will be verified. Default: \'%(default)s\'.")
parser.add_argument('--notary-server', '--server', '-s', default=DEFAULT_SERVER, metavar='SERVER',
			help="Notary server to contact. Default: \'%(default)s\'.")
parser.add_argument('--notary_port', '--port', '-p', type=int, default=DEFAULT_PORT, metavar='PORT',
			help="Port to contact the server on. Default: \'%(default)s\'.")

args = parser.parse_args()

try: 
	code, xml_text = fetch_notary_xml(args.notary_server, args.notary_port, args.service_id)
	if code == 404: 
		print("Notary has no results for '%s'." % args.service_id)
	elif code != 200: 
		print("Notary server returned error code: %s" % code)
except Exception, e:
	print("Exception contacting notary server:")
	traceback.print_exc(e)
	exit(1) 

print(50 * "-")
print("XML Response:")
print(xml_text)
print(50 * "-")

try:
	pub_key = open(args.notary_pubkey).read()
	if not verify_notary_signature(args.service_id, xml_text, pub_key):
		print("Signature verification failed. Results are not valid.")
		exit(1)
except IOError:
	print("Warning: no public key specified, not verifying notary signature.")

print("Results:")
print(notary_reply_as_text(xml_text))
