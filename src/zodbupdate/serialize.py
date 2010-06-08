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

from ZODB.broken import find_global, Broken, rebuild
import cPickle
import cStringIO
import logging
import types

logger = logging.getLogger('zodbupdate')


def isbroken(symb):
    return isinstance(symb, types.TypeType) and Broken in symb.__mro__


class ZODBBroken(Broken):
    """Extend ZODB Broken to work with broken objects that doesn't
    have any __Broken_newargs__ sets (which happens if their __new__
    method is not called).
    """

    def __reduce__(self):
        """We pickle broken objects in hope of being able to fix them later.
        """
        return (rebuild,
                ((self.__class__.__module__, self.__class__.__name__)
                 + getattr(self, '__Broken_newargs__', ())),
                self.__Broken_state__)


class ZODBReference:
    """Class to remenber reference we don't want to touch.
    """

    def __init__(self, ref):
        self.ref = ref


class ObjectRenamer:
    """This load and save a ZODB record, modifying all references to
    renamed class according the given renaming rules:

    - in global symbols contained in the record,

    - in persistent reference information,

    - in class information (first pickle of the record).
    """

    def __init__(self, changes):
        self.__added = dict()
        self.__changes = dict()
        for old, new in changes.iteritems():
            self.__changes[tuple(old.split(' '))] = tuple(new.split(' '))
        self.__changed = False

    def __update_symb(self, symb_info):
        """This method look in a klass or symbol have been renamed or
        not. If the symbol have not been renamed explicitly, it's
        loaded and its location is checked to see if it have moved as
        well.
        """
        if symb_info in self.__changes:
            self.__changed = True
            return self.__changes[symb_info]
        else:
            symb = find_global(*symb_info, Broken=ZODBBroken)
            if isbroken(symb):
                logger.warning(u'Warning: Missing factory for %s' %
                               u' '.join(symb_info))
            elif hasattr(symb, '__name__') and hasattr(symb, '__module__'):
                new_symb_info = (symb.__module__, symb.__name__)
                if new_symb_info != symb_info:
                    logger.info(
                        u'New implicit rule detected %s to %s' %
                        (u' '.join(symb_info), u' '.join(new_symb_info)))
                    self.__changes[symb_info] = new_symb_info
                    self.__added[symb_info] = new_symb_info
                    self.__changed = True
                    return new_symb_info
        return symb_info

    def __find_global(self, *klass_info):
        """Find a class with the given name, looking for a renaming
        rule first.

        Using ZODB find_global let us manage missing classes.
        """
        return find_global(*self.__update_symb(klass_info), Broken=ZODBBroken)

    def __persistent_load(self, reference):
        """Load a persistent reference. The reference might changed
        according a renaming rules. We give back a special object to
        represent that reference, and not the real object designated
        by the reference.
        """
        if isinstance(reference, tuple):
            oid, klass_info = reference
            if isinstance(klass_info, tuple):
                klass_info = self.__update_symb(klass_info)
            return ZODBReference((oid, klass_info))
        if isinstance(reference, list):
            mode, information = reference
            if mode == 'm':
                database_name, oid, klass_info = information
                if isinstance(klass_info, tuple):
                    klass_info = self.__update_symb(klass_info)
                return ZODBReference(['m', (database_name, oid, klass_info)])
        return ZODBReference(reference)

    def __unpickler(self, pickle):
        """Create an unpickler with our custom global symbol loader
        and reference resolver.
        """
        unpickler = cPickle.Unpickler(pickle)
        unpickler.persistent_load = self.__persistent_load
        unpickler.find_global = self.__find_global
        return unpickler

    def __persistent_id(self, obj):
        """Save the given object as a reference only if it was a
        reference before. We re-use the same information.
        """
        if not isinstance(obj, ZODBReference):
            return None
        return obj.ref

    def __pickler(self, output):
        """Create a pickler able to save to the given file, objects we
        loaded while paying attention to any reference we loaded.
        """
        pickler = cPickle.Pickler(output, 1)
        pickler.persistent_id = self.__persistent_id
        return pickler

    def __update_class_meta(self, class_meta):
        """Update class information, which can contain information
        about a renamed class.
        """
        if isinstance(class_meta, tuple):
            symb, args = class_meta
            if isbroken(symb):
                symb_info = (symb.__module__, symb.__name__)
                logger.warning(u'Warning: Missing factory for %s' %
                               u' '.join(symb_info))
                return (symb_info, args)
            elif isinstance(symb, tuple):
                return self.__update_symb(symb), args
        return class_meta

    def rename(self, input_file):
        """Take a ZODB record (as a file object) as input. We load it,
        replace any reference to renamed class we know of. If any
        modification are done, we save the record again and return it,
        return None otherwise.
        """
        self.__changed = False

        unpickler = self.__unpickler(input_file)
        class_meta = unpickler.load()
        data = unpickler.load()

        class_meta = self.__update_class_meta(class_meta)

        if not self.__changed:
            return None

        output_file = cStringIO.StringIO()
        pickler = self.__pickler(output_file)
        try:
            pickler.dump(class_meta)
            pickler.dump(data)
        except cPickle.PicklingError:
            # Could not pickle that record, likely due to a broken
            # class ignore it.
            return None

        output_file.truncate()
        return output_file

    def get_found_implicit_rules(self):
        result = {}
        for old, new in self.__added.items():
            result[' '.join(old)] = ' '.join(new)
        return result
