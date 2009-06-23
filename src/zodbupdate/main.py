##############################################################################
#
# Copyright (c) 2009 Zope Corporation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################

import ZODB.config
import ZODB.FileStorage
import logging
import optparse
import pkg_resources
import pprint
import sys
import zodbupdate.update


parser = optparse.OptionParser(
    description="Updates all references to classes to their canonical location.")
parser.add_option("-f", "--file",
                  help="load FileStorage")
parser.add_option("-c", "--config",
                  help="load storage from config file")
parser.add_option("-n", "--dry-run", action="store_true",
                  help="perform a trial run with no changes made")
parser.add_option("-i", "--ignore-missing", action="store_true",
                  help="update database even if classes are missing")
parser.add_option("-s", "--save-renames",
                  help="save automatically determined rename rules to file")
parser.add_option("-q", "--quiet", action="store_true",
                  help="suppress non-error messages")
parser.add_option("-v", "--verbose", action="store_true",
                  help="more verbose output")

class DuplicateFilter(object):

    def __init__(self):
        self.seen = set()

    def filter(self, record):
        if record.msg in self.seen:
            return False
        self.seen.add(record.msg)
        return True

duplicate_filter = DuplicateFilter()


def main():
    options, args = parser.parse_args()

    if options.quiet:
        level = logging.ERROR
    elif options.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger().setLevel(level)
    logging.getLogger('zodbupdate').addFilter(duplicate_filter)

    if options.file and options.config:
        raise SystemExit(
            'Exactly one of --file or --config must be given.')

    if options.file:
        storage = ZODB.FileStorage.FileStorage(options.file)
    elif options.config:
        storage = ZODB.config.storageFromURL(options.config)
    else:
        raise SystemExit(
            'Exactly one of --file or --config must be given.')

    rename_rules = {}
    for entry_point in pkg_resources.iter_entry_points('zodbupdate'):
        rules = entry_point.load()
        rename_rules.update(rules)
        logging.debug('Loaded %s rules from %s:%s' %
                      (len(rules), entry_point.module_name, entry_point.name))

    updater = zodbupdate.update.Updater(
        storage, dry=options.dry_run,
        ignore_missing=options.ignore_missing,
        renames=rename_rules)
    try:
        updater()
    except Exception, e:
        logging.debug('An error occured', exc_info=True)
        logging.error('Stopped processing, due to: %s' % e)
        raise SystemExit()

    if options.save_renames:
        f = open(options.save_renames, 'w')
        f.write('renames = %s' % pprint.pformat(updater.renames))
        f.close()
