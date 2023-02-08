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

import contextlib
import io
import logging
import sys
import types

import zodbpickle
from ZODB.broken import Broken
from ZODB.broken import find_global
from ZODB.broken import rebuild

from zodbupdate import utils


logger = logging.getLogger('zodbupdate.serialize')
known_broken_modules = {}

# types to skip when renaming/migrating databases
SKIP_SYMBS = [('ZODB.blob', 'Blob')]


def create_broken_module_for(symb):
    """If your pickle refer a broken class (not an instance of it, a
       reference to the class symbol itself) you have no choice than
       having this module available in the same symbol and with the
       same name, otherwise repickling doesn't work (as both pickle
       and cPickle __import__ the module, and verify the class symbol
       is the same than the one provided).
    """
    parts = symb.__module__.split('.')
    previous = None
    for fullname, name in reversed(
            [('.'.join(parts[0:p + 1]), parts[p])
             for p in range(0, len(parts))]):
        if fullname not in sys.modules:
            if fullname not in known_broken_modules:
                module = types.ModuleType(fullname)
                module.__name__ = name
                module.__file__ = '<broken module to pickle class reference>'
                module.__path__ = []
                known_broken_modules[fullname] = module
            else:
                if previous:
                    module = known_broken_modules[fullname]
                    setattr(module, *previous)
                break
            if previous:
                setattr(module, *previous)
            previous = (name, module)
        else:
            if previous:
                setattr(sys.modules[fullname], *previous)
                break
    if symb.__module__ in known_broken_modules:
        setattr(known_broken_modules[symb.__module__], symb.__name__, symb)
    elif symb.__module__ in sys.modules:
        setattr(sys.modules[symb.__module__], symb.__name__, symb)


class BrokenModuleFinder:
    """This broken module finder works with create_broken_module_for.
    """

    def load_module(self, fullname):
        module = known_broken_modules[fullname]
        if fullname not in sys.modules:
            sys.modules[fullname] = module
        module.__loader__ = self
        return module

    def find_module(self, fullname, path=None):
        if fullname in known_broken_modules:
            return self
        return None


sys.meta_path.append(BrokenModuleFinder())


class NullIterator:
    """An empty iterator that doesn't gives any result.
    """

    def __iter__(self):
        return self

    def __next__(self):
        raise StopIteration()


class IterableClass(type):

    def __iter__(cls):
        """Define a empty iterator to fix unpickling of missing
        Interfaces that have been used to do alsoProvides on a another
        pickled object.
        """
        return NullIterator()


class ZODBBroken(Broken, metaclass=IterableClass):
    """Extend ZODB Broken to work with broken objects that doesn't
    have any __Broken_newargs__ sets (which happens if their __new__
    method is not called).
    """

    def __reduce__(self):
        """We pickle broken objects in hope of being able to fix them later.
        """
        return (rebuild,
                ((self.__class__.__module__, self.__class__.__name__)
                 + getattr(self, '__Broken_newargs__', tuple())),
                self.__Broken_state__)


class ZODBReference:
    """Class to remember reference we don't want to touch.
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

    def __init__(
            self, renames, decoders, pickle_protocol=3, repickle_all=False,
            encoding=None):
        self.__added = dict()
        self.__renames = renames
        self.__decoders = decoders
        self.__changed = False
        self.__protocol = pickle_protocol
        self.__repickle_all = repickle_all
        self.__encoding = encoding
        self.__unpickle_options = {}
        if encoding:
            self.__unpickle_options = {
                'encoding': encoding,
                'errors': 'bytes',
            }

    def __update_symb(self, symb_info):
        """This method look in a klass or symbol have been renamed or
        not. If the symbol have not been renamed explicitly, it's
        loaded and its location is checked to see if it have moved as
        well.
        """
        if symb_info in SKIP_SYMBS:
            self.__skipped = True

        if symb_info in self.__renames:
            self.__changed = True
            return self.__renames[symb_info]
        else:
            symb = find_global(*symb_info, Broken=ZODBBroken)
            if utils.is_broken(symb):
                logger.warning('Warning: Missing factory for {}'.format(
                    ' '.join(symb_info)))
                create_broken_module_for(symb)
            elif hasattr(symb, '__name__') and hasattr(symb, '__module__'):
                new_symb_info = (symb.__module__, symb.__name__)
                if new_symb_info != symb_info:
                    logger.info('New implicit rule detected {} to {}'.format(
                        ' '.join(symb_info), ' '.join(new_symb_info)))
                    self.__renames[symb_info] = new_symb_info
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
        # This takes care of returning the OID as bytes in order to convert
        # a database to Python 3.
        if isinstance(reference, tuple):
            oid, cls_info = reference
            if isinstance(cls_info, tuple):
                cls_info = self.__update_symb(cls_info)
            return ZODBReference(
                (utils.safe_binary(oid), cls_info))
        if isinstance(reference, list):
            if len(reference) == 1:
                oid, = reference
                return ZODBReference(
                    ['w', (utils.safe_binary(oid))])
            mode, information = reference
            if mode == 'm':
                database_name, oid, cls_info = information
                if isinstance(cls_info, tuple):
                    cls_info = self.__update_symb(cls_info)
                return ZODBReference(
                    ['m', (database_name, utils.safe_binary(oid), cls_info)])
            if mode == 'n':
                database_name, oid = information
                return ZODBReference(
                    ['m', (database_name, utils.safe_binary(oid))])
            if mode == 'w':
                if len(information) == 1:
                    oid, = information
                    return ZODBReference(
                        ['w', (utils.safe_binary(oid))])
                oid, database_name = information
                return ZODBReference(
                    ['w', (utils.safe_binary(oid), database_name)])
        if isinstance(reference, (str, zodbpickle.binary)):
            oid = reference
            return ZODBReference(utils.safe_binary(oid))
        raise AssertionError('Unknown reference format.')

    def __persistent_id(self, obj):
        """Save the given object as a reference only if it was a
        reference before. We re-use the same information.
        """
        if not isinstance(obj, ZODBReference):
            return None
        return obj.ref

    def __unpickler(self, input_file):
        """Create an unpickler with our custom global symbol loader
        and reference resolver.
        """
        return utils.Unpickler(
            input_file,
            self.__persistent_load,
            self.__find_global,
            **self.__unpickle_options)

    def __pickler(self, output_file):
        """Create a pickler able to save to the given file, objects we
        loaded while paying attention to any reference we loaded.
        """
        return utils.Pickler(
            output_file, self.__persistent_id, self.__protocol)

    def __update_class_meta(self, class_meta):
        """Update class information, which can contain information
        about a renamed class.
        """
        if isinstance(class_meta, tuple):
            symb, args = class_meta
            if utils.is_broken(symb):
                symb_info = (symb.__module__, symb.__name__)
                logger.warning(
                    'Warning: Missing factory for {}'.format(
                        ' '.join(symb_info)))
                return (symb_info, args)
            elif isinstance(symb, tuple):
                return self.__update_symb(symb), args
        return class_meta

    def __decode_data(self, class_meta, data):
        if not self.__decoders:
            return
        key = None
        if isinstance(class_meta, type):
            key = (class_meta.__module__, class_meta.__name__)
        elif isinstance(class_meta, tuple):
            symb, args = class_meta
            if isinstance(symb, type):
                key = (symb.__module__, symb.__name__)
            elif isinstance(symb, tuple):
                key = symb
            else:
                raise AssertionError('Unknown class format.')
        else:
            raise AssertionError('Unknown class format.')
        for decoder in self.__decoders.get(key, []):
            self.__changed = decoder(data) or self.__changed

    @contextlib.contextmanager
    def __patched_encoding(self):
        if self.__encoding:
            orig = utils.ENCODING
            utils.ENCODING = self.__encoding
            try:
                yield
            finally:
                utils.ENCODING = orig
        else:
            yield

    def rename(self, input_file):
        """Take a ZODB record (as a file object) as input. We load it,
        replace any reference to renamed class we know of. If any
        modification are done, we save the record again and return it,
        return None otherwise.
        """
        self.__changed = False
        self.__skipped = False

        with self.__patched_encoding():
            unpickler = self.__unpickler(input_file)
            class_meta = unpickler.load()
            if self.__skipped:
                # do not do renames/conversions on blob records
                return None
            class_meta = self.__update_class_meta(class_meta)

            data = unpickler.load()
            self.__decode_data(class_meta, data)

            if not (self.__changed or self.__repickle_all):
                return None

            output_file = io.BytesIO()
            pickler = self.__pickler(output_file)
            try:
                pickler.dump(class_meta)
                pickler.dump(data)
            except utils.PicklingError as error:
                logger.error(
                    f'Error: cannot pickle modified record: {error}')
                # Could not pickle that record, skip it.
                return None

            output_file.truncate()
            return output_file

    def get_rules(self, implicit=False, explicit=False):
        rules = {}
        if explicit:
            rules.update(self.__renames)
        if implicit:
            rules.update(self.__added)
        return rules
