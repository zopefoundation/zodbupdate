=============================================================
zodbupdate - Update existing databases to match your software
=============================================================

This package provides a tool that automatically identifies and updates
references from persistent objects to classes that are in the process of being
moved from one module to another and/or being renamed.

If a class is being moved or renamed, you need to update all references from
your database to the new name before finally deleting the old code.

This tool looks through all current objects of your database,
identifies moved/renamed classes and `touches` objects accordingly. It
creates transactions that contains the update of your database (one
transaction every 100,000 records).

Having run this tool, you are then free to delete the old code.

.. contents::

Usage
=====

Installing the egg of this tool provides a console script `zodbupdate` which
you can call giving either a FileStorage filename or a configuration file
defining a storage::

    $ zodbupdate -f Data.fs
    $ zodbupdate -c zodb.conf

Detailed usage information is available:

    $ zodbupdate -h

Custom software/eggs
--------------------

It is important to install this egg in an interpreter/environment where your
software is installed as well. If you're using a regular Python installation
or virtualenv, just installing the package using easy_install should be fine.

If you are using buildout, installing can be done using the egg recipe with
this configuration::

    [buildout]
    parts += zodbupdate

    [zodbupdate]
    recipe = zc.recipe.egg
    eggs = zodbupdate
        <list additional eggs here>

If you do not install `zodbupdate` together with the necessary software it
will report missing classes and not touch your database.

Non-FileStorage configurations
------------------------------

You can configure any storage known to your ZODB installation by providing a
ZConfig configuration file (similar to zope.conf). For example you can connect
to a ZEO server by providing a config file `zeo.conf`::

    <zeoclient>
        server 127.0.0.1:8100
        storage 1
    </zeoclient>

And then running `zodbupdate` using:

    $ zodbupdate -c zeo.conf


Pre-defined rename rules
------------------------

Rename rules can be defined using an entry point called ``zodbupdate``::

    setup(...
          entry_points = """
          [zodbupdate]
          renames = mypackage.mymodule:rename_dict
          """)

These can also be defined in python::

    setup(...
          entry_points={
            'zodbupdate': ['renames = mypackage.mymodule:rename_dict'],
          })

Those entry points must points to dictionaries that map old class
names to new class names::

    rename_dict = {
        'mypackage.mymodule ClassName':
        'otherpackage.othermodule OtherClass'}

As soon as you have rules defined, you can already remove the old
import location mentioned in them.


Packing
-------

The option ``--pack`` will pack the storage on success. (You tell your
users to use that option. If they never pack their storage, it is a good
occasion).


Converting to Python 3
----------------------

``zodbupdate`` can be used to migrate a database created with a Python
2 application to be usable with the same application in Python 3. To
accomplish this, you need to:

1. Stop your application. Nothing should be written to the database
   while the migration is running.

2. Update your Python 2 application to use the latest ZODB version. It
   will not work with ZODB 3.

3. With Python 2, run ``zodbupdate --pack --convert-py3``.

If you use a Data.fs we recommend you to use the ``-f`` option to
specify your database. After the conversion the magic header of the
database will be updated so that you will be able to open the database
with Python 3.

If you use a different storage (like RelStorage), be sure you will be
connecting to it using your Python 3 application after the
migration. You will still be able to connect to your database and use
your application with Python 2 without errors, but then you will need
to convert it again to Python 3.

While the pack is not required, it is highly recommended.

The conversion will take care of the following tasks:

- Updating stored Python datetime, date and time objects to use
  Python 3 bytes,

- Updating ZODB references to use Python 3 bytes.

- Optionally convert stored strings to either unicode or bytes pending
  your configuration.

If your application expect to use bytes in Python 3, they must be
stored as such in the database, and all other strings must be stored
as unicode string, if they contain other characters than ascii characters.

When using ``--convert-py3``, ``zodbupdate`` will load a set of
decoders from the entry points::

    setup(...
          entry_points = """
          [zodbupdate.decode]
          decodes = mypackage.mymodule:decode_dict
          """)

Decoders are dictionaries that specifies as keys attributes on
Persistent classes that must either be encoded as bytes (if the value
is ``binary``) or decoded to unicode using value as encoding (for
instance ``utf-8`` here)::

    decode_dict = {
       'mypackage.mymodule ClassName attribute': 'binary',
       'otherpackage.othermodule OtherClass other_attribute': 'utf-8'}

Please note that for the moment only attributes on Persistent classes
are supported.

Please also note that these conversion rules are _only_ selected for the 
class that is referenced in the pickle, rules for superclasses are _not_ 
applied. This means that you have to push down annotation rules to all 
the subclasses of a superclass that has a field that needs this annotation.

Converting to Python 3 from within Python 3
-------------------------------------------

``zodbupdate`` can also be run from within Python 3 to convert a database
created with Python 2 to be usable in Python 3. However this works
slightly differently than when running the conversion using Python 2.
In Python 3 you must specify a default encoding to use while unpickling strings:
``zodbupdate --pack --convert-py3 --encoding utf-8``.

For each string in the database, zodbupdate will convert it as follows:

1. If it's an attribute configured explicitly via a decoder as described
   above, it will be decoded or encoded as specified there.
2. Otherwise the value will be decoded using the encoding specified
   on the command line.
3. If there is an error while decoding using the encoding specified
   on the command line, the value will be stored as bytes.

Problems and solutions
----------------------

Your Data.fs has POSKey errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you call `zodbupdate` with ``-f`` and the path to your Data.fs,
records triggering those errors will be ignored.

You have another error
~~~~~~~~~~~~~~~~~~~~~~

We recommend to run zodbupdate with ``-v -d`` to get the
maximum of information.

If you are working on big storages, you can use the option ``-o`` to
re-run `zodbupdate` at a failing record you previously encountered
afterward.
