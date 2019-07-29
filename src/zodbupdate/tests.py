# encoding=utf-8
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

import logging
import os
import shutil
import sys
import tempfile
import types
import unittest
from contextlib import contextmanager

import ZODB
import ZODB.blob
import ZODB.broken
import ZODB.FileStorage
import persistent
import six
import transaction
import zope.interface

import zodbupdate.main
import zodbupdate.serialize


class TestsBasics(unittest.TestCase):
    """Basic tests without the need of mocked or integrated code
    """

    def test_decode_attribute(self):
        from zodbupdate.convert import decode_attribute
        test_string = u'Hellö World'

        # 1.1) with utf8 encoding and no fallbacks, input is utf8
        decoder = decode_attribute(
            attribute='testattr',
            encoding='utf8',
            encoding_fallbacks=[]
        )
        test_data = {
            'testattr': test_string.encode('utf8')
        }
        self.assertTrue(decoder(data=test_data))
        self.assertEqual(test_data['testattr'], test_string)
        # 1.2) with utf8 encoding and no fallbacks, input is latin1: fails
        test_data = {
            'testattr': test_string.encode('latin1')
        }
        with self.assertRaises(UnicodeDecodeError):
            decoder(data=test_data)

        # 2.1) with utf8 encoding and 2 fallbacks, first fails too, input is utf8
        decoder = decode_attribute(
            attribute='testattr',
            encoding='utf8',
            encoding_fallbacks=['utf_7', 'latin1']
        )
        test_data = {
            'testattr': test_string.encode('utf8')
        }
        self.assertTrue(decoder(data=test_data))
        self.assertEqual(test_data['testattr'], test_string)
        # 2.2) as 2.1, but input is latin1
        test_data = {
            'testattr': test_string.encode('latin1')
        }
        self.assertTrue(decoder(data=test_data))
        self.assertEqual(test_data['testattr'], test_string)


class TestLogHandler(object):
    level = logging.DEBUG

    def __init__(self, msg_lst):
        self.msg_lst = msg_lst

    def handle(self, record):
        if record.name == 'zodbupdate.serialize':
            self.msg_lst.append(record.msg)


class Tests(unittest.TestCase):

    def setUp(self):
        self.log_messages = []
        self.log_handler = TestLogHandler(self.log_messages)
        self.logger = zodbupdate.main.setup_logger(handler=self.log_handler)

        sys.modules['module1'] = types.ModuleType('module1')
        sys.modules['module1.interfaces'] = types.ModuleType(
            'module1.interfaces')
        sys.modules['module2'] = types.ModuleType('module2')
        sys.modules['module2.interfaces'] = types.ModuleType(
            'module2.interfaces')

        class IFactory(zope.interface.Interface):
            pass

        class IOtherFactory(zope.interface.Interface):
            pass

        class Data(object):
            pass

        class OldData:
            pass

        class Factory(persistent.Persistent):
            pass

        class OtherFactory(persistent.Persistent):
            pass

        sys.modules['module1'].Factory = Factory
        Factory.__module__ = 'module1'
        sys.modules['module1'].Data = Data
        Data.__module__ = 'module1'
        sys.modules['module1'].OldData = OldData
        OldData.__module__ = 'module1'
        sys.modules['module1'].interfaces = sys.modules['module1.interfaces']
        sys.modules['module1.interfaces'].IFactory = IFactory
        IFactory.__module__ = 'module1.interfaces'
        sys.modules['module2'].OtherFactory = OtherFactory
        OtherFactory.__module__ = 'module2'
        sys.modules['module2'].interfaces = sys.modules['module2.interfaces']
        sys.modules['module2.interfaces'].IOtherFactory = IOtherFactory
        IOtherFactory.__module__ = 'module2.interfaces'

        self.tmphnd, self.dbfile = tempfile.mkstemp()
        self.tmpblob = tempfile.mkdtemp()

        self.storage = ZODB.blob.BlobStorage(
            self.tmpblob,
            ZODB.FileStorage.FileStorage(self.dbfile),
        )
        self.db = ZODB.DB(self.storage)
        self.conn = self.db.open()
        self.root = self.conn.root()

        self._skipped_symbs = zodbupdate.serialize.SKIP_SYMBS

    def update(self, **args):
        self.conn.close()
        self.db.close()
        self.storage.close()

        self.storage = ZODB.blob.BlobStorage(
            self.tmpblob,
            ZODB.FileStorage.FileStorage(self.dbfile),
        )
        updater = zodbupdate.main.create_updater(self.storage, **args)
        updater()
        self.storage.close()

        self.storage = ZODB.blob.BlobStorage(
            self.tmpblob,
            ZODB.FileStorage.FileStorage(self.dbfile),
        )
        self.db = ZODB.DB(self.storage)
        self.conn = self.db.open()
        self.root = self.conn.root()
        return updater

    def tearDown(self):
        self.logger.removeHandler(self.log_handler)
        zodbupdate.main.duplicate_filter.reset()

        if 'module1' in sys.modules:
            del sys.modules['module1']
        if 'module1.interfaces' in sys.modules:
            del sys.modules['module1.interfaces']
        if 'module2' in sys.modules:
            del sys.modules['module2']
        if 'module2.interfaces' in sys.modules:
            del sys.modules['module2.interfaces']

        self.conn.close()
        self.db.close()
        self.storage.close()
        os.close(self.tmphnd)
        os.unlink(self.dbfile)
        os.unlink(self.dbfile + '.index')
        os.unlink(self.dbfile + '.tmp')
        os.unlink(self.dbfile + '.lock')
        shutil.rmtree(self.tmpblob)

        zodbupdate.serialize.SKIP_SYMBS = self._skipped_symbs

    def test_no_transaction_if_no_changes(self):
        # If an update run doesn't produce any changes it won't commit the
        # transaction to avoid superfluous clutter in the DB.
        last = self.storage.lastTransaction()
        updater = self.update()
        self.assertEqual(last, self.storage.lastTransaction())
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_factory_registered_with_copy_reg(self):
        # Factories registered with copy_reg.pickle loose their __name__.
        # We simply ignore those.
        from six.moves import copyreg

        class AnonymousFactory(object):

            def __new__(cls, name):
                return object.__new__(cls)

            def __init__(self, name):
                self._name = name

            def getName(self):
                return self._name

        sys.modules['module1'].AnonymousFactory = AnonymousFactory
        sys.modules['module1'].AnonymousFactory.__module__ = 'module1'
        sys.modules['module1'].Anonymous = AnonymousFactory('Anonymous')
        copyreg.pickle(AnonymousFactory,
                       AnonymousFactory.getName,
                       AnonymousFactory)
        self.root['test'] = sys.modules['module1'].Anonymous
        transaction.commit()

        updater = self.update()

        self.assertEqual('module1', self.root['test'].__class__.__module__)
        self.assertEqual(
            'AnonymousFactory',
            self.root['test'].__class__.__name__)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_skipped_types_are_left_untouched(self):
        skipped = sys.modules['module1'].Factory()
        self.root['skipped'] = skipped
        transaction.commit()
        self.assertIn(('ZODB.blob', 'Blob'), zodbupdate.serialize.SKIP_SYMBS)
        zodbupdate.serialize.SKIP_SYMBS += [('module1', 'Factory')]
        oid = self.root['skipped']._p_oid
        old_pickle, old_serial = self.storage.load(oid)
        self.update(
            default_renames={
                ('module1', 'Factory'): ('module2', 'OtherFactory')})
        pickle, serial = self.storage.load(oid)
        self.assertEqual(old_pickle, pickle)
        self.assertEqual(old_serial, serial)

    def test_not_skipped_types_are_touched(self):
        skipped = sys.modules['module1'].Factory()
        self.root['skipped'] = skipped
        transaction.commit()
        self.assertNotIn(
            ('module1', 'Factory'),
            zodbupdate.serialize.SKIP_SYMBS)
        oid = self.root['skipped']._p_oid
        old_pickle, old_serial = self.storage.load(oid)
        self.update(
            default_renames={
                ('module1', 'Factory'): ('module2', 'OtherFactory')})
        pickle, serial = self.storage.load(oid)
        self.assertNotEqual(old_pickle, pickle)
        self.assertNotEqual(old_serial, serial)


class Python2Tests(Tests):

    def test_convert_with_default_encoding(self):
        # Python 2's pickle doesn't support an encoding parameter
        with self.assertRaises(AssertionError):
            self.update(encoding='utf-8')

    def test_convert_attribute_to_bytes(self):
        from zodbupdate.convert import encode_binary

        test = sys.modules['module1'].Factory()
        test.binary = 'this looks like binary'
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True, default_decoders={
            ('module1', 'Factory'): [encode_binary('binary')]})

        # Protocol is 3 (x80x03) now and the string is encoded as
        # bytes (C).
        self.assertEqual(
            '\x80\x03cmodule1\nFactory\nq\x01.'
            '\x80\x03}q\x02U\x06binaryq\x03C\x16this looks like binarys.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_attribute_to_unicode(self):
        from zodbupdate.convert import decode_attribute

        test = sys.modules['module1'].Factory()
        test.text = u'text élégant'.encode('utf-8')
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True, default_decoders={
            ('module1', 'Factory'): [decode_attribute('text', 'utf-8')]})

        # Protocol is 3 (x80x03) now and the string is encoded as unicode (X)
        self.assertEqual(
            '\x80\x03cmodule1\nFactory\nq\x01.'
            '\x80\x03}q\x02U\x04textq\x03'
            'X\x0e\x00\x00\x00text \xc3\xa9l\xc3\xa9gantq\x04s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_attribute_to_unicode_2(self):
        from zodbupdate.convert import decode_attribute

        test = sys.modules['module1'].Factory()
        test.text = u'text élégant'.encode('utf-8')
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True, default_decoders={
            ('module1', 'Factory'): [decode_attribute('text', 'utf-8')]})

    def test_convert_object_references(self):
        test = sys.modules['module1'].Factory()
        test.reference = sys.modules['module1'].Factory()
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True)

        # Protocol is 3 (x80x03) now and oid in the object reference
        # is encoded as bytes (C).
        self.assertEqual(
            '\x80\x03cmodule1\nFactory\nq\x01.'
            '\x80\x03}q\x02U\treferenceq\x03'
            'C\x08\x00\x00\x00\x00\x00\x00\x00\x02h\x01\x86q\x04Qs.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_set_to_py3(self):
        test = sys.modules['module1'].Factory()
        test.favourite_numbers = {0xaa, 0xbb, 0xcc, 0xdd}
        self.root['test'] = test
        transaction.commit()

        # This is what a Python 2 pickle looks like -- we'll reuse it
        # in Python3Tests
        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                b'\x80\x02cmodule1\nFactory\nq\x01.'
                b'\x80\x02}q\x02U\x11favourite_numbersq\x03c__builtin__\nset\n'
                b'q\x04]q\x05(K\xaaK\xbbK\xccK\xdde\x85Rq\x06s.',
                # ZODB >= 5.4
                b'\x80\x03cmodule1\nFactory\nq\x01.'
                b'\x80\x03}q\x02U\x11favourite_numbersq\x03c__builtin__\nset\n'
                b'q\x04]q\x05(K\xaaK\xbbK\xccK\xdde\x85Rq\x06s.',
            )
        )

        self.update(convert_py3=True)

        # Protocol is 3 (x80x03) now and __builtin__.set is now builtins.set.
        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x01.'
            b'\x80\x03}q\x02U\x11favourite_numbersq\x03cbuiltins\nset\n'
            b'q\x04]q\x05(K\xaaK\xbbK\xccK\xdde\x85Rq\x06s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_sets_Set_to_py3(self):
        import sets

        test = sys.modules['module1'].Factory()
        test.favourite_numbers = sets.Set([0xaa, 0xbb, 0xcc, 0xdd])
        self.root['test'] = test
        transaction.commit()

        # This is what a Python 2 pickle looks like -- we'll reuse it
        # in Python3Tests
        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                b'\x80\x02cmodule1\nFactory\nq\x01.'
                b'\x80\x02}q\x02U\x11favourite_numbersq\x03csets\nSet\nq\x04'
                b')\x81q\x05}q\x06(K\xaa\x88K\xbb\x88K\xcc\x88K\xdd\x88u\x85bs.',
                # ZODB >= 5.4
                b'\x80\x03cmodule1\nFactory\nq\x01.'
                b'\x80\x03}q\x02U\x11favourite_numbersq\x03csets\nSet\nq\x04'
                b')\x81q\x05}q\x06(K\xaa\x88K\xbb\x88K\xcc\x88K\xdd\x88u\x85bs.',
            )
        )

        self.update(convert_py3=True)

        # Protocol is 3 (x80x03) now and sets.Set is encoded
        # as a builtin set
        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x01.'
            b'\x80\x03}q\x02U\x11favourite_numbersq\x03cbuiltins\nset\n'
            b'q\x04]q\x05(K\xaaK\xbbK\xccK\xdde\x85Rq\x06s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_datetime_to_py3(self):
        import datetime

        test = sys.modules['module1'].Factory()
        test.date_of_birth = datetime.datetime(2018, 12, 12)
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True)

        # Protocol is 3 (x80x03) now and datetime payload is encoded
        # as bytes (C).
        self.assertEqual(
            '\x80\x03cmodule1\nFactory\nq\x01.'
            '\x80\x03}q\x02U\rdate_of_birthq\x03cdatetime\ndatetime\nq\x04'
            'C\n\x07\xe2\x0c\x0c\x00\x00\x00\x00\x00\x00\x85Rq\x05s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_date_to_py3(self):
        import datetime

        test = sys.modules['module1'].Factory()
        test.date_of_birth = datetime.date(2018, 12, 12)
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True)

        # Protocol is 3 (x80x03) now and datetime payload is encoded
        # as bytes (C).
        self.assertEqual(
            '\x80\x03cmodule1\nFactory\nq\x01.'
            '\x80\x03}q\x02U\rdate_of_birthq\x03'
            'cdatetime\ndate\nq\x04C\x04\x07\xe2\x0c\x0c\x85Rq\x05s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_time_to_py3(self):
        import datetime

        test = sys.modules['module1'].Factory()
        test.date_of_birth = datetime.time(12, 12)
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True)

        # Protocol is 3 (x80x03) now and datetime payload is encoded
        # as bytes (C).
        self.assertEqual(
            '\x80\x03cmodule1\nFactory\nq\x01.'
            '\x80\x03}q\x02U\rdate_of_birthq\x03cdatetime\ntime\nq\x04'
            'C\x06\x0c\x0c\x00\x00\x00\x00\x85Rq\x05s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_factory_ignore_missing_persistent(self):
        # Create a ZODB with an object referencing a factory, then
        # remove the factory and update the ZODB.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()
        del sys.modules['module1'].Factory

        updater = self.update()

        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                '\x80\x02cmodule1\nFactory\nq\x01.\x80\x02}q\x02.',
                # ZODB >= 5.4
                '\x80\x03cmodule1\nFactory\nq\x01.\x80\x03}q\x02.',
            )
        )
        self.assertTrue(
            isinstance(self.root['test'], ZODB.broken.PersistentBroken))
        self.assertTrue(len(self.log_messages))
        self.assertEqual(
            ['Warning: Missing factory for module1 Factory'],
            self.log_messages)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_factory_ignore_missing_reference(self):
        factory = self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()

        other = self.root['other'] = sys.modules['module2'].OtherFactory()
        factory.other = other
        transaction.commit()
        del sys.modules['module2']

        updater = self.update()

        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                '\x80\x02cmodule1\nFactory\nq\x01.'
                '\x80\x02}q\x02U\x05otherq\x03'
                'U\x08\x00\x00\x00\x00\x00\x00\x00\x02q\x04'
                'cmodule2\nOtherFactory\nq\x05\x86Qs.',
                # ZODB >= 5.4
                '\x80\x03cmodule1\nFactory\nq\x01.'
                '\x80\x03}q\x02U\x05otherq\x03'
                'C\x08\x00\x00\x00\x00\x00\x00\x00\x02'
                'cmodule2\nOtherFactory\nq\x04\x86Qs.',
            )
        )

        self.assertTrue(
            isinstance(self.root['other'], ZODB.broken.PersistentBroken))
        self.assertTrue(len(self.log_messages))
        self.assertEqual(
            ['Warning: Missing factory for module2 OtherFactory'],
            self.log_messages)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_factory_ignore_missing_object(self):
        factory = self.root['test'] = sys.modules['module1'].Factory()
        factory.data = sys.modules['module1'].Data()
        transaction.commit()
        del sys.modules['module1'].Data

        updater = self.update()

        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                '\x80\x02cmodule1\nFactory\nq\x01.'
                '\x80\x02}q\x02U\x04dataq\x03'
                'cmodule1\nData\nq\x04)\x81q\x05}q\x06bs.',
                # ZODB >= 5.4
                '\x80\x03cmodule1\nFactory\nq\x01.'
                '\x80\x03}q\x02U\x04dataq\x03'
                'cmodule1\nData\nq\x04)\x81q\x05}q\x06bs.',
            )
        )
        self.assertTrue(len(self.log_messages))
        self.assertEqual(
            ['Warning: Missing factory for module1 Data'],
            self.log_messages)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_factory_ignore_missing_class(self):
        factory = self.root['test'] = sys.modules['module2'].OtherFactory()
        factory.data = sys.modules['module1'].Data
        transaction.commit()
        del sys.modules['module1']

        updater = self.update()

        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                '\x80\x02cmodule2\nOtherFactory\nq\x01.'
                '\x80\x02}q\x02U\x04dataq\x03cmodule1\nData\nq\x04s.',
                # ZODB >= 5.4
                '\x80\x03cmodule2\nOtherFactory\nq\x01.'
                '\x80\x03}q\x02U\x04dataq\x03cmodule1\nData\nq\x04s.',
            )
        )
        self.assertTrue(len(self.log_messages))
        self.assertEqual(
            ['Warning: Missing factory for module1 Data'],
            self.log_messages)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_factory_ignore_missing_interface(self):
        factory = self.root['test'] = sys.modules['module1'].Factory()
        zope.interface.alsoProvides(
            factory, sys.modules['module1.interfaces'].IFactory)
        transaction.commit()
        del sys.modules['module1']
        del sys.modules['module1.interfaces']

        updater = self.update()

        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                '\x80\x02cmodule1\nFactory\nq\x01.'
                '\x80\x02}q\x02U\x0c__provides__q\x03'
                'czope.interface.declarations\nProvides\nq\x04h\x01'
                'cmodule1.interfaces\nIFactory\nq\x05\x86q\x06Rq\x07s.',
                # ZODb >= 5.4
                '\x80\x03cmodule1\nFactory\nq\x01.'
                '\x80\x03}q\x02U\x0c__provides__q\x03'
                'czope.interface.declarations\nProvides\nq\x04h\x01'
                'cmodule1.interfaces\nIFactory\nq\x05\x86q\x06Rq\x07s.',
            )
        )
        self.assertTrue(len(self.log_messages))
        self.assertEqual(
            ['Warning: Missing factory for module1 Factory',
             'Warning: Missing factory for module1.interfaces IFactory'],
            self.log_messages)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_factory_renamed(self):
        # Create a ZODB with an object referencing a factory, then
        # rename the the factory but keep a reference from the old name in
        # place. Update the ZODB. Then remove the old reference. We should
        # then still be able to access the object.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()

        sys.modules['module1'].NewFactory = sys.modules['module1'].Factory
        sys.modules['module1'].NewFactory.__name__ = 'NewFactory'

        updater = self.update(debug=True)

        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                '\x80\x02cmodule1\nNewFactory\nq\x01.\x80\x02}q\x02.',
                # ZODB >= 5.4
                '\x80\x03cmodule1\nNewFactory\nq\x01.\x80\x03}q\x02.',
            )
        )

        self.assertEqual('module1', self.root['test'].__class__.__module__)
        self.assertEqual('NewFactory', self.root['test'].__class__.__name__)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual(
            {('module1', 'Factory'): ('module1', 'NewFactory')},
            renames)

    def test_factory_renamed_dryrun(self):
        # Run an update with "dy run" option and see that the pickle is
        # not updated.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()

        sys.modules['module1'].NewFactory = sys.modules['module1'].Factory
        sys.modules['module1'].NewFactory.__name__ = 'NewFactory'

        updater = self.update(dry_run=True)
        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                '\x80\x02cmodule1\nFactory\nq\x01.\x80\x02}q\x02.',
                # ZODB >= 5.4
                '\x80\x03cmodule1\nFactory\nq\x01.\x80\x03}q\x02.',
            )
        )

        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual(
            {('module1', 'Factory'): ('module1', 'NewFactory')},
            renames)

        updater = self.update(dry_run=False)
        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                '\x80\x02cmodule1\nNewFactory\nq\x01.\x80\x02}q\x02.',
                # ZODB >= 5.4
                '\x80\x03cmodule1\nNewFactory\nq\x01.\x80\x03}q\x02.',
            )
        )

        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual(
            {('module1', 'Factory'): ('module1', 'NewFactory')},
            renames)

    def test_loaded_renames_override_automatic(self):
        # Same as test_factory_renamed, but provide a pre-defined rename
        # dictionary whose rules will result in a different class being picked
        # than what automatic detection would have done.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()

        sys.modules['module1'].NewFactory = sys.modules['module1'].Factory
        sys.modules['module1'].NewFactory.__name__ = 'NewFactory'

        updater = self.update(
            default_renames={
                ('module1', 'Factory'): ('module2', 'OtherFactory')})

        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                '\x80\x02cmodule2\nOtherFactory\nq\x01.\x80\x02}q\x02.',
                # ZODB >= 5.4
                '\x80\x03cmodule2\nOtherFactory\nq\x01.\x80\x03}q\x02.',
            )
        )

        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_loaded_renames_override_missing_persistent(self):
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()

        del sys.modules['module1'].Factory
        updater = self.update(
            default_renames={
                ('module1', 'Factory'): ('module2', 'OtherFactory')})

        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                '\x80\x02cmodule2\nOtherFactory\nq\x01.\x80\x02}q\x02.',
                # ZODB >= 5.4
                '\x80\x03cmodule2\nOtherFactory\nq\x01.\x80\x03}q\x02.'
            )
        )

        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_loaded_renames_override_missing_interfaces(self):
        class IModule1(zope.interface.Interface):
            pass
        IModule1.__module__ = 'module1'
        sys.modules['module1'].IModule1 = IModule1

        factory = self.root['test'] = sys.modules['module1'].Factory()
        zope.interface.alsoProvides(
            factory, sys.modules['module1.interfaces'].IFactory, IModule1)
        transaction.commit()
        del sys.modules['module1'].interfaces
        del sys.modules['module1.interfaces']
        del sys.modules['module1']

        updater = self.update(
            default_renames={
                ('module1.interfaces', 'IFactory'):
                ('module2.interfaces', 'IOtherFactory'),
                ('module1', 'Factory'):
                ('module2', 'OtherFactory')})

        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4.0
                '\x80\x02cmodule2\nOtherFactory\nq\x01.'
                '\x80\x02}q\x02U\x0c__provides__q\x03'
                'czope.interface.declarations\nProvides\nq\x04h\x01'
                'cmodule2.interfaces\nIOtherFactory\nq\x05'
                'cmodule1\nIModule1\nq\x06\x87q\x07Rq\x08s.',
                # ZODB >= 5.4.0
                '\x80\x03cmodule2\nOtherFactory\nq\x01.'
                '\x80\x03}q\x02U\x0c__provides__q\x03'
                'czope.interface.declarations\nProvides\nq\x04h\x01'
                'cmodule2.interfaces\nIOtherFactory\nq\x05'
                'cmodule1\nIModule1\nq\x06\x87q\x07Rq\x08s.',
            )
        )
        self.assertEqual(
            ['Warning: Missing factory for module1 IModule1'],
            self.log_messages)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_old_style_class(self):
        factory = self.root['test'] = sys.modules['module1'].Factory()
        factory.data = sys.modules['module1'].OldData()
        transaction.commit()

        self.update()

        self.assertIn(
            self.storage.load(self.root['test']._p_oid, '')[0],
            (
                # ZODB < 5.4
                '\x80\x02cmodule1\nFactory\nq\x01.'
                '\x80\x02}q\x02U\x04dataq\x03(cmodule1\nOldData\nq\x04oq\x05}q\x06bs.'
                # ZODB >= 5.4
                '\x80\x03cmodule1\nFactory\nq\x01.'
                '\x80\x03}q\x02U\x04dataq\x03(cmodule1\nOldData\nq\x04oq\x05}q\x06bs.'
            )
        )

    def test_encode_binary_leaves_none_untouched(self):
        from zodbupdate.convert import encode_binary
        mock = dict()
        mock['foo'] = None
        encoder = encode_binary('foo')
        result = encoder(mock)
        self.assertEquals(result, False)
        self.assertEquals(mock['foo'], None)

    def test_decode_attribute_leaves_none_untouched(self):
        from zodbupdate.convert import decode_attribute
        mock = dict()
        mock['foo'] = None
        encoder = decode_attribute('foo', 'utf-8')
        result = encoder(mock)
        self.assertEquals(result, False)
        self.assertEquals(mock['foo'], None)

    def test_blobs_are_left_untouched(self):
        blob = ZODB.blob.Blob()
        self.root['blob'] = blob
        transaction.commit()

        oid = self.root['blob']._p_oid
        old_pickle, old_serial = self.storage.load(oid)

        self.update(convert_py3=True)

        pickle, serial = self.storage.load(oid)
        self.assertEqual(old_pickle, pickle)
        self.assertEqual(old_serial, serial)

        # make sure the reference to the blob was converted
        self.assertIn(
            b'C\x08\x00\x00\x00\x00\x00\x00\x00\x01cZODB.blob',
            self.storage.load(self.root._p_oid, '')[0]
        )


@contextmanager
def overridePickle(obj_to_override, pickle_data):
    orig_serialize = ZODB.serialize.ObjectWriter.serialize

    def serialize(self, obj):
        if obj is obj_to_override:
            return pickle_data
        return orig_serialize(self, obj)

    ZODB.serialize.ObjectWriter.serialize = serialize
    try:
        yield
    finally:
        ZODB.serialize.ObjectWriter.serialize = orig_serialize


class Python3Tests(Tests):

    def test_convert_attribute_to_bytes(self):
        from zodbupdate.convert import encode_binary

        test = sys.modules['module1'].Factory()
        test.binary = 'this looks like binary'
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True, default_decoders={
            ('module1', 'Factory'): [encode_binary('binary')]})

        # Protocol is 3 (x80x03) now and the string is encoded as
        # bytes (C).
        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.'
            b'\x80\x03}q\x01X\x06\x00\x00\x00binaryq\x02'
            b'C\x16this looks like binaryq\x03s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_attribute_to_unicode(self):
        from zodbupdate.convert import decode_attribute

        test = sys.modules['module1'].Factory()
        test.text = u'text élégant'.encode('utf-8')
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True, default_decoders={
            ('module1', 'Factory'): [decode_attribute('text', 'utf-8')]})

        # Protocol is 3 (x80x03) now and the string is encoded as unicode (X)
        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.'
            b'\x80\x03}q\x01X\x04\x00\x00\x00textq\x02'
            b'X\x0e\x00\x00\x00text \xc3\xa9l\xc3\xa9gantq\x03s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_object_references(self):
        test = sys.modules['module1'].Factory()
        test.reference = sys.modules['module1'].Factory()
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True)

        # Protocol is 3 (x80x03) now and oid in the object reference
        # is encoded as bytes (C).
        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.'
            b'\x80\x03}q\x01X\t\x00\x00\x00referenceq\x02'
            b'C\x08\x00\x00\x00\x00\x00\x00\x00\x02q\x03h\x00\x86q\x04Qs.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_set_to_py3(self):
        test = sys.modules['module1'].Factory()
        test.favourite_numbers = {0xaa, 0xbb, 0xcc, 0xdd}
        self.root['test'] = test
        pickle_data = (
            b'\x80\x02cmodule1\nFactory\nq\x01.'
            b'\x80\x02}q\x02U\x11favourite_numbersq\x03c__builtin__\nset\n'
            b'q\x04]q\x05(K\xaaK\xbbK\xccK\xdde\x85Rq\x06s.'
        )
        with overridePickle(test, pickle_data):
            transaction.commit()

        self.update(convert_py3=True)

        # Protocol is 3 (x80x03) now and __builtin__.set is now builtins.set.
        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.'
            b'\x80\x03}q\x01X\x11\0\0\0favourite_numbersq\x02cbuiltins\nset\n'
            b'q\x03]q\x04(K\xaaK\xbbK\xccK\xdde\x85q\x05Rq\x06s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_sets_Set_to_py3(self):
        test = sys.modules['module1'].Factory()
        test.favourite_numbers = {0xaa, 0xbb, 0xcc, 0xdd}
        self.root['test'] = test
        pickle_data = (
            b'\x80\x02cmodule1\nFactory\nq\x01.'
            b'\x80\x02}q\x02U\x11favourite_numbersq\x03csets\nSet\nq\x04'
            b')\x81q\x05}q\x06(K\xaa\x88K\xbb\x88K\xcc\x88K\xdd\x88u\x85bs.'
        )
        with overridePickle(test, pickle_data):
            transaction.commit()

        self.update(convert_py3=True)

        # Protocol is 3 (x80x03) now and __builtin__.set is now builtins.set.
        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.'
            b'\x80\x03}q\x01X\x11\0\0\0favourite_numbersq\x02cbuiltins\nset\n'
            b'q\x03]q\x04(K\xaaK\xbbK\xccK\xdde\x85q\x05Rq\x06s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_datetime_to_py3(self):
        import datetime

        test = sys.modules['module1'].Factory()
        test.date_of_birth = datetime.datetime(2018, 12, 12)
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True)

        # Protocol is 3 (x80x03) now and datetime payload is encoded
        # as bytes (C).
        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.'
            b'\x80\x03}q\x01X\r\x00\x00\x00date_of_birthq\x02'
            b'cdatetime\ndatetime\nq\x03'
            b'C\n\x07\xe2\x0c\x0c\x00\x00\x00\x00\x00\x00q\x04'
            b'\x85q\x05Rq\x06s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_date_to_py3(self):
        import datetime

        test = sys.modules['module1'].Factory()
        test.date_of_birth = datetime.date(2018, 12, 12)
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True)

        # Protocol is 3 (x80x03) now and datetime payload is encoded
        # as bytes (C).
        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.'
            b'\x80\x03}q\x01X\r\x00\x00\x00date_of_birthq\x02'
            b'cdatetime\ndate\nq\x03'
            b'C\x04\x07\xe2\x0c\x0cq\x04\x85q\x05Rq\x06s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_time_to_py3(self):
        import datetime

        test = sys.modules['module1'].Factory()
        test.date_of_birth = datetime.time(12, 12)
        self.root['test'] = test
        transaction.commit()

        self.update(convert_py3=True)

        # Protocol is 3 (x80x03) now and datetime payload is encoded
        # as bytes (C).
        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.'
            b'\x80\x03}q\x01X\r\x00\x00\x00date_of_birthq\x02'
            b'cdatetime\ntime\nq\x03'
            b'C\x06\x0c\x0c\x00\x00\x00\x00q\x04\x85q\x05Rq\x06s.',
            self.storage.load(self.root['test']._p_oid, '')[0])

    def test_convert_with_default_encoding(self):
        # Manually craft a protocol 2 pickle
        test = sys.modules['module1'].Factory()
        self.root['test'] = test
        data = (
            b'\x80\x02cmodule1\nFactory\nq\x01.'
            b'\x80\x02}q\x02U\x06stringq\x03U\x03\xe2\x98\x83q\x04s.'
        )
        with overridePickle(test, data):
            transaction.commit()

        self.update(convert_py3=True, encoding='utf-8')

        # Now we have a protocol 3 pickle with the text decoded
        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.'
            b'\x80\x03}q\x01X\x06\x00\x00\x00stringq\x02'
            b'X\x03\x00\x00\x00\xe2\x98\x83q\x03s.',
            self.storage.load(test._p_oid, '')[0]
        )

    def test_factory_ignore_missing_persistent(self):
        # Create a ZODB with an object referencing a factory, then
        # remove the factory and update the ZODB.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()
        del sys.modules['module1'].Factory

        updater = self.update()

        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.\x80\x03}q\x01.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        self.assertTrue(
            isinstance(self.root['test'], ZODB.broken.PersistentBroken))
        self.assertTrue(len(self.log_messages))
        self.assertEqual(
            ['Warning: Missing factory for module1 Factory'],
            self.log_messages)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_factory_ignore_missing_reference(self):
        factory = self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()

        other = self.root['other'] = sys.modules['module2'].OtherFactory()
        factory.other = other
        transaction.commit()
        del sys.modules['module2']

        updater = self.update()

        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.'
            b'\x80\x03}q\x01X\x05\x00\x00\x00otherq\x02'
            b'C\x08\x00\x00\x00\x00\x00\x00\x00\x02q\x03'
            b'cmodule2\nOtherFactory\nq\x04\x86q\x05Qs.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        self.assertTrue(
            isinstance(self.root['other'], ZODB.broken.PersistentBroken))
        self.assertTrue(len(self.log_messages))
        self.assertEqual(
            ['Warning: Missing factory for module2 OtherFactory'],
            self.log_messages)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_factory_ignore_missing_object(self):
        factory = self.root['test'] = sys.modules['module1'].Factory()
        factory.data = sys.modules['module1'].Data()
        transaction.commit()
        del sys.modules['module1'].Data

        updater = self.update()

        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.'
            b'\x80\x03}q\x01X\x04\x00\x00\x00dataq\x02'
            b'cmodule1\nData\nq\x03)\x81q\x04s.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        self.assertTrue(len(self.log_messages))
        self.assertEqual(
            ['Warning: Missing factory for module1 Data'],
            self.log_messages)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_factory_ignore_missing_class(self):
        factory = self.root['test'] = sys.modules['module2'].OtherFactory()
        factory.data = sys.modules['module1'].Data
        transaction.commit()
        del sys.modules['module1']

        updater = self.update()

        self.assertEqual(
            b'\x80\x03cmodule2\nOtherFactory\nq\x00.'
            b'\x80\x03}q\x01X\x04\x00\x00\x00dataq\x02cmodule1\nData\nq\x03s.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        self.assertTrue(len(self.log_messages))
        self.assertEqual(
            ['Warning: Missing factory for module1 Data'],
            self.log_messages)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_factory_ignore_missing_interface(self):
        factory = self.root['test'] = sys.modules['module1'].Factory()
        zope.interface.alsoProvides(
            factory, sys.modules['module1.interfaces'].IFactory)
        transaction.commit()
        del sys.modules['module1']
        del sys.modules['module1.interfaces']

        updater = self.update()

        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.'
            b'\x80\x03}q\x01X\x0c\x00\x00\x00__provides__q\x02'
            b'czope.interface.declarations\nProvides\nq\x03h\x00'
            b'cmodule1.interfaces\nIFactory\nq\x04\x86q\x05Rq\x06s.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        self.assertTrue(len(self.log_messages))
        self.assertEqual(
            ['Warning: Missing factory for module1 Factory',
             'Warning: Missing factory for module1.interfaces IFactory'],
            self.log_messages)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_factory_renamed(self):
        # Create a ZODB with an object referencing a factory, then
        # rename the the factory but keep a reference from the old name in
        # place. Update the ZODB. Then remove the old reference. We should
        # then still be able to access the object.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()

        sys.modules['module1'].NewFactory = sys.modules['module1'].Factory
        sys.modules['module1'].NewFactory.__name__ = 'NewFactory'

        updater = self.update(debug=True)

        self.assertEqual(
            b'\x80\x03cmodule1\nNewFactory\nq\x00.\x80\x03}q\x01.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        self.assertEqual('module1', self.root['test'].__class__.__module__)
        self.assertEqual('NewFactory', self.root['test'].__class__.__name__)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual(
            {('module1', 'Factory'): ('module1', 'NewFactory')},
            renames)

    def test_factory_renamed_dryrun(self):
        # Run an update with "dy run" option and see that the pickle is
        # not updated.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()

        sys.modules['module1'].NewFactory = sys.modules['module1'].Factory
        sys.modules['module1'].NewFactory.__name__ = 'NewFactory'

        updater = self.update(dry_run=True)
        self.assertEqual(
            b'\x80\x03cmodule1\nFactory\nq\x00.\x80\x03}q\x01.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual(
            {('module1', 'Factory'): ('module1', 'NewFactory')},
            renames)

        updater = self.update(dry_run=False)
        self.assertEqual(
            b'\x80\x03cmodule1\nNewFactory\nq\x00.\x80\x03}q\x01.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual(
            {('module1', 'Factory'): ('module1', 'NewFactory')},
            renames)

    def test_loaded_renames_override_automatic(self):
        # Same as test_factory_renamed, but provide a pre-defined rename
        # dictionary whose rules will result in a different class being picked
        # than what automatic detection would have done.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()

        sys.modules['module1'].NewFactory = sys.modules['module1'].Factory
        sys.modules['module1'].NewFactory.__name__ = 'NewFactory'

        updater = self.update(
            default_renames={
                ('module1', 'Factory'): ('module2', 'OtherFactory')})

        self.assertEqual(
            b'\x80\x03cmodule2\nOtherFactory\nq\x00.\x80\x03}q\x01.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_loaded_renames_override_missing_persistent(self):
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()

        del sys.modules['module1'].Factory
        updater = self.update(
            default_renames={
                ('module1', 'Factory'): ('module2', 'OtherFactory')})

        self.assertEqual(
            b'\x80\x03cmodule2\nOtherFactory\nq\x00.\x80\x03}q\x01.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_loaded_renames_override_missing_interfaces(self):
        class IModule1(zope.interface.Interface):
            pass
        IModule1.__module__ = 'module1'
        sys.modules['module1'].IModule1 = IModule1

        factory = self.root['test'] = sys.modules['module1'].Factory()
        zope.interface.alsoProvides(
            factory, sys.modules['module1.interfaces'].IFactory, IModule1)
        transaction.commit()
        del sys.modules['module1'].interfaces
        del sys.modules['module1.interfaces']
        del sys.modules['module1']

        updater = self.update(
            default_renames={
                ('module1.interfaces', 'IFactory'):
                ('module2.interfaces', 'IOtherFactory'),
                ('module1', 'Factory'):
                ('module2', 'OtherFactory')})

        self.assertEqual(
            b'\x80\x03cmodule2\nOtherFactory\nq\x00.'
            b'\x80\x03}q\x01X\x0c\x00\x00\x00__provides__q\x02'
            b'czope.interface.declarations\nProvides\nq\x03h\x00'
            b'cmodule2.interfaces\nIOtherFactory\nq\x04'
            b'cmodule1\nIModule1\nq\x05\x87q\x06Rq\x07s.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        self.assertEqual(
            ['Warning: Missing factory for module1 IModule1'],
            self.log_messages)
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestsBasics))
    if six.PY2:
        suite.addTest(unittest.makeSuite(Python2Tests))
    if six.PY3:
        suite.addTest(unittest.makeSuite(Python3Tests))
    return suite
