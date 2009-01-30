# vim:fileencoding=utf-8
# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt

import sys
import StringIO
from ZODB.FileStorage import FileStorage
from ZODB.DB import DB
import ZODB.broken
import transaction
import pickle
import pickletools
import ZODB.utils

SAFE_OPS = 'IJKML\x8a\x8bSTUN\x88\x89VXFG]ael)t\x85\x86\x87}dsu02(1ghjpqrRbo\x81\x80.PQ'
KNOWN_HARD = 'ci'

s = FileStorage('Data.fs')
d = DB(s)
c = d.open()
r = c.root()

missing_classes = set()
oids_to_rewrite = set()
rewrites_found = set()

def find_missing_classes(oid, data):
    # First part of the pickle: the object factory
    for op, arg, pos in pickletools.genops(data):
        if op.code in SAFE_OPS:
            continue
        elif op.code in KNOWN_HARD:
            module_name, symbol = arg.split(' ')
            try:
                module = __import__(module_name, globals(), {}, [symbol])
                factory = getattr(module, symbol)
            except (ImportError, AttributeError):
                missing_classes.add('%s.%s' % (module_name, symbol))
            else:
                if ((factory.__module__, factory.__name__) !=
                    (module_name, symbol)):
                    # The factory is reachable but it's not the
                    # canonical location. Mark object for updating.
                    rewrites_found.add(((module_name, symbol),
                        (factory.__module__, factory.__name__)))
                    oids_to_rewrite.add(oid)
        else:
            raise ValueError('Unknown pickle opcode %r' % op.code)

next = None
while True:
    oid, tid, data, next = s.record_iternext(next)
    pickle_data = StringIO.StringIO(data)
    find_missing_classes(oid, pickle_data)
    find_missing_classes(oid, pickle_data)
    if next is None:
        break

if missing_classes:
    print "The following classes are missing:"
    for class_ in sorted(missing_classes):
        print class_
else:
    print "All classes found."
    print "%s moved classes detected, will update %s objects" % (len(rewrites_found), len(oids_to_rewrite))
    for (old_mod, old_name), (new_mod, new_name) in rewrites_found:
        print "%s.%s -> %s.%s" % (old_mod, old_name, new_mod, new_name)
    for oid in oids_to_rewrite:
        obj = c.get(oid)
        obj._p_changed = True
    transaction.commit()
