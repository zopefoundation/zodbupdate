===============================================================
zodbupdate - Update existing databases to match your software
=============================================================

This package provides a tool that automatically identifies and updates
references from persistent objects to classes that are in the process of being
moved from one module to another and/or being renamed.

If a class is being moved or renamed, you need to update all references from
your database to the new name before finally deleting the old code.

This tool looks through all current objects of your database, identifies
moved/renamed classes and `touches` objects accordingly. It creates a single
transaction that contains the update of your database.

Having run this tool, you are then free to delete the old code.

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
    recipe = zc.recipe.eggs
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
