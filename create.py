# vim:fileencoding=utf-8
# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt

from ZODB.FileStorage import FileStorage
from ZODB.DB import DB

s = FileStorage('Data.fs')
d = DB(s)
c = d.open()
r = c.root()

import klass

r['foo'] = klass.P1()
r['foo'].x = klass.P2()

import transaction
transaction.commit()

