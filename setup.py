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
    with open(x) as f:
        return f.read()


tests_require = [
    'persistent',
    'zope.interface',
]

setup(name='zodbupdate',
      author='Zope Developers',
      author_email='zodb-dev@zope.org',
      url='https://github.com/zopefoundation/zodbupdate/',
      license='ZPL 2.1',
      description='Update ZODB class references for moved or renamed classes.',
      classifiers=[
          "Development Status :: 6 - Mature",
          "Framework :: Zope :: 2",
          "Framework :: Zope :: 3",
          "Framework :: Zope :: 4",
          "License :: OSI Approved :: Zope Public License",
          "Operating System :: OS Independent",
          "Programming Language :: Python",
          "Programming Language :: Python :: 2",
          "Programming Language :: Python :: 2.7",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.5",
          "Programming Language :: Python :: 3.6",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: 3.8",
          "Programming Language :: Python :: Implementation :: CPython",
      ],
      long_description=(
          read('README.rst')
          + '\n' +
          read('CHANGES.rst')),
      version='1.3',
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
      extras_require={'test': tests_require},
      zip_safe=False,
      entry_points={
          "console_scripts": ['zodbupdate = zodbupdate.main:main']
      },
      test_suite="zodbupdate.tests.test_suite",
)
