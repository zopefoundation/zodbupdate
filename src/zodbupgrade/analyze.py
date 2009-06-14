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


class MissingClasses(ValueError):
    pass


def update_factory_references(op, arg):
    """Check a pickle operation for moved or missing factory references.

    Returns an updated (op, arg) tuple using the canonical reference for the
    factory as would be created if the pickle was unpickled and re-pickled.

    """
    if op.code not in 'ci':
        return

    factory_module, factory_name = arg.split(' ')
    module = __import__(factory_module, globals(), {}, [factory_name])
    factory = getattr(module, factory_name)
    # XXX Handle missing factories

    if not hasattr(factory, '__name__'):
        logger.warn(
            "factory %r does not have __name__: "
            "can't check canonical location" % factory)
        return
    if not hasattr(factory, '__module__'):
        # TODO: This case isn't covered with a test. I just
        # couldn't provoke a factory to not have a __module__ but
        # users reported this issue to me.
        logger.warn(
            "factory %r does not have __module__: "
            "can't check canonical location" % factory)
        return

    # XXX Log for later reuse
    new_arg = '%s %s' % (factory.__module__, factory.__name__)
    return op, new_arg


def each_record(storage):
    next = None
    while True:
        oid, tid, data, next = storage.record_iternext(next)
        yield StringIO.StringIO(data)
        if next is None:
            break


def update_storage(storage):
    """Update 
    and updaAnalyzes class references of current records of a storage.

    Look for missing or moved classes and return a list of OIDs that need
    updating, a list of classes that are missing, and a list of rewrites.

    """
    logger.info('Analyzing database ...')
    for count, data in enumerate(each_record(storage)):
        if not count % 5000:
            logger.info('    %s objects' % count)

        # ZODB records consist of two concatenated pickles, so the following
        # needs to be done twice:
        for i in range(2):
            zodbupgrade.picklefilter.filter(
                update_factory_references, pickle_data)

    logger.info('    Analyzation completed.')


def update_storage(storage, ignore_missing=False, dry=False):
    missing_classes, rewrites_found, oids = analyze_storage(storage)
    if missing_classes and not ignore_missing:
        raise MissingClasses(missing_classes)

    if rewrites_found:
        logger.info("Found moved classes:")
    for (old_mod, old_name), (new_mod, new_name) in rewrites_found.items():
        logger.info("%s.%s -> %s.%s" % (old_mod, old_name, new_mod, new_name))
    logger.info("%i objects need updating" % len(oids))

    if dry:
        logger.info('Dry run selected, aborting.')
        return

    logger.info('Starting database update')
    db = DB(storage)
    connection = db.open()
    for oid in oids:
        obj = connection.get(oid)
        obj._p_changed = True
    t = transaction.get()
    t.note('Class references updated by `zodbupgrade`')
    transaction.commit()
    db.close()
    logger.info('Database update completed')
