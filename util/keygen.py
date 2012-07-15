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

"""Generate a private and public RSA keypair."""

import os
import re
import argparse
import stat
from subprocess import call


# Notary signatures covering observed key data do not need long-term security,
# as signatures are recomputed frequently and notary keys are easily updated.
# We want the shortest key size (maximize performance) that is still secure.
# 1369-bit RSA is deemed secure enough for now [14].
# For more see the Perspectives academic paper
# http://perspectivessecurity.files.wordpress.com/2011/07/perspectives_usenix08.pdf
NEW_KEY_LENGTH = 1369
DEFAULT_KEY_NAME = "notary.priv"


def get_keynames(private_key_name=DEFAULT_KEY_NAME):
	"""Calculate the names to use for public and private keys."""
	real_priv_name = private_key_name + ".priv"
	real_pub_name = private_key_name + ".pub"

	keypat = re.compile("(.*)\.priv$")
	if (keypat.match(private_key_name)):
		# don't append ".priv" twice
		real_priv_name = keypat.match(private_key_name).group(1) + ".priv"
		real_pub_name = keypat.match(private_key_name).group(1) + ".pub"

	return (real_pub_name, real_priv_name)


def generate_keypair(private_key_name=DEFAULT_KEY_NAME):
	"""Generate a private and public RSA keypair."""

	(real_pub_name, real_priv_name) = get_keynames(private_key_name)

	if not (os.path.isfile(real_priv_name)):
		print "Generating notary private key '%s'" % (real_priv_name)
		ret = call(["openssl", "genrsa", "-out", real_priv_name, str(NEW_KEY_LENGTH)])
		if (ret == 0):
			print "Success"
			os.chmod(real_priv_name, stat.S_IRUSR | stat.S_IXUSR) #600 . Won't affect anything on Windows.
		print "Generating notary public key '%s'" % (real_pub_name)
		ret = call(["openssl", "rsa", "-in", real_priv_name, "-out", real_pub_name, "-outform", "PEM", "-pubout"])
		if (ret == 0):
			print "Success"

	return (real_pub_name, real_priv_name)


def get_parser():
	"""
	Get a parser object with the correct arguments for the keygen module.
	Returns the correct type of parser for running as a standalone module
	or when imported from somewhere else.
	"""
	parser = None
	if __name__ == "__main__":
		parser = argparse.ArgumentParser(description=generate_keypair.__doc__)

		# when running by itself, using an optional positional argument
		# is the expected behaviour
		parser.add_argument('private_key', nargs='?', default=DEFAULT_KEY_NAME,
			help="File to use as the private key. '.priv' will be appended if necessary. Default: \'%(default)s\'.")

	else:
		# don't specify description or epilogue,
		# so the module that includes us can write their own.
		parser = argparse.ArgumentParser(add_help=False)

		# when imported from another module it makes more sense to use an optional argument.
		parser.add_argument('--private-key', '-k', default=DEFAULT_KEY_NAME, metavar='PRIVATE_KEY_FILE',
			help="File to use as the private key. '.priv' will be appended if necessary. Default: \'%(default)s\'.")

	return parser


if __name__ == "__main__":
	args = get_parser().parse_args()
	generate_keypair(args.private_key)
