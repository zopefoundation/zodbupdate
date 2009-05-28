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

import sys
import zodbupgrade.analyze
import ZODB.FileStorage
import logging


logging.getLogger().addHandler(logging.StreamHandler())
logging.getLogger().setLevel(0)


def main():
    db = sys.argv[1]
    storage = ZODB.FileStorage.FileStorage('Data.fs')
    zodbupgrade.analyze.update_storage(storage)
