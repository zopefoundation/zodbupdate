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

import ZODB.FileStorage
import ZODB.config
import ZODB.serialize
import logging
import optparse
import pkg_resources
import pprint
import time
import zodbupdate.update
import zodbupdate.utils
import six


parser = optparse.OptionParser(
    description=("Updates all references to classes to "
                 "their canonical location."))
parser.add_option(
    "-f", "--file",
    help="load FileStorage")
parser.add_option(
    "-c", "--config",
    help="load storage from config file")
parser.add_option(
    "-n", "--dry-run", action="store_true",
    help="perform a trial run with no changes made")
parser.add_option(
    "-s", "--save-renames",
    help="save automatically determined rename rules to file")
parser.add_option(
    "-q", "--quiet", action="store_true",
    help="suppress non-error messages")
parser.add_option(
    "-v", "--verbose", action="store_true",
    help="more verbose output")
parser.add_option(
    "-o", "--oid",
    help="start with provided oid in hex format, ex: 0xaa1203")
parser.add_option(
    "-d", "--debug", action="store_true",
    help="post mortem pdb on failure")
parser.add_option(
    "--pack", action="store_true", dest="pack",
    help=("pack the storage when done. use in conjunction of -c "
          "if you have blobs storage"))
parser.add_option(
    "--convert-py3", action="store_true",  dest="convert_py3",
    help="convert pickle format to protocol 3 and adjust bytes")


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

    start_at = '0x00'
    if options.oid:
        start_at = options.oid

    rename_rules = {}
    for entry_point in pkg_resources.iter_entry_points('zodbupdate'):
        rules = entry_point.load()
        rename_rules.update(rules)
        logging.info(
            'Loaded %s rules from %s:%s' %
            (len(rules), entry_point.module_name, entry_point.name))

    updater = zodbupdate.update.Updater(
        storage,
        dry=options.dry_run,
        renames=rename_rules,
        start_at=start_at,
        debug=options.debug,
        convert_py3=options.convert_py3)

    try:
        updater()
    except Exception as error:
        logging.error('An error occured', exc_info=True)
        logging.error('Stopped processing, due to: {}'.format(error))
        raise SystemExit()

    implicit_renames = updater.processor.get_found_implicit_rules()
    if implicit_renames:
        print('Found new rules:')
        print(pprint.pformat(implicit_renames))
    if options.save_renames:
        print('Saving rules into %s' % options.save_renames)
        rename_rules.update(implicit_renames)
        f = open(options.save_renames, 'w')
        f.write('renames = %s' % pprint.pformat(rename_rules))
        f.close()
    if options.pack:
        print('Packing storage ...')
        storage.pack(time.time(), ZODB.serialize.referencesf)
    storage.close()

    if options.convert_py3:
        if six.PY3:
            print("You are already in python 3.")
        elif not options.file:
            print("We do not know the database file so "
                  "we do not change the magic marker.")
        else:
            print("Updating magic marker for {}".format(options.file))
            with open(options.file, 'r+b') as data_fs:
                # Override the magic.
                data_fs.write('FS30')
