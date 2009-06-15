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
import ZODB.FileStorage
import logging 
import os
import persistent
import pickle
import sys
import tempfile
import transaction
import types
import unittest
import zodbupgrade.analyze
import zodbupgrade.picklefilter


class IgnoringFilter(object):

    def filter(self, record):
        return False

ignore = IgnoringFilter()


class ZODBUpgradeTests(unittest.TestCase):

    def setUp(self):
        zodbupgrade.analyze.logger.addFilter(ignore)

        sys.modules['module1'] =  types.ModuleType('module1')
        class Factory(persistent.Persistent):
            pass
        sys.modules['module1'].Factory = Factory
        Factory.__module__ = 'module1'

        _, self.dbfile = tempfile.mkstemp()
        self.db = None
        self.reopen_db()

    def update(self, **args):
        updater = zodbupgrade.analyze.Updater(self.storage, **args)
        updater()
        self.storage.close()
        return updater

    def tearDown(self):
        zodbupgrade.analyze.logger.removeFilter(ignore)
        del sys.modules['module1']

        self.db.close()
        os.unlink(self.dbfile)
        os.unlink(self.dbfile + '.index')
        os.unlink(self.dbfile + '.tmp')
        os.unlink(self.dbfile + '.lock')

    def reopen_storage(self):
        self.storage = ZODB.FileStorage.FileStorage(self.dbfile)

    def reopen_db(self):
        self.reopen_storage()
        self.db = ZODB.DB(self.storage)
        self.conn = self.db.open()
        self.root = self.conn.root()

    def test_factory_missing(self):
        # Create a ZODB with an object referencing a factory, then 
        # remove the factory and analyze the ZODB.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()
        del sys.modules['module1'].Factory

        self.db.close()
        self.reopen_storage()

        self.assertRaises(ValueError, self.update)

    def test_factory_renamed(self):
        # Create a ZODB with an object referencing a factory, then 
        # rename the the factory but keep a reference from the old name in
        # place. Update the ZODB. Then remove the old reference. We should
        # then still be able to access the object.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()
        self.db.close()

        sys.modules['module1'].NewFactory = sys.modules['module1'].Factory
        sys.modules['module1'].NewFactory.__name__ = 'NewFactory'

        self.db.close()
        self.reopen_storage()

        self.update()

        del sys.modules['module1'].Factory

        self.reopen_db()

        self.assertEquals('cmodule1\nNewFactory\nq\x01.}q\x02.',
                          self.storage.load(self.root['test']._p_oid, '')[0])
        self.assertEquals('module1', self.root['test'].__class__.__module__)
        self.assertEquals('NewFactory', self.root['test'].__class__.__name__)

    def test_factory_renamed_dryrun(self):
        # Run an update with "dy run" option and see that the pickle is
        # not updated.
        self.root['test'] = sys.modules['module1'].Factory()
        transaction.commit()
        self.db.close()

        sys.modules['module1'].NewFactory = sys.modules['module1'].Factory
        sys.modules['module1'].NewFactory.__name__ = 'NewFactory'

        self.db.close()
        self.reopen_storage()

        self.update(dry=True)

        self.reopen_db()

        self.assertEquals('cmodule1\nFactory\nq\x01.}q\x02.',
                          self.storage.load(self.root['test']._p_oid, '')[0])

        self.db.close()
        self.reopen_storage()
        self.update(dry=False)
        self.reopen_db()

        self.assertEquals('cmodule1\nNewFactory\nq\x01.}q\x02.',
                          self.storage.load(self.root['test']._p_oid, '')[0])

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
        self.db.close()
        self.reopen_storage()
        self.update()

        self.assertEquals('module1', self.root['test'].__class__.__module__)
        self.assertEquals('AnonymousFactory', self.root['test'].__class__.__name__)


class PickleFilterTests(unittest.TestCase):
    # Tests the pickle filter for re-pickling op-codes

    def assertNonArgCode(self, code):
        self.assertArgCode(code, code, None)

    def assertArgCode(self, result, code, arg):
        self.assertEquals(
            result,
            zodbupgrade.picklefilter.to_pickle_chunk(code, arg))

    def test_sanity_check(self):
        # Check binary compatibility on simple "real" pickle
        pass

    def test_MARK(self):
        self.assertNonArgCode(pickle.MARK)

    def test_STOP(self):
        self.assertNonArgCode(pickle.STOP)

    def test_POP(self):
        self.assertNonArgCode(pickle.POP)

    def test_POP_MARK(self):
        self.assertNonArgCode(pickle.POP_MARK)

    def test_DUP(self):
        self.assertNonArgCode(pickle.DUP)

    def test_FLOAT(self):
        self.assertArgCode('F12.300000000000001\n', pickle.FLOAT, 12.3)

    def test_INT(self):
        self.assertArgCode('I01237940039285380274899124224\n', pickle.INT, 2**90)

    def test_BININT(self):
        self.assertArgCode('J\x00\x00\x01\x00', pickle.BININT, 0xffff+1)

    def test_BININT1(self):
        self.assertArgCode('K\xf0', pickle.BININT1, 0xf0)

    def test_LONG(self):
        self.assertArgCode("L1546\n", pickle.LONG, 1546)

    def test_BININT2(self):
        self.assertArgCode('M\xf0\xff', pickle.BININT2, 0xfff0)

    def test_NONE(self):
        self.assertNonArgCode(pickle.NONE)

    def test_PERSID(self):
        self.assertArgCode('P12345\n', pickle.PERSID, '12345')

    def test_BINPERSID(self):
        self.assertNonArgCode(pickle.BINPERSID)

    def test_REDUCE(self):
        self.assertNonArgCode(pickle.REDUCE)

    def test_STRING(self):
        self.assertArgCode("S'asdf'\n", pickle.STRING, 'asdf')

    def test_BINSTRING(self):
        self.assertArgCode('T\x06\x00\x00\x00foobar', pickle.BINSTRING, 'foobar')

    def test_SHORT_BINSTRING(self):
        self.assertArgCode('U\x04asdf', pickle.SHORT_BINSTRING, 'asdf')

    def test_UNICODE(self):
        self.assertArgCode('V\xfcnders\n', pickle.UNICODE, u'\xfcnders')

    def test_BINUNICODE(self):
        self.assertArgCode('X\x06\x00\x00\x00\xc3\xbc1234', pickle.BINUNICODE, u'\xfc1234')

    def test_APPEND(self):
        self.assertNonArgCode(pickle.APPEND)

    def test_BUILD(self):
        self.assertNonArgCode(pickle.BUILD)

    def test_GLOBAL(self):
        self.assertArgCode('cbar\nfoo\n', pickle.GLOBAL, 'bar foo')

    def test_DICT(self):
        self.assertNonArgCode(pickle.DICT)

    def test_EMPTY_DICT(self):
        self.assertNonArgCode(pickle.EMPTY_DICT)

    def test_APPENDS(self):
        self.assertNonArgCode(pickle.APPENDS)

    def test_GET(self):
        self.assertArgCode('g12\n', pickle.GET, 12)

    def test_BINGET(self):
        self.assertArgCode('h\x80', pickle.BINGET, 128)

    def test_INST(self):
        self.assertArgCode('ifoo\nbar\n', pickle.INST, 'foo bar')

    def test_LONG_BINGET(self):
        self.assertArgCode('j\x00\x04\x00\x00', pickle.LONG_BINGET, 1024)

    def test_LIST(self):
        self.assertNonArgCode(pickle.LIST)

    def test_EMPTY_LIST(self):
        self.assertNonArgCode(pickle.EMPTY_LIST)

    def test_OBJ(self):
        self.assertNonArgCode(pickle.OBJ)

    def test_PUT(self):
        self.assertArgCode("p12\n", pickle.PUT, 12)

    def test_BINPUT(self):
        self.assertArgCode('q\x80', pickle.BINPUT, 128)

    def test_LONG_BINPUT(self):
        self.assertArgCode('r\x00\x04\x00\x00', pickle.LONG_BINPUT, 1024)

    def test_SETITEM(self):
        self.assertNonArgCode(pickle.SETITEM)

    def test_TUPLE(self):
        self.assertNonArgCode(pickle.TUPLE)

    def test_EMPTY_TUPLE(self):
        self.assertNonArgCode(pickle.EMPTY_TUPLE)

    def test_SETITEMS(self):
        self.assertNonArgCode(pickle.SETITEMS)

    def test_BINFLOAT(self):
        self.assertArgCode('G@(\x00\x00\x00\x00\x00\x00',
                           pickle.BINFLOAT, 12.0)

    def test_TRUE(self):
        self.assertArgCode(pickle.TRUE, pickle.INT, True)

    def test_FALSE(self):
        self.assertArgCode(pickle.FALSE, pickle.INT, False)

    def test_PROTO(self):
        self.assertArgCode('\x80\x01', pickle.PROTO, 1)

    def test_NEWOBJ(self):
        self.assertNonArgCode(pickle.NEWOBJ)

    def test_EXT1(self):
        self.assertArgCode('\x82\xf0', pickle.EXT1, 0xf0)

    def test_EXT2(self):
        self.assertArgCode('\x83\x00\x01', pickle.EXT2, 0xff+1)

    def test_EXT4(self):
        self.assertArgCode('\x84\x00\x00\x01\x00', pickle.EXT4, 0xffff+1)

    def test_TUPLE1(self):
        self.assertNonArgCode(pickle.TUPLE1)

    def test_TUPLE2(self):
        self.assertNonArgCode(pickle.TUPLE2)

    def test_TUPLE3(self):
        self.assertNonArgCode(pickle.TUPLE3)

    def test_NEWTRUE(self):
        self.assertNonArgCode(pickle.NEWTRUE)

    def test_NEWFALSE(self):
        self.assertNonArgCode(pickle.NEWFALSE)

    def test_LONG1(self):
        self.assertArgCode('\x8a\x02\x80\x00', pickle.LONG1, 128)

    def test_LONG4(self):
        self.assertArgCode('\x8b\x02\x00\x00\x00\x00\x04', pickle.LONG4, 2**10)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ZODBUpgradeTests))
    suite.addTest(unittest.makeSuite(PickleFilterTests))
    return suite
