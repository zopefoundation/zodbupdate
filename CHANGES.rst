Changes
=======

1.2 (unreleased)
----------------

- Nothing changed yet.


1.1 (2018-10-05)
----------------

- Skip records for ZODB.blob when migrating database to Python 3 to not break
  references to blobfiles.

- When migrating databases to Python 3, do not fail when converting
  attributes containing None.

- Fix tests on Python 2 with ZODB >= 5.4.0, which now uses pickle
  protocol 3.

- Fix `is_broken` check for old-style class instances.

- Add support for Python 3.7.

- Drop PyPy support.


1.0 (2018-02-13)
----------------

- Support Python 2.7 and 3.4, 3.5 and 3.6 and pypy 3. Drop any older
  version of Python.

- The option to the select the pickler (``--pickler``) has been
  removed. This was only useful if you had extension classes with
  Python 2.5 or less.

- Added an option to convert a database to Python 3.

0.5 (2010-10-07)
----------------

- More debug logging shows now the currently processed OID
  (that is helpful to determine which object misses the factory).

- Support for missing factories have been improved: an error used to
  occur if a pickle needed an update and contained a reference to a
  missing class (not instance of this class). This case is now fixed.

- Python 2.4 is no longer supported. Please stick to version 0.3 if
  you need Python 2.4 support.



0.4 (2010-07-14)
----------------

- Add an option to debug broken records.

- Add an option to skip records.

- Add an option to use Python unPickler instead of C one. This let you
  debug records. As well Python unPickler let you update old ExtensionClass
  records who had a special hack in the past.

- Broken interfaces are well supported now (if you did alsoProvides with them).


0.3 (2010-02-02)
----------------

- Unplickle and re-pickle the code to rename references to moved classes.
  This make the script works on database created with older versions of
  ZODB.

- If you are working directly with a FileStorage, POSKeyError are reported
  but non-fatal.

- Remove superfluous code that tried to prevent commits when no changes
  happened: ZODB does this all by itself already.

0.2 (2009-06-23)
----------------

- Add option to store the rename rules into a file.

- Don't commit transactions that have no changes.

- Load rename rules from entry points ``zodbupdate``.

- Compatibility with Python 2.4

- Rename from ``zodbupgrade`` to ``zodbupdate``.

- Add 'verbose' option.

- Improve logging.

- Suppress duplicate log messages (e.g. if the same class is missing in
  multiple objects).

- Improve the updating process: rewrite pickle opcodes instead of blindly
  touching a class. This also allows updating pickles that can't be unpickled
  due to missing classes.

0.1 (2009-06-08)
----------------

- First release.
