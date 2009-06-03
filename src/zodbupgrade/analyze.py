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

from ZODB.DB import DB
import StringIO
import ZODB.broken
import ZODB.utils
import pickle
import pickletools
import sys
import transaction
import logging

logger = logging.getLogger('zodbupgrade')


SAFE_OPS = 'IJKML\x8a\x8bSTUN\x88\x89VXFG]ael)t\x85\x86\x87}dsu02(1ghjpqrRbo\x81\x80.PQ'
KNOWN_HARD = 'ci'


def find_factory_references(pickle):
    """Analyze a pickle for moved or missing factory references.

    Returns: 

        - factories whose dotted name could be imported but stem from an
          indirect import (this is a dictionary)

        - factories whose dotted name could not be imported (an iterable)

    """
    missing_factories = set()
    rewrites_found = dict()
    for op, arg, pos in pickletools.genops(pickle):
        if op.code in SAFE_OPS:
            continue
        elif op.code in KNOWN_HARD:
            module_name, symbol = arg.split(' ')
            try:
                module = __import__(module_name, globals(), {}, [symbol])
                factory = getattr(module, symbol)
            except (ImportError, AttributeError):
                missing_factories.add('%s.%s' % (module_name, symbol))
            else:
                if not hasattr(factory, '__name__'):
                    logger.warn(
                        "factory %r does not have __name__, can't check canonical location" % factory)
                    continue
                if not hasattr(factory, '__module__'):
                    # TODO: This case isn't covered with a test. I just
                    # couldn't provoke a factory to not have a __module__ but
                    # users reported this issue to me.
                    logger.warn(
                        "factory %r does not have __module__, can't check canonical location" % factory)
                    continue
                if ((factory.__module__, factory.__name__) !=
                    (module_name, symbol)):
                    # The factory is reachable but it's not the
                    # canonical location. Mark object for updating.
                    rewrites_found[(module_name, symbol)] = (
                        factory.__module__, factory.__name__)
        else:
            raise ValueError('Unknown pickle opcode %r' % op.code)
    return rewrites_found, missing_factories


def analyze_storage(storage):
    """Analyzes class references of current records of a storage.

    Look for missing or moved classes and return a list of OIDs that need
    updating, a list of classes that are missing, and a list of rewrites.

    """
    missing_classes = set()
    rewrites_found = dict()
    oids_rewrite = set()

    count = 0
    next = None
    while True:
        oid, tid, data, next = storage.record_iternext(next)
        count += 1
        pickle_data = StringIO.StringIO(data)

        if not count % 5000:
            logger.info(
                'Analyzed %i objects. Found %i moved classes and %i missing '
                'classes so far.' % (count, len(rewrites_found), len(missing_classes)))

        # ZODB records consist of two concatenated pickles, so the following
        # needs to be done twice:
        for i in range(2):
            r, m = find_factory_references(pickle_data)
            if r:
                oids_rewrite.add(oid)
            rewrites_found.update(r)
            missing_classes.update(m)

        if next is None:
            break
    return missing_classes, rewrites_found, oids_rewrite


def update_storage(storage):
    missing_classes, rewrites_found, oids = analyze_storage(storage)
    if missing_classes:
        raise ValueError(missing_classes)

    logger.info("Rewriting database with mapping:")
    for (old_mod, old_name), (new_mod, new_name) in rewrites_found.items():
        logger.info("%s.%s -> %s.%s" % (old_mod, old_name, new_mod, new_name))
    logger.info("%i objects need rewriting" % len(oids))

    db = DB(storage)
    connection = db.open()
    for oid in oids:
        obj = connection.get(oid)
        obj._p_changed = True
    t = transaction.get()
    t.note('Class references updated by `zodbupgrade`')
    transaction.commit()
    db.close()
