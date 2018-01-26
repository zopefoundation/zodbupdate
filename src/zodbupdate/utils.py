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


if six.PY3:
    raise RuntimeError('Not yet')
else:
    try:
        import zodbpickle.fastpickle as pickle
    except ImportError:
        import zodbpickle.pickle as pickle


logger = logging.getLogger('zodbupdate')

DEFAULT_PROTOCOL = ZODB._compat._protocol


def Unpickler(
        input_file, persistent_load, find_global):
    # Please refer to ZODB._compat for explanation.
    unpickler = pickle.Unpickler(input_file)
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
