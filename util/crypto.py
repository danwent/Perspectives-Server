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
import re

from M2Crypto import BIO, RSA


valid_pub_key = re.compile("^(-----BEGIN PUBLIC KEY-----)[\n\r]*(.+)(-----END PUBLIC KEY-----)[\n\r]*$", re.DOTALL)
valid_priv_key = re.compile("^(-----BEGIN RSA PRIVATE KEY-----)[\n\r]*(.+)[\n\r]*(-----END RSA PRIVATE KEY-----)[\n\r]*$", re.DOTALL)


def sign_content(content, private_key):
	"""Sign content with a private key."""

	m = hashlib.md5()
	m.update(content)
	bio = BIO.MemoryBuffer(private_key)
	rsa_priv = RSA.load_key_bio(bio)
	sig_before_raw = rsa_priv.sign(m.digest(),'md5') 
	sig = base64.standard_b64encode(sig_before_raw) 

	return sig

def validate_public_rsa(key):
	"""Check if a key is a valid public RSA key."""
	return validate_rsa_key(key, "public")

def validate_private_rsa(key):
	"""Check if a key is a valid private RSA key."""
	return validate_rsa_key(key, "private")


def validate_rsa_key(key, keytype):
	"""Check if a key is a valid RSA key."""

	if (keytype == "public"):
		regex = valid_pub_key
	else:
		regex = valid_priv_key

	if (regex.match(key)):
		key = str(regex.match(key).group(2)).strip()
	else:
		return False

	# check that it has valid base64 characters
	key = re.sub('\s', '', key)
	base64chars = re.compile("^[A-Za-z0-9+/=]+$") # from RFC 3548

	if not (base64chars.match(key)):
		return False

	data = base64.b64decode(key)
	if (data == ""):
		return False # contained non-base64 data

	# Note: we could do additional checks against the public key header
	# or check that the private and public keys are a matching pair

	return True
