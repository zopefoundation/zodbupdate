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
import sys
import zodbupgrade.analyze


parser = optparse.OptionParser(
    description="Updates all references to classes to their canonical location.")
parser.add_option("-f", "--file",
                  help="load FileStorage")
parser.add_option("-c", "--config",
                  help="load storage from config file")
parser.add_option("-n", "--dry-run", action="store_true",
                  help="perform a trial run with no changes made")
parser.add_option("--ignore-missing", action="store_true",
                  help="update database even if classes are missing")
parser.add_option("-q", "--quiet", action="store_true",
                  help="suppress non-error messages")

def main():
    options, args = parser.parse_args()

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

    if options.quiet:
        level = logging.ERROR
    else:
        level = logging.INFO
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger().setLevel(level)

    upgrader = zodbupgrade.analyze.Upgrader(storage)
    upgrader()
