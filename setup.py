# vim:fileencoding=utf-8
# Copyright (c) 2008 gocept gmbh & co. kg
# See also LICENSE.txt

from setuptools import setup, find_packages


setup(name='zodbupgrade',
      version='0',
      package_dir={'': 'src'},
      packages=find_packages('src'),
      include_package_data=True,
      install_requires=[
          'ZODB3==3.8.1',
          'setuptools'
      ],
      )
