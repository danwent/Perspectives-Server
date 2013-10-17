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
Cache and retrieve data in key-value pairs.
"""

import abc
import os
import sys


class CacheBase(object):
	"""
	Abstract base class for all caching classes to inherit from.
	"""

	__metaclass__ = abc.ABCMeta

	CACHE_SERVER_VAR = 'SERVERS'
	CACHE_USER_VAR = 'USERNAME'
	CACHE_PASS_VAR = 'PASSWORD'
	CACHE_EXPIRY = 60 * 60 * 24 # seconds

	@classmethod
	def get_help():
		"""Tell the user how they can use this type of cache."""
		raise NotImplementedError( "This is just the abstract base class - please use a class that inherits from CacheBase." )

	@abc.abstractmethod
	def __init__(self, input):
		"""Create the cache."""
		# handle anything necessary here, such as connecting to servers
		raise NotImplementedError( "This is just the abstract base class - please use a class that inherits from CacheBase." )

	@abc.abstractmethod
	def get(self, key):
		"""Retrieve the value for a given key, or None if no key exists."""
		raise NotImplementedError( "This is just the abstract base class - please use a class that inherits from CacheBase." )

	@abc.abstractmethod
	def set(self, key, data, expiry):
		"""Save the value to a given key name."""
		raise NotImplementedError( "This is just the abstract base class - please use a class that inherits from CacheBase." )


class Memcache(CacheBase):
	"""
	Cache data using memcached (memcached.org).
	"""

	# the pylibmc module is not thread-safe,
	# so use connection pools to make it safe.

	CACHE_SERVER_VAR = 'MEMCACHE_SERVERS'
	CACHE_USER_VAR = 'MEMCACHE_USERNAME'
	CACHE_PASS_VAR = 'MEMCACHE_PASSWORD'

	@classmethod
	def get_help(self):
		"""Tell the user how they can use this type of cache."""
		return "Cache configuration is read from the environment variables " \
				+ self.CACHE_SERVER_VAR  + ", " + self.CACHE_USER_VAR + ", and " + self.CACHE_PASS_VAR + "."

	def __init__(self):
		"""Connect to the memcache server(s)."""
		self.pool = None
		try:
			import pylibmc
			#TODO: ALL INPUT IS EVIL
			#regex check these variables
			mc = pylibmc.Client(
				servers=[os.environ.get(self.CACHE_SERVER_VAR)],
				username=os.environ.get(self.CACHE_USER_VAR),
				password=os.environ.get(self.CACHE_PASS_VAR),
				binary=True
			)
			self.pool = pylibmc.ThreadMappedPool(mc)
		except ImportError:
			print >> sys.stderr, "ERROR: Could not import module 'pylibmc' - memcache is disabled. Please install the module and try again."
			self.pool = None
		except AttributeError:
			print >> sys.stderr, "ERROR: Could not connect to the memcache server '%s' as user '%s'. memcache is disabled.\
				Please check that the server is running, check your memcache environment variables, and try again."\
				% (os.environ.get(self.CACHE_SERVER_VAR), os.environ.get(self.CACHE_PASS_VAR))
			self.pool = None
		except TypeError, e:
			# thrown by pylibmc e.g. if the wrong password was supplied
			print >> sys.stderr, "ERROR: Could not connect to memcache server: '%s'. memcache is disabled." % (str(e))
			self.pool = None

	def __del__(self):
		"""Clean up resources"""
		if (self.pool != None):
			self.pool.relinquish()

	def get(self, key):
		"""Retrieve the value for a given key, or None if no key exists."""
		if (self.pool != None):
			with self.pool.reserve() as mc:
				try:
					return mc.get(str(key))
				except Exception as e:
					print >> sys.stderr, "cache get() error: '{0}'.".format(e)
		else:
			print >> sys.stderr, "Cache does not exist! Create it first"
			return None

	def set(self, key, data, expiry=CacheBase.CACHE_EXPIRY):
		"""Save the value to a given key name."""
		if (self.pool != None):
			with self.pool.reserve() as mc:
				try:
					mc.set(str(key), data, time=expiry)
				except Exception as e:
					print >> sys.stderr, "cache set() error: '{0}'.".format(e)
		else:
			print >> sys.stderr, "Cache does not exist! Create it first"


class Memcachier(Memcache):
	"""
	Cache data using memcachier (www.memcachier.com).
	"""

	# Memcachier is actually 'protocol-compliant' with memcached -
	# it has exactly the same interface except for the env vars

	CACHE_SERVER_VAR = 'MEMCACHIER_SERVERS'
	CACHE_USER_VAR = 'MEMCACHIER_USERNAME'
	CACHE_PASS_VAR = 'MEMCACHIER_PASSWORD'

	@classmethod
	def get_help(self):
		"""Tell the user how they can use this type of cache."""
		return super(Memcachier, self).get_help()

	def __init__(self):
		"""Connect to the memcachier server(s)."""
		return super(Memcachier, self).__init__()

	def __del__(self):
		"""Clean up resources"""
		return super(Memcachier, self).__del__()

	def get(self, key):
		"""Retrieve the value for a given key, or None if no key exists."""
		return super(Memcachier, self).get(key)

	def set(self, key, data, expiry):
		"""Save the value to a given key name."""
		return super(Memcachier, self).set(key, data, expiry)


class Redis(CacheBase):
	"""
	Cache data using redis.
	"""

	# the redis-py module nicely handles thread-safety for us,
	# so we don't have to do anything :)
	# https://github.com/andymccurdy/redis-py#thread-safety

	REDIS_URL = 'REDISTOGO_URL'

	@classmethod
	def get_help(self):
		"""Tell the user how they can use this type of cache."""
		return "Redis configuration is read from the environment variable '%s'." % (self.REDIS_URL)

	def __init__(self):
		"""Connect to the redis server(s)."""
		self.redis = None
		try:
			import redis
			#TODO: ALL INPUT IS EVIL
			#regex check these variables
			redis_url = os.getenv(self.REDIS_URL, 'redis://localhost')
			self.redis = redis.from_url(redis_url)
		except ImportError:
			print >> sys.stderr, "ERROR: Could not import module 'redis' - redis caching is disabled. Please install the module and try again."
			self.redis = None
		except Exception, e:
			# unfortunately, the redis library doesn't give us any details if the connection didn't work.
			print >> sys.stderr, "ERROR starting redis: '%s'. Is your redis URL '%s' correct? Redis caching is disabled." % (e, self.REDIS_URL)
			self.redis = None

	def get(self, key):
		"""Retrieve the value for a given key, or None if no key exists."""
		if (self.redis != None):
			try:
				return self.redis.get(key)
			except Exception, e:
				print >> sys.stderr, "redis get() error: '{0}'.".format(e)
		else:
			print >> sys.stderr, "ERROR: Redis cache does not exist! Create it first"
			return None

	def set(self, key, data, expiry=CacheBase.CACHE_EXPIRY):
		"""Save the value to a given key name."""
		if (self.redis != None):
			try:
				self.redis.set(key, data)
				self.redis.expire(key, expiry)
			except Exception, e:
				print >> sys.stderr, "redis set() error: '{0}'.".format(e)
		else:
			print >> sys.stderr, "ERROR: Redis cache does not exist! Create it first"


class Pycache(CacheBase):
	"""
	Cache data using RAM.
	"""

	CACHE_SIZE = "50" # megabytes

	@classmethod
	def get_help(cls):
		"""Tell the user how they can use this type of cache."""
		# TODO: quantify how many observation records this can store
		return "Size can be specified in Megabytes (M/MB) or Gigabytes (G/GB). \
			Megabytes is assumed if no unit is given. \
			Default size: " + cls.CACHE_SIZE + "MB."

	@classmethod
	def get_metavar(cls):
		"""
		Return the string that should be used for argparse's metavariable
		(i.e. the string that explains how to specify a cache size on the command line)
		"""
		return "CACHE_SIZE_INTEGER[M|MB|G|GB]"

	def __init__(self, cache_size=CACHE_SIZE):
		"""Create a cache using RAM."""
		self.cache = None

		import re

		# let the user specify sizes with the characters 'MB' or 'GB'
		if (re.search("[^0-9MGBmgb]+", cache_size) != None):
			raise ValueError("Invalid Pycache cache size '%s': use '%s'." %
				(str(cache_size), self.get_metavar()))

		if (re.search("[Mm]", cache_size) and re.search("[Gg]", cache_size)):
			raise ValueError("Invalid Pycache cache size '%s': " % (str(cache_size)) +
				"specify only one of MB and GB.")

		multiplier = 1024 * 1024 # convert to bytes

		if (re.search("[Gg]", cache_size)):
			multiplier *= 1024

		# remove non-numeric characters
		cache_size = cache_size.translate(None, 'MGBmgb')
		cache_size = int(cache_size)

		if (cache_size < 1):
			raise ValueError("Invalid Pycache cache size '%s': " % (str(cache_size)) +
				"cache must be at least 1MB.")

		cache_size *= multiplier

		try:
			from util import pycache
			self.cache = pycache
			pycache.set_cache_size(cache_size)
		except ImportError, e:
			print >> sys.stderr, "ERROR: Could not import module 'pycache': '%s'." % (e)
			self.cache = None
		except Exception, e:
			print >> sys.stderr, "ERROR creating cache in memory: '%s'." % (e)
			self.cache = None

	def get(self, key):
		"""Retrieve the value for a given key, or None if no key exists."""
		if (self.cache != None):
			try:
				return self.cache.get(key)
			except Exception, e:
				print >> sys.stderr, "pycache get() error: '{0}'.".format(e)
		else:
			print >> sys.stderr, "pycache get() error: cache does not exist! create it before retrieving values."
			return None

	def set(self, key, data, expiry=CacheBase.CACHE_EXPIRY):
		"""Save the value to a given key name."""
		if (self.cache != None):
			try:
				self.cache.set(key, data, expiry)
			except Exception, e:
				print >> sys.stderr, "pycache set() error: '{0}'.".format(e)
		else:
			print >> sys.stderr, "pycache set() error: cache does not exist! create it before setting values."
