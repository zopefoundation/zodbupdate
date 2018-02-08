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

import ZODB
import ZODB.broken
import ZODB.FileStorage
import os
import persistent
import sys
import tempfile
import transaction
import types
import unittest
import six
import zodbupdate.main


class LogFilter(object):

    def __init__(self, msg_lst):
        self.msg_lst = msg_lst

    # Do not spit out any logging, but record them
    def filter(self, record):
        self.msg_lst.append(record.msg)
        return False


class Tests(unittest.TestCase):

    def setUp(self):
        self.log_messages = []
        self.log_filter = LogFilter(self.log_messages)
        zodbupdate.update.logger.addFilter(self.log_filter)

        sys.modules['module1'] = types.ModuleType('module1')
        sys.modules['module2'] = types.ModuleType('module2')

        class Factory(persistent.Persistent):
            pass

        class OtherFactory(persistent.Persistent):
            pass

        sys.modules['module1'].Factory = Factory
        Factory.__module__ = 'module1'
        sys.modules['module2'].OtherFactory = OtherFactory
        OtherFactory.__module__ = 'module2'

        self.tmphnd, self.dbfile = tempfile.mkstemp()

        self.storage = ZODB.FileStorage.FileStorage(self.dbfile)
        self.db = ZODB.DB(self.storage)
        self.conn = self.db.open()
        self.root = self.conn.root()

    def update(self, **args):
        self.conn.close()
        self.db.close()
        self.storage.close()

        self.storage = ZODB.FileStorage.FileStorage(self.dbfile)
        updater = zodbupdate.main.create_updater(self.storage, **args)
        updater()
        self.storage.close()

        self.storage = ZODB.FileStorage.FileStorage(self.dbfile)
        self.db = ZODB.DB(self.storage)
        self.conn = self.db.open()
        self.root = self.conn.root()
        return updater

    def tearDown(self):
        zodbupdate.update.logger.removeFilter(self.log_filter)
        del sys.modules['module1']
        del sys.modules['module2']

        self.conn.close()
        self.db.close()
        self.storage.close()
        os.close(self.tmphnd)
        os.unlink(self.dbfile)
        os.unlink(self.dbfile + '.index')
        os.unlink(self.dbfile + '.tmp')
        os.unlink(self.dbfile + '.lock')


class Python2Tests(Tests):

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

    def test_factory_ignore_missing(self):
        # Create a ZODB with an object referencing a factory, then
        # remove the factory and update the ZODB.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()
        del sys.modules['module1'].Factory

        updater = self.update()

        self.assertEqual(
            '\x80\x02cmodule1\nFactory\nq\x01.\x80\x02}q\x02.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        self.assertTrue(
            isinstance(self.root['test'], ZODB.broken.PersistentBroken))
        self.assertTrue(len(self.log_messages))
        self.assertEqual(
            'Warning: Missing factory for module1 Factory',
            self.log_messages[0])
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
            '\x80\x02cmodule1\nNewFactory\nq\x01.\x80\x02}q\x02.',
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
            '\x80\x02cmodule1\nFactory\nq\x01.\x80\x02}q\x02.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual(
            {('module1', 'Factory'): ('module1', 'NewFactory')},
            renames)

        updater = self.update(dry_run=False)
        self.assertEqual(
            '\x80\x02cmodule1\nNewFactory\nq\x01.\x80\x02}q\x02.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual(
            {('module1', 'Factory'): ('module1', 'NewFactory')},
            renames)

    def test_factory_registered_with_copy_reg(self):
        # Factories registered with copy_reg.pickle loose their __name__.
        # We simply ignore those.

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
        import copy_reg
        copy_reg.pickle(AnonymousFactory,
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

    def test_no_transaction_if_no_changes(self):
        # If an update run doesn't produce any changes it won't commit the
        # transaction to avoid superfluous clutter in the DB.
        last = self.storage.lastTransaction()
        updater = self.update()
        self.assertEqual(last, self.storage.lastTransaction())
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

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
            '\x80\x02cmodule2\nOtherFactory\nq\x01.\x80\x02}q\x02.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)

    def test_loaded_renames_override_missing(self):
        # Same as test_factory_missing, but provide a pre-defined rename
        # dictionary whose rules will result in a different class being picked
        # than what automatic detection would have done.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()

        del sys.modules['module1'].Factory
        updater = self.update(
            default_renames={
                ('module1', 'Factory'): ('module2', 'OtherFactory')})

        self.assertEqual(
            '\x80\x02cmodule2\nOtherFactory\nq\x01.\x80\x02}q\x02.',
            self.storage.load(self.root['test']._p_oid, '')[0])
        renames = updater.processor.get_rules(implicit=True)
        self.assertEqual({}, renames)


def test_suite():
    suite = unittest.TestSuite()
    if six.PY2:
        suite.addTest(unittest.makeSuite(Python2Tests))
    return suite
