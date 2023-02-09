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

import io
import logging
from struct import pack
from struct import unpack

import ZODB.broken
import ZODB.POSException
import ZODB.utils
from ZODB.blob import BlobStorage
from ZODB.Connection import TransactionMetaData
from ZODB.FileStorage import FileStorage
from ZODB.interfaces import IStorageCurrentRecordIteration
from ZODB.interfaces import IStorageIteration
from ZODB.interfaces import IStorageUndoable

import zodbupdate.serialize
import zodbupdate.utils


logger = logging.getLogger('zodbupdate')

TRANSACTION_COUNT = 100000


class Updater:
    """Access a storage and perform operations on all of its records.
    """

    def __init__(
            self, storage, dry=False, renames=None, decoders=None,
            start_at='0x00', debug=False, repickle_all=False,
            pickle_protocol=zodbupdate.utils.DEFAULT_PROTOCOL,
            encoding='ASCII'):
        self.dry = dry
        self.storage = storage
        self.processor = zodbupdate.serialize.ObjectRenamer(
            renames=renames,
            decoders=decoders,
            pickle_protocol=pickle_protocol,
            repickle_all=repickle_all,
            encoding=encoding,
        )
        self.start_at = start_at
        self.debug = debug

    def __new_transaction(self):
        t = TransactionMetaData()
        self.storage.tpc_begin(t)
        t.note('Updated factory references using `zodbupdate`.')
        return t

    def __commit_transaction(self, t, changed, commit_count):
        if self.dry or not changed:
            logger.info(
                'Dry run selected or no changes, '
                'aborting transaction. (#{})'.format(commit_count))
            self.storage.tpc_abort(t)
        else:
            logger.info(f'Committing changes (#{commit_count}).')
            self.storage.tpc_vote(t)
            self.storage.tpc_finish(t)

    def __call__(self):
        commit_count = 0
        try:
            record_count = 0
            t = self.__new_transaction()

            for oid, serial, current in self.records:
                logger.debug('Processing OID {}'.format(
                    ZODB.utils.oid_repr(oid)))

                new = self.processor.rename(current)
                if new is None:
                    continue

                logger.debug('Updated OID {}'.format(
                    ZODB.utils.oid_repr(oid)))
                self.storage.store(oid, serial, new.getvalue(), '', t)
                record_count += 1

                if record_count > TRANSACTION_COUNT:
                    record_count = 0
                    commit_count += 1
                    self.__commit_transaction(t, True, commit_count)
                    t = self.__new_transaction()

            commit_count += 1
            self.__commit_transaction(t, record_count != 0, commit_count)
        except Exception as error:
            if not self.debug:
                raise
            import pdb
            import sys
            (type, value, traceback) = sys.exc_info()
            pdb.post_mortem(traceback)
            del traceback
            raise error

    @property
    def records(self):
        next = ZODB.utils.repr_to_oid(self.start_at)
        storage = self.storage
        # If we've got a BlobStorage wrapper, let's
        # actually iterate through the storage it wraps.
        if isinstance(storage, BlobStorage):
            storage = storage._BlobStorage__storage
        if isinstance(storage, FileStorage):
            # Custom iterator for FileStorage. This is used to be able
            # to recover form a POSKey error.
            index = storage._index

            while True:
                oid = index.minKey(next)
                try:
                    data, tid = storage.load(oid, "")
                except ZODB.POSException.POSKeyError as e:
                    logger.error(
                        'Warning: Jumping record {}, '
                        'referencing missing key in database: {}'.format(
                            ZODB.utils.oid_repr(oid), str(e)))
                else:
                    yield oid, tid, io.BytesIO(data)

                oid_as_long, = unpack(">Q", oid)
                next = pack(">Q", oid_as_long + 1)
                try:
                    next = index.minKey(next)
                except ValueError:
                    # No more records
                    break
        elif IStorageCurrentRecordIteration.providedBy(storage):
            # Second best way to iterate through the lastest records.
            while True:
                oid, tid, data, next = storage.record_iternext(next)
                yield oid, tid, io.BytesIO(data)
                if next is None:
                    break
        elif (IStorageIteration.providedBy(storage) and
              (not IStorageUndoable.providedBy(storage) or
               not storage.supportsUndo())):
            # If we can't iterate only through the recent records,
            # iterate on all. Of course doing a pack before help :).
            for transaction_ in storage.iterator():
                for rec in transaction_:
                    yield rec.oid, rec.tid, io.BytesIO(rec.data)
        else:
            raise SystemExit(
                "Don't know how to iterate through this storage type")
