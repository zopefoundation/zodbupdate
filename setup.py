##############################################################################
#
# Copyright (c) 2009 Zope Corporation and Contributors.
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

from setuptools import setup, find_packages


def read(x):
    return open(x).read()


tests_require = [
    'persistent',
    'zope.interface',
]

setup(name='zodbupdate',
      author='Zope Developers',
      author_email='zodb-dev@zope.org',
      url='http://www.python.org/pypi/zodbupdate',
      license='ZPL 2.1',
      description='Update ZODB class references for moved or renamed classes.',
      long_description=(
        read('README.rst')
        + '\n' +
        read('CHANGES.rst')),
      version='1.1.dev0',
      package_dir={'': 'src'},
      packages=find_packages('src'),
      include_package_data=True,
      install_requires=[
          'ZODB',
          'setuptools',
          'six',
          'transaction',
          'zodbpickle',
      ],
      test_suite='zodbupdate.tests.test_suite',
      tests_require=tests_require,
      extras_require={'test': tests_require},
      entry_points={
          "console_scripts": ['zodbupdate = zodbupdate.main:main']
      })
