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

from setuptools import find_packages
from setuptools import setup


def read(x):
    with open(x) as f:
        return f.read()


tests_require = [
    'persistent',
    'zope.interface',
    'relstorage',
]

setup(name='zodbupdate',
      author='Zope Developers',
      author_email='zope-dev@zope.dev',
      url='https://github.com/zopefoundation/zodbupdate/',
      license='ZPL 2.1',
      description='Update ZODB class references for moved or renamed classes.',
      classifiers=[
          "Development Status :: 6 - Mature",
          "Framework :: Zope :: 3",
          "Framework :: Zope :: 5",
          "License :: OSI Approved :: Zope Public License",
          "Operating System :: OS Independent",
          "Programming Language :: Python",
          "Programming Language :: Python :: 3",
          "Programming Language :: Python :: 3.7",
          "Programming Language :: Python :: 3.8",
          "Programming Language :: Python :: 3.9",
          "Programming Language :: Python :: 3.10",
          "Programming Language :: Python :: 3.11",
          "Programming Language :: Python :: Implementation :: CPython",
      ],
      long_description=(
          read('README.rst')
          + '\n' +
          read('CHANGES.rst')),
      version='2.0',
      keywords='zodb update upgrade migrate data pickle',
      package_dir={'': 'src'},
      packages=find_packages('src'),
      include_package_data=True,
      python_requires='>=3.7',
      install_requires=[
          'ZODB',
          'setuptools',
          'transaction',
          'zodbpickle',
      ],
      extras_require={'test': tests_require},
      zip_safe=False,
      entry_points={
          "console_scripts": ['zodbupdate = zodbupdate.main:main']
      },
      )
