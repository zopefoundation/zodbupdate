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
import zodbupdate.convert
import zodbupdate.update
import zodbupdate.utils
import six

logger = logging.getLogger('zodbupdate')


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


def load_renames():
    renames = {}
    for entry_point in pkg_resources.iter_entry_points('zodbupdate'):
        definition = entry_point.load()
        for old, new in definition.items():
            renames[tuple(old.split(' '))] = tuple(new.split(' '))
        logger.info('Loaded {} rename rules from {}:{}'.format(
            len(definition), entry_point.module_name, entry_point.name))
    return renames


def create_updater(
        storage,
        default_renames=None,
        default_decoders=None,
        start_at=None,
        convert_py3=False,
        dry_run=False,
        debug=False):
    if not start_at:
        start_at = '0x00'

    decoders = {}
    if default_decoders:
        decoders.update(default_decoders)
    renames = load_renames()
    if default_renames:
        renames.update(default_renames)
    repickle_all = False
    pickle_protocol = zodbupdate.utils.DEFAULT_PROTOCOL
    if convert_py3:
        pickle_protocol = 3
        repickle_all = True
        decoders.update(zodbupdate.convert.load_decoders())
        renames.update(zodbupdate.convert.default_renames())
        if six.PY3:
            raise AssertionError(
                'You can only convert a database to Python 3 format '
                'from Python 2.')

    return zodbupdate.update.Updater(
        storage,
        dry=dry_run,
        renames=renames,
        decoders=decoders,
        start_at=start_at,
        debug=debug,
        repickle_all=repickle_all,
        pickle_protocol=pickle_protocol)


def format_renames(renames):
    formatted = {}
    for old, new in renames.items():
        formatted[' '.join(old)] = ' '.join(new)
    if not formatted:
        return ''
    return pprint.pformat(formatted)


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
    logger.addFilter(duplicate_filter)

    if options.file and options.config:
        raise AssertionError(
            'Exactly one of --file or --config must be given.')

    if options.file:
        storage = ZODB.FileStorage.FileStorage(options.file)
    elif options.config:
        with open(options.config) as config:
            storage = ZODB.config.storageFromFile(config)
    else:
        raise AssertionError(
            'Exactly one of --file or --config must be given.')

    updater = create_updater(
        storage,
        start_at=options.oid,
        convert_py3=options.convert_py3,
        dry_run=options.dry_run,
        debug=options.debug)
    try:
        updater()
    except Exception as error:
        logging.info('An error occured', exc_info=True)
        logging.error('Stopped processing, due to: {}'.format(error))
        raise AssertionError()

    implicit_renames = format_renames(
        updater.processor.get_rules(implicit=True))
    if implicit_renames:
        logger.info('Found new rules: {}'.format(implicit_renames))
    if options.save_renames:
        logger.info('Saving rules into {}'.format(options.save_renames))
        with open(options.save_renames, 'w') as output:
            output.write('renames = {}'.format(
                format_renames(updater.processor.get_rules(
                    implicit=True, explicit=True))))
    if options.pack:
        logger.info('Packing storage ...')
        storage.pack(time.time(), ZODB.serialize.referencesf)
    storage.close()

    if options.convert_py3 and not options.dry_run:
        zodbupdate.convert.update_magic_data_fs(options.file)
