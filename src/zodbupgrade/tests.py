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




class ZODBUpgradeTests(unittest.TestCase):

    def setUp(self):
        sys.modules['module1'] =  types.ModuleType('module1')
        class Factory(object):
            pass
        sys.modules['module1'].Factory = Factory
        Factory.__module__ = 'module1'

        _, self.dbfile = tempfile.mkstemp()
        self.db = None
        self.reopen_db()

    def tearDown(self):
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


def test_suite():
    return unittest.makeSuite(ZODBUpgradeTests)
