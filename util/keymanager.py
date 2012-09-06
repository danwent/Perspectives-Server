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

"""Read, set, create, and export public and private server keys."""

import argparse
import os
import re
import sys

import keygen
import crypto


class keymanager:
	"""Read, set, create, and export public and private server keys."""

	def __init__(self, args):
		"""
		Initialize a new keymanager.

		Some extra work is done here to make it easier for callers to import this module."""

		# sanity/safety check:
		# filter the args and send only those that are relevant to __actual_init__.
		self.__actual_init__(**keymanager.filter_args(vars(args)))


	# note: keep these arg names the same as the argparser args - see filter_args()
	def __actual_init__(self, private_key=None, envkeys=None):
		"""
		Initialize a new keymanager.

		The actual initialization work is done here.
		"""

		self.envkeys = envkeys
		self.private_key = private_key
		return


	@classmethod
	def filter_args(self, argsdict):
		"""
		Filter a dictionary of arguments and return only ones that are applicable to this class.
		"""
		valid_args = keymanager.__actual_init__.func_code.co_varnames[:keymanager.__actual_init__.func_code.co_argcount]
		d = dict((key, val) for key, val in argsdict.iteritems() if key in valid_args)

		if 'self' in d:
			del d['self']

		return d

	@classmethod
	def get_parser(self):
		"""
		Get a parser object with the correct arguments for this module.
		Returns the correct type of parser for running as a standalone module
		or when imported from somewhere else.
		"""
		parser = None
		if __name__ == "__main__":
			parser = argparse.ArgumentParser(description=keymanager.__doc__)

			# when running by itself, using an optional positional argument
			# is the expected behaviour
			keygroup = parser.add_mutually_exclusive_group()
			keygroup.add_argument('private_key', nargs='?', default=keygen.DEFAULT_PRIV_NAME,
				help="File to use as the private key. '.priv' will be appended if necessary. Default: \'%(default)s\'.")

		else:
			# don't specify description or epilogue,
			# so the module that includes us can write their own.
			parser = argparse.ArgumentParser(add_help=False)

			# when imported from another module it makes more sense to use an optional argument.
			keygroup = parser.add_mutually_exclusive_group()
			keygroup.add_argument('--private-key', '-k', default=keygen.DEFAULT_PRIV_NAME, metavar='PRIVATE_KEY_FILE',
				help="File to use as the private key. '.priv' will be appended if necessary. Default: \'%(default)s\'.")

		return parser


	def get_keys(self):
		"""
		Read and return a public/private key pair, creating them if necessary.
		If valid keys cannot be created or read, return (None, None).
		"""

		(pub_key, priv_key) = self.get_file_keys(self.private_key)

		if (pub_key == None or priv_key == None):
			return (None, None)

		valid_keys = True

		if not (crypto.validate_public_rsa(pub_key)):
			print >> sys.stderr, "Error: public key '%s' is not a valid RSA key." % pub_key
			valid_keys = False
		if not (crypto.validate_private_rsa(priv_key)):
			print >> sys.stderr, "Error: private key is not a valid RSA key."
			valid_keys = False

		if (valid_keys):
			return (pub_key, priv_key)
		else:
			return (None, None)


	def get_file_keys(self, private_key):
		"""Read public and private keys from files on disk."""
		(pub_file, priv_file) = self.get_keynames(private_key)
		keygen.generate_keypair(pub_file, priv_file)
		try:
			with open(priv_file,'r') as priv:
				priv_key = priv.read()

			with open(pub_file,'r') as pub:
				pub_key = pub.read()

		except IOError as e:
			print >> sys.stderr, e
			pub_key = None
			priv_key = None

		return (pub_key, priv_key)


	def get_keynames(self, private_key_name=keygen.DEFAULT_PRIV_NAME):
		"""Calculate the names to use for public and private key files."""
		real_priv_name = private_key_name + ".priv"
		real_pub_name = private_key_name + ".pub"

		keypat = re.compile("(.*)\.priv$")
		if (keypat.match(private_key_name)):
			# don't append ".priv" twice
			real_priv_name = keypat.match(private_key_name).group(1) + ".priv"
			real_pub_name = keypat.match(private_key_name).group(1) + ".pub"

		return (real_pub_name, real_priv_name)


if __name__ == "__main__":
	args = keymanager.get_parser().parse_args()
	keymanager = keymanager(args)
	keymanager.get_keys()
