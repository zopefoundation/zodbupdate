##############################################################################
#
# Copyright (c) 2009-2010 Zope Corporation and Contributors.
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

import ZODB._compat
import logging
import six
import sys
import zodbpickle

from ZODB.broken import Broken


def is_broken(symb):
    """Return true if the given symbol is broken.
    """
    return isinstance(symb, six.class_types) and issubclass(symb, Broken)


if six.PY3:
    import zodbpickle.pickle as pickle

    class UnpicklerImpl(pickle.Unpickler):

        def __init__(self, f, **kw):
            super(UnpicklerImpl, self).__init__(f, **kw)

        # Py3: Python 3 doesn't allow assignments to find_global,
        # instead, find_class can be overridden

        find_global = None

        def find_class(self, modulename, name):
            if self.find_global is None:
                return super(UnpicklerImpl, self).find_class(modulename, name)
            return self.find_global(modulename, name)

else:
    try:
        import zodbpickle.fastpickle as pickle
    except ImportError:
        import zodbpickle.pickle as pickle

    UnpicklerImpl = pickle.Unpickler


PicklingError = pickle.PicklingError

logger = logging.getLogger('zodbupdate')

DEFAULT_PROTOCOL = ZODB._compat._protocol


def Unpickler(
        input_file, persistent_load, find_global, **kw):
    # Please refer to ZODB._compat for explanation.
    unpickler = UnpicklerImpl(input_file, **kw)
    if find_global is not None:
        unpickler.find_global = find_global
        try:
            unpickler.find_class = find_global
        except AttributeError:
            pass
    unpickler.persistent_load = persistent_load
    return unpickler


def Pickler(
        output_file, persistent_id, protocol=DEFAULT_PROTOCOL):
    # Please refer to ZODB._compat for explanation.
    pickler = pickle.Pickler(output_file, protocol)
    if not six.PY3:
        pickler.inst_persistent_id = persistent_id
    pickler.persistent_id = persistent_id
    return pickler


ENCODING = sys.getdefaultencoding()

def safe_binary(value):
    if isinstance(value, bytes):
        return zodbpickle.binary(value)
    if isinstance(value, six.text_type):
        return zodbpickle.binary(value.encode(ENCODING))
    return value
