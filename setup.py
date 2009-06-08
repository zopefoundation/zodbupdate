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


setup(name='zodbupgrade',
      author='Zope Developers',
      author_email='zodb-dev@zope.org',
      description=
        'Update ZODB class references for moved or renamed classes.',
      long_description=(
        read('README.txt')
        + '\n' +
        read('TODO.txt')
        + '\n' +
        read('CHANGES.txt')),
      version='0.1dev',
      package_dir={'': 'src'},
      packages=find_packages('src'),
      include_package_data=True,
      install_requires=[
          'ZODB3',
          'setuptools'
      ],
      entry_points = dict(
        console_scripts =
            ['zodbupgrade = zodbupgrade.main:main']))
