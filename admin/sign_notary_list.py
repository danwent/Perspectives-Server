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

from __future__ import print_function

import base64
import hashlib
import sys

from M2Crypto import BIO, RSA

#TODO: use argparse
if len(sys.argv) != 3: 
	print("usage: <notary-list-file> <private-key>" )
	exit(1) 


data = open(sys.argv[1],'r').read()
notary_priv_key= open(sys.argv[2],'r').read() 

m = hashlib.md5()
m.update(data)
bio = BIO.MemoryBuffer(notary_priv_key)
rsa_priv = RSA.load_key_bio(bio)
sig_before_raw = rsa_priv.sign(m.digest(),'md5') 
sig = base64.standard_b64encode(sig_before_raw) 
print(sig)
