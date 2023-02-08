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

import logging
import sys

import ZODB._compat
import zodbpickle
import zodbpickle.pickle as pickle
from ZODB.broken import Broken


def is_broken(symb):
    """Return true if the given symbol is broken.
    """
    return isinstance(symb, type) and issubclass(symb, Broken)


class UnpicklerImpl(pickle.Unpickler):

    def __init__(self, f, **kw):
        super().__init__(f, **kw)

    # Python doesn't allow assignments to find_global,
    # instead, find_class can be overridden

    find_global = None

    def find_class(self, modulename, name):
        if self.find_global is None:
            return super().find_class(modulename, name)
        return self.find_global(modulename, name)


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
    pickler.persistent_id = persistent_id
    return pickler


ENCODING = sys.getdefaultencoding()


def safe_binary(value):
    if isinstance(value, bytes):
        return zodbpickle.binary(value)
    if isinstance(value, str):
        return zodbpickle.binary(value.encode(ENCODING))
    return value


def get_zodb_magic(filepath):
    """ Read the first four bytes of a ZODB file to get its magic """
    with open(filepath, 'rb') as fp:
        return fp.read(4)
