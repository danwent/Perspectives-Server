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
Cryptography-related functions.
"""

import base64
import hashlib
from M2Crypto import BIO, RSA


def sign_content(content, private_key):
	"""Sign content with a private key."""

	m = hashlib.md5()
	m.update(content)
	bio = BIO.MemoryBuffer(private_key)
	rsa_priv = RSA.load_key_bio(bio)
	sig_before_raw = rsa_priv.sign(m.digest(),'md5') 
	sig = base64.standard_b64encode(sig_before_raw) 

	return sig
