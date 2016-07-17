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
import logging
import os
import re
import sys

import keygen
import crypto


class keymanager(object):
	"""Read, set, create, and export public and private server keys."""

	ENV_PUB_KEY_NAME='NOTARY_PUBLIC_KEY'
	ENV_PRIV_KEY_NAME='NOTARY_PRIVATE_KEY'

	def __init__(self, args):
		"""
		Initialize a new keymanager.

		Some extra work is done here to make it easier for callers to import this module."""

		# sanity/safety check:
		# filter the args and send only those that are relevant to __actual_init__.
		self.__actual_init__(**keymanager.filter_args(vars(args)))



	# note: keep these arg names the same as the argparser args - see filter_args()
	def __actual_init__(self, private_key=None, envkeys=None, export_heroku_keys=None):
		"""
		Initialize a new keymanager.

		The actual initialization work is done here.
		"""
		self.envkeys = envkeys
		self.private_key = private_key
		self.export_heroku_keys = export_heroku_keys
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
				help="File to use as the private key. '.priv' will be appended if necessary. Default: \'%(default)s\'.\
				If the public/private keypair do not exist they will be automatically created.")

		else:
			# don't specify description or epilogue,
			# so the module that includes us can write their own.
			parser = argparse.ArgumentParser(add_help=False)

			# when imported from another module it makes more sense to use an optional argument.
			keygroup = parser.add_mutually_exclusive_group()
			keygroup.add_argument('--private-key', '-k', default=keygen.DEFAULT_PRIV_NAME, metavar='PRIVATE_KEY_FILE',
				help="File to use as the private key. '.priv' will be appended if necessary. Default: \'%(default)s\'.\
				If the public/private keypair do not exist they will be automatically created.")

		keygroup.add_argument('--envkeys', action='store_true', default=False,
			help="Read public and private keys from the environment variables '" +
				self.ENV_PUB_KEY_NAME + "' and '" + self.ENV_PRIV_KEY_NAME + "' rather than from files." +
				" Default: \'%(default)s\'.")
		keygroup.add_argument('--export-heroku-keys', '--export-heroku', '--heroku',
			nargs='?', default=None, const='', metavar='app-name',
			help="Export the keys as heroku 'config vars' for the specified app (or the current app if none is specified).\
			For notaries hosted on heroku.com.")

		return parser


	def get_keys(self):
		"""
		Read and return a public/private key pair, creating them if necessary.
		If valid keys cannot be created or read, return (None, None).
		"""
		if (self.envkeys):
			(pub_key, priv_key) = self.get_env_keys()
		else:
			(pub_key, priv_key) = self.get_file_keys(self.private_key)

		if (pub_key == None or priv_key == None):
			return (None, None)

		valid_keys = True

		if not (crypto.validate_public_rsa(pub_key)):
			logging.error("Error: public key '%s' is not a valid RSA key." % pub_key)
			valid_keys = False
		if not (crypto.validate_private_rsa(priv_key)):
			logging.error("Error: private key is not a valid RSA key.")
			valid_keys = False

		if (valid_keys):
			if (self.export_heroku_keys != None):
				self.set_heroku_keys(pub_key, priv_key)
			return (pub_key, priv_key)
		else:
			return (None, None)


	def get_env_keys(self):
		"""Read public and private keys from environment variables."""

		if ((self.ENV_PUB_KEY_NAME not in os.environ) or \
			(self.ENV_PRIV_KEY_NAME not in os.environ) or \
			(os.environ[self.ENV_PUB_KEY_NAME] == None) or \
			(os.environ[self.ENV_PRIV_KEY_NAME] == None)):

			return (None, None)

		valid_pub_key = crypto.valid_pub_key
		valid_priv_key = crypto.valid_priv_key

		pub_key = None
		key_try = str(os.environ[self.ENV_PUB_KEY_NAME])
		match = valid_pub_key.match(key_try)
		if (match != None):
			pub_key = "%s\n%s\n%s" % (match.group(1), self.wrap_key(match.group(2)), match.group(3))

		priv_key = None
		key_try = str(os.environ[self.ENV_PRIV_KEY_NAME])
		match = valid_priv_key.match(key_try)
		if (match != None):
			priv_key = "%s\n%s\n%s" % (match.group(1), self.wrap_key(match.group(2)), match.group(3))

		return (pub_key, priv_key)

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
			logging.error(e)
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

	def set_heroku_keys(self, pub_key, priv_key):
		"""
		Export keys as heroku config vars.
		This way the user doesn't have to awkwardly copy/paste things manually.
		"""

		# remove newlines so keys are exported properly
		pub_key = pub_key.replace('\n', '')
		priv_key = priv_key.replace('\n', '')

		app_name = ''
		if (self.export_heroku_keys != ''):
			# then the user specified an app name.

			# remove invalid characters from the app name.
			# note: heroku's app names match the policy on valid domain names
			# https://en.wikipedia.org/wiki/Hostname#Restrictions_on_valid_host_names
			# i.e.: heroku app names must start with a letter
			# and can only contain lowercase letters, numbers, and dashes.
			app_name = self.export_heroku_keys
			app_name = "--app " + re.sub("[^a-z0-9\-]",'', app_name)

		# wrap key values in "" in case we have an = sign in our key.
		# quotes will not be present in the exported config var.
		export = "heroku config:set %s=\"%s\" %s=\"%s\" %s" % \
			(self.ENV_PUB_KEY_NAME, pub_key, self.ENV_PRIV_KEY_NAME, priv_key, app_name)
		ret = os.system(export)
		if (ret != 0):
			logging.error("Error: setting heroku config vars\n")


	def wrap_key(self, key, width = 65):
		"""Wrap text at 'width' lines so it prints nicely."""
		key = key.strip()
		if (len(key) < width):
			return key
		else:
			return key[:(width-1)] + '\n' + self.wrap_key(key[(width-1):])


if __name__ == "__main__":
	args = keymanager.get_parser().parse_args()
	keymanager = keymanager(args)
	keymanager.get_keys()
