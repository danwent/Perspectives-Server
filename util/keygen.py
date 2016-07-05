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

"""Generate a private and public RSA keypair using openssl."""

from __future__ import print_function

import os
import re
import stat
from subprocess import call


# Notary signatures covering observed key data do not need long-term security,
# as signatures are recomputed frequently and notary keys are easily updated.
# We want the shortest key size (maximize performance) that is still secure.
# 1369-bit RSA is deemed secure enough for now [14].
# For more see the Perspectives academic paper
# http://perspectivessecurity.files.wordpress.com/2011/07/perspectives_usenix08.pdf
NEW_KEY_LENGTH = 1369
DEFAULT_PRIV_NAME = "notary.priv"
DEFAULT_PUB_NAME = "notary.pub"

def generate_keypair(public_key_name=DEFAULT_PUB_NAME, private_key_name=DEFAULT_PRIV_NAME):
	"""Generate a private and public RSA keypair using ssl and write those keys to files."""

	if not (os.path.isfile(private_key_name)):
		print("Generating notary private key '%s'" % (private_key_name))
		ret = call(["openssl", "genrsa", "-out", private_key_name, str(NEW_KEY_LENGTH)])
		if (ret == 0):
			print("Success")
			os.chmod(private_key_name, stat.S_IRUSR | stat.S_IXUSR) #600 . 'Read-only' on Windows.
		print("Generating notary public key '%s'" % (public_key_name))
		ret = call(["openssl", "rsa", "-in", private_key_name, "-out", public_key_name, "-outform", "PEM", "-pubout"])
		if (ret == 0):
			print("Success")

	return (public_key_name, private_key_name)

