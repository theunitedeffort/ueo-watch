#!/usr/bin/env python3

import argparse
import hashlib
import logging
import time

import minidb

class CacheEntry(minidb.Model):
    guid = str
    timestamp = int
    data = str
    tries = int
    etag = str

def get_guid(location):
  sha_hash = hashlib.new('sha1')
  sha_hash.update(location.encode('utf-8'))
  return sha_hash.hexdigest()

def remove_latest(db_path, location, count):
  guid = get_guid(location)
  logging.debug('guid for "%s" is %s' % (location, guid))
  if (count <= 0):
    raise ValueError('Specify a positive integer for --count.  given value: %d' % count)
  db = minidb.Store(db_path, debug=True, vacuum_on_close=True)
  db.register(CacheEntry)
  remove_ids = [row[0] for row in CacheEntry.query(
    db, CacheEntry.c.id, where=CacheEntry.c.guid == guid,
    order_by=CacheEntry.c.timestamp.desc, limit=count)]
  # If nothing's returned from the query, the given guid is not in the db
  # and no action is needed.
  result = 0
  if remove_ids:
    for remove_id in remove_ids:
      result += CacheEntry.delete_where(db, (CacheEntry.c.guid == guid) & (CacheEntry.c.id == remove_id))
  else:
    print('no entries for "%s"' % location)

  print('removed latest %d %s for "%s" from %s' % (result, 'entry' if result == 1 else 'entries', location, db_path))
  latest = [row[0] for row in CacheEntry.query(db, CacheEntry.c.timestamp,
    where=CacheEntry.c.guid == guid, order_by=CacheEntry.c.timestamp.desc,
    limit=1)]
  if latest:
    print('latest entry is currently from %s' % time.strftime('%a %b %d %I:%M:%S %p', time.localtime(latest[0])))
  db.commit()
  db.close()
  return result


def main():
  parser = argparse.ArgumentParser(description='Removes existing entries in the urlwatch database')
  parser.add_argument('location', help='location to modify (usually a URL)')
  parser.add_argument('--verbose', '-v', action='store_true', help="enable debug logging")
  parser.add_argument('--cache', default='cache.db', help='path to the urlwatch cache db file (default: cache.db)')
  parser.add_argument('--count', default=1, type=int, help='remove this many latest entries (default: 1)')

  args = parser.parse_args()
  if args.verbose:
    logging.basicConfig(level=logging.DEBUG, format='%(module)s %(levelname)s: %(message)s')

  remove_latest(args.cache, args.location, args.count)


if __name__ == '__main__':
  main()