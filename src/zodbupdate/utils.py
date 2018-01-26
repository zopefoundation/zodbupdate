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

import pickle
import cPickle
import logging

logger = logging.getLogger('zodbupdate')


class PythonUnpickler(pickle.Unpickler):
    """Use Python unpickler.
    """
    dispatch = pickle.Unpickler.dispatch.copy()

    def __init__(self, input_file, persistent_load, find_global):
        pickle.Unpickler.__init__(self, input_file)
        self.__repickle = False
        self.persistent_load = persistent_load
        self.find_class = find_global

    def load_reduce(self):
        stack = self.stack
        args = stack.pop()
        func = stack[-1]
        if args is None:
            # Hack for old ExtensionClass that was removed from Python
            # in 2.6. We set repickle to True to trigger a repickling
            # of this pickle later on to get ride of those records.
            value = func.__new__(func)
            self.__repickle = True
            logger.warning(
                'Warning: Pickle contains ExtensionClass hack for %s' % func)
        else:
            value = func(*args)
        stack[-1] = value

    def need_repickle(self):
        """Tell the user if it is necessary to repickle the pickle to
        update it.
        """
        return self.__repickle

    dispatch[pickle.REDUCE] = load_reduce


def CUnpickler(input_file, persistent_load, find_global):
    """Use C unpickler.
    """
    unpickler = cPickle.Unpickler(input_file)
    unpickler.persistent_load = persistent_load
    unpickler.find_global = find_global
    return unpickler


UNPICKLERS = {
    'Python': PythonUnpickler,
    'C': CUnpickler}
