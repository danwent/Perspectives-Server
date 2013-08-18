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
Cache and retrieve data in key-value pairs using RAM only.

When the cache reaches maximum size entries are discarded in
'least recently used' order.

This module does not preemptively reserve memory from the OS;
additional memory is only acquired as needed.
Make sure you have enough memory to use the cache you request!
"""

# Use a module so python can ensure there is only one cache regardless of threads.
# Note this doesn't allow inheritance; if we need that we will need to refactor.

import heapq
import itertools
import sys
import threading
import time

# Note: the maximum cache size applies only to stored data;
# the internal structures used to for implementation will cause pycache
# to use slightly more memory.
DEFAULT_CACHE_SIZE = 50 * 1024 * 1024 # bytes


class CacheEntry(object):
	"""Store data for a given entry in the cache."""

	def __init__(self, key, data, expiry):
		"""Create new cache entry."""

		if (expiry < 1):
			raise ValueError("CacheEntry expiry values must be positive")

		now = int(time.time())

		self.key = key
		self.data = data
		self.expiry = now + expiry
		self.memory_used = sys.getsizeof(data)

		# count the key as having been requested just now, so it is not immediately removed.
		# this is usually correct, as the caller will likely have just retrieved or calculated
		# the data before calling us to store it.
		# this also prevents thrashing so new entries are not rapidly added and then removed from the heap.
		self.last_requested = now

	def update_request_time(self):
		"""Update the most recent request time for this cache entry."""
		self.last_requested = int(time.time())

	def has_expired(self):
		"""Returns true if this entry has expired; false otherwise."""
		if (self.expiry < int(time.time())):
			return True
		return False


class Heap(object):
	"""Store CacheEntries in a heap.
	Entries are stored in 'least recently used' order
	so we know what to remove when we run out of space."""

	# This is a wrapper class to allow use of the heapq module in an Object-Oriented way,
	# and to contain the logic for our priority queue.
	# The heap does not store the cached data; it is only used to track the 'least recently used' order
	# so cache entries can be removed when we need space.

	# This heap uses lazy deletion - entries are not deleted immediately, as we don't want
	# to spend time traversing and re-creating the heap each time.
	# Instead entries are marked for deletion and removed when they are encountered via popping.

	# Performance Note:
	# We could add checks to recreate the heap list if old entries are taking up too much space,
	# but with keys expiring it should be fine for now.
	# We could also add a check to see if the counter has grown too large, but iterators use
	# an infinite stream, so it shouldn't be necessary.

	def __init__(self):
		"""Create a new heap."""
		self.heap = []
		self.current_entries = {}
		self.counter = itertools.count()

	def __len__(self):
		"""Return the number of items in the heap."""
		return len(self.heap)

	def __del__(self):
		"""Delete the heap."""
		del self.heap
		del self.current_entries

	def clear(self):
		"""Remove all items from the heap."""
		self.current_entries.clear()
		del self.heap
		self.heap = []

	def push(self, cache_entry):
		"""Add an entry onto the heap."""
		# use an iterator to break ties if multiple keys are added in the same second;
		# this ensures tuple comparison works in python 3.
		# credit for this idea goes to the python docs -
		# http://docs.python.org/2/library/heapq.html
		entry_id = next(self.counter)

		heap_entry = [cache_entry.last_requested, entry_id, cache_entry.key]
		self.current_entries[cache_entry.key] = entry_id
		heapq.heappush(self.heap, heap_entry)

	def update(self, cache_entry):
		"""Update the value of a heap entry."""
		# this is a convenience function to make it easier to understand what's happening.
		# entries are not actually updated in-place (that takes too long);
		# instead a new entry is created and the current one marked for lazy deletion later
		# (the entry is 'marked' for deletion by replacing the entry_id for that key in current_entries)
		self.push(cache_entry)

	def pop(self):
		"""Remove the least recently used heap entry."""
		while self.heap:
			last_requested, entry_id, key = heapq.heappop(self.heap)
			if (key in self.current_entries and (self.current_entries[key] == entry_id)):
				del self.current_entries[key]
				return key
			# otherwise the element we just popped is either expired or an old junk entry;
			# discard it and continue.
		raise IndexError("Heap has no entries to pop")

	def remove(self, cache_entry):
		"""Remove the entry from the heap."""
		# a convenience function: entries are not removed immediately but marked for lazy deletion.
		if cache_entry.key in self.current_entries:
			del self.current_entries[cache_entry.key]
		# else: don't worry - some other thread might have removed the entry just before us.


def __free_memory(mem_needed):
	"""Remove entries from the heap and cache until we have enough free memory."""
	global current_mem
	global max_mem

	with mem_lock:
		while heap and (current_mem + mem_needed > max_mem):
			key = heap.pop()
			if key in cache:
				# naive implementation - we don't worry about discarding a non-expired item
				# before all expired items are gone.
				# we just want to clear *some* memory for the new item as fast as possible.
				# if this really hurts performance we could refactor.
				__delete_key(key)
			else:
				raise KeyError("The heap key '%s' does not exist in the cache and cannot be removed." % (key))


def __delete_key(key):
	"""Remove this entry from the cache."""
	global current_mem

	with mem_lock:
		current_mem -= cache[key].memory_used
		del cache[key]


def set_cache_size(size):
	"""Set the maximum amount of RAM to use, in bytes."""
	size = int(size)
	if size > 0:
		with mem_lock:
			global max_mem
			max_mem = size


def get_cache_size():
	"""Return the current total memory being used, in bytes."""
	return current_mem


def get_cache_count():
	"""Return the current number of entries in the cache."""
	return len(cache)


def clear():
	"""Delete all entries from the cache."""
	global current_mem

	with mem_lock:
		cache.clear()
		heap.clear()
		current_mem = 0


def set(key, data, expiry):
	"""Save the value to a given key."""
	global current_mem
	global max_mem

	with set_lock:
		if key in set_threads:
			# some other thread is already updating the value for this key.
			# don't compete or waste time calculating a possibly duplicate value
			return
		else:
			set_threads[key] = True

	try:
		entry = CacheEntry(key, data, expiry)

		if (entry.memory_used > max_mem):
			print >> sys.stderr, "ERROR: cannot store data for '%s' - it's larger than the max cache size (%s bytes)\n" \
				% (key, max_mem)
			return

		with mem_lock:

			# add/replace the entry in the hash;
			# this tracks whether we have the key at all.
			if entry.key in cache:
				current_mem -= cache[key].memory_used # subtract the memory we gain back

			if (current_mem + entry.memory_used > max_mem):
				__free_memory(entry.memory_used)

			heap.push(entry)
			cache[key] = entry
			current_mem += entry.memory_used

	finally:
		del set_threads[key]


def get(key):
	"""Retrieve the value for a given key, or None if no key exists."""
	if key not in cache:
		return None

	if (cache[key].has_expired()):
		heap.remove(cache[key])
		__delete_key(key)
		return None

	cache[key].update_request_time()
	heap.update(cache[key])

	return cache[key].data



# Use a dictionary to efficiently store/retrieve data
# and a heap to maintain a 'least recently used' order.
cache = {}
heap = Heap()

current_mem = 0 # bytes
max_mem = DEFAULT_CACHE_SIZE


# we don't care if we get a slightly out of date value when retrieving,
# but prevent multiple set() calls from writing data for the same key at the same time.
set_threads = {}
set_lock = threading.Lock()

# prevent multiple threads from altering memory counts at the same time
mem_lock = threading.RLock()
