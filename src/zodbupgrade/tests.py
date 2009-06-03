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
import os
import sys
import tempfile
import types
import unittest
import transaction
import zodbupgrade.analyze
import logging 


class IgnoringFilter(object):

    def filter(self, record):
        return False

ignore = IgnoringFilter()


class ZODBUpgradeTests(unittest.TestCase):

    def setUp(self):
        zodbupgrade.analyze.logger.addFilter(ignore)

        sys.modules['module1'] =  types.ModuleType('module1')
        class Factory(object):
            pass
        sys.modules['module1'].Factory = Factory
        Factory.__module__ = 'module1'

        _, self.dbfile = tempfile.mkstemp()
        self.db = None
        self.reopen_db()

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

        self.assertRaises(ValueError,
                          zodbupgrade.analyze.update_storage, self.storage)

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
        zodbupgrade.analyze.update_storage(self.storage)

        del sys.modules['module1'].Factory

        self.reopen_db()

        self.assertEquals('module1', self.root['test'].__class__.__module__)
        self.assertEquals('NewFactory', self.root['test'].__class__.__name__)

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
        zodbupgrade.analyze.update_storage(self.storage)

        self.assertEquals('module1', self.root['test'].__class__.__module__)
        self.assertEquals('AnonymousFactory', self.root['test'].__class__.__name__)


def test_suite():
    return unittest.makeSuite(ZODBUpgradeTests)
