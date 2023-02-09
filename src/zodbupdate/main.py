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

import argparse
import logging
import pprint
import time

import pkg_resources

import ZODB.config
import ZODB.FileStorage
import ZODB.serialize

import zodbupdate.convert
import zodbupdate.update
import zodbupdate.utils


logger = logging.getLogger('zodbupdate')


parser = argparse.ArgumentParser(
    description=("Updates all references to classes to "
                 "their canonical location."))
exclusive_group = parser.add_mutually_exclusive_group()
exclusive_group.add_argument(
    "-f", "--file",
    help="load FileStorage")
exclusive_group.add_argument(
    "-c", "--config",
    help="load storage from config file")
parser.add_argument(
    "-n", "--dry-run", action="store_true",
    help="perform a trial run with no changes made")
parser.add_argument(
    "-s", "--save-renames",
    help="save automatically determined rename rules to file")
parser.add_argument(
    "-q", "--quiet", action="store_true",
    help="suppress non-error messages")
parser.add_argument(
    "-v", "--verbose", action="store_true",
    help="more verbose output")
parser.add_argument(
    "-o", "--oid",
    help="start with provided oid in hex format, ex: 0xaa1203")
parser.add_argument(
    "-d", "--debug", action="store_true",
    help="post mortem pdb on failure")
parser.add_argument(
    "--pack", action="store_true", dest="pack",
    help=("pack the storage when done. use in conjunction of -c "
          "if you have blobs storage"))
parser.add_argument(
    "--convert-py3", action="store_true", dest="convert_py3",
    help="convert pickle format to protocol 3 and adjust bytes")
parser.add_argument(
    '--encoding', dest="encoding",
    help="used for decoding pickled strings in py3"
)
parser.add_argument(
    '--encoding-fallback',
    dest="encoding_fallbacks",
    nargs="*",
    help="Older databases may have other encoding stored than 'utf-8', like"
    " latin1. If an encoding error occurs, fallback to the given encodings "
    "and issue a warning.",
)


class DuplicateFilter:

    def __init__(self):
        self.reset()

    def filter(self, record):
        if record.msg in self.seen:
            return False
        self.seen.add(record.msg)
        return True

    def reset(self):
        self.seen = set()


duplicate_filter = DuplicateFilter()


def setup_logger(verbose=False, quiet=False, handler=None):
    logging.getLogger('zodbupdate.serialize').addFilter(duplicate_filter)
    if quiet:
        level = logging.ERROR
    elif verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO
    if handler is None:
        handler = logging.StreamHandler()
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger


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
        encoding=None,
        encoding_fallbacks=None,
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
        decoders.update(
            zodbupdate.convert.load_decoders(
                encoding_fallbacks=encoding_fallbacks
            )
        )
        renames.update(zodbupdate.convert.default_renames())

    return zodbupdate.update.Updater(
        storage,
        dry=dry_run,
        renames=renames,
        decoders=decoders,
        start_at=start_at,
        debug=debug,
        repickle_all=repickle_all,
        pickle_protocol=pickle_protocol,
        encoding=encoding,
    )


def format_renames(renames):
    formatted = {}
    for old, new in renames.items():
        formatted[' '.join(old)] = ' '.join(new)
    if not formatted:
        return ''
    return pprint.pformat(formatted)


def main():
    args = parser.parse_args()

    setup_logger(quiet=args.quiet, verbose=args.verbose)

    if args.file and args.config:
        raise AssertionError(
            'Exactly one of --file or --config must be given.')

    # Magic bytes need to be at the beginning so that FileStorage
    # doesn't complain.
    if args.convert_py3 and not args.dry_run:
        zodbupdate.convert.update_magic_data_fs(args.file)
    elif args.convert_py3 and args.dry_run:
        zodb_magic = zodbupdate.utils.get_zodb_magic(args.file)
        if zodb_magic != ZODB.FileStorage.packed_version:
            raise SystemExit(
                'You cannot use --dry-run under Python 3 with a ZODB '
                'created under Python 2 as --dry-run does not rewrite the '
                'magic header data before opening the ZODB file.')

    if args.file:
        storage = ZODB.FileStorage.FileStorage(args.file)
    elif args.config:
        with open(args.config) as config:
            storage = ZODB.config.storageFromFile(config)
    else:
        raise AssertionError(
            'Exactly one of --file or --config must be given.')

    updater = create_updater(
        storage,
        start_at=args.oid,
        convert_py3=args.convert_py3,
        encoding=args.encoding,
        encoding_fallbacks=args.encoding_fallbacks,
        dry_run=args.dry_run,
        debug=args.debug)
    try:
        updater()
    except Exception as error:
        logging.info('An error occured', exc_info=True)
        logging.error(f'Stopped processing, due to: {error}')
        raise AssertionError()

    implicit_renames = format_renames(
        updater.processor.get_rules(implicit=True))
    if implicit_renames:
        logger.info(f'Found new rules: {implicit_renames}')
    if args.save_renames:
        logger.info(f'Saving rules into {args.save_renames}')
        with open(args.save_renames, 'w') as output:
            output.write('renames = {}'.format(
                format_renames(updater.processor.get_rules(
                    implicit=True, explicit=True))))
    if args.pack:
        logger.info('Packing storage ...')
        storage.pack(time.time(), ZODB.serialize.referencesf)
    storage.close()
