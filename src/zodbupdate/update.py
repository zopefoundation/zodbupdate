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
import logging
import pickle
import pickletools
import sys
import transaction
import zodbupdate.picklefilter

logger = logging.getLogger('zodbupdate')


class Updater(object):
    """Update class references for all current objects in a storage."""

    def __init__(self, storage, dry=False, ignore_missing=False):
        self.ignore_missing = ignore_missing
        self.dry = dry
        self.storage = storage
        self.missing = set()
        self.renames = {}

    def __call__(self):
        t = transaction.Transaction()
        self.storage.tpc_begin(t)
        t.note('Updated factory references using `zodbupdate`.')

        for oid, serial, current in self.records:
            new = self.update_record(current)
            if new == current:
                continue
            logger.debug('Updated %s' % ZODB.utils.oid_repr(oid))
            self.storage.store(oid, serial, new, '', t)

        if self.dry:
            logger.info('Dry run selected, aborting transaction.')
            self.storage.tpc_abort(t)
        else:
            logger.info('Committing changes.')
            self.storage.tpc_vote(t)
            self.storage.tpc_finish(t)

    @property
    def records(self):
        next = None
        while True:
            oid, tid, data, next = self.storage.record_iternext(next)
            yield oid, tid, StringIO.StringIO(data)
            if next is None:
                break

    def update_record(self, old):
        new = ''
        for i in range(2):
            # ZODB data records consist of two concatenated pickles, so the
            # following needs to be done twice:
            new += zodbupdate.picklefilter.filter(
                self.update_operation, old)
        return new

    def update_operation(self, code, arg):
        """Check a pickle operation for moved or missing factory references.

        Returns an updated (code, arg) tuple using the canonical reference for the
        factory as would be created if the pickle was unpickled and re-pickled.

        """
        if code not in 'ci':
            return

        if arg in self.renames:
            # XXX missing testcase
            return code, self.renames[arg]

        factory_module, factory_name = arg.split(' ')
        try:
            module = __import__(factory_module, globals(), {}, [factory_name])
            factory = getattr(module, factory_name)
        except (AttributeError, ImportError):
            name = '%s.%s' % (factory_module, factory_name)
            message = 'Missing factory: %s' % name
            logger.info(message)
            self.missing.add(name)
            if self.ignore_missing:
                return
            raise ValueError(message)

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

        new_arg = '%s %s' % (factory.__module__, factory.__name__)
        if new_arg != arg:
            self.renames[arg] = new_arg
        return code, new_arg
