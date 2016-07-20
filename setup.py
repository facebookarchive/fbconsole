#!/usr/bin/env python
#
# Copyright 2014-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

import sys
from setuptools import setup

PY3 = sys.version_info[0] == 3

install_requires = [
    'six',
    'anyjson',
    ]
extra = {}
if PY3:
    extra['use_2to3'] = True
else:
    install_requires.extend([
            'poster',
            'mechanize',
            ])

if sys.version_info[0] == 2 and sys.version_info[1] == 5:
    install_requires.extend([
            'simplejson',
            ])


setup(
    name='fbconsole',
    version='0.4',
    description='A simple facebook api client for writing command line scripts.',
    author='Paul Carduner, Facebook',
    author_email='pcardune@fb.com',
    url='http://github.com/fbsamples/fbconsole',
    package_dir={'': 'src'},
    py_modules=[
        'fbconsole',
    ],
    license="BSD",
    install_requires=install_requires,
    zip_safe=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: BSD',
        'Operating System :: OS Independent',
        'Topic :: Utilities',
        ],
    test_suite = "fbconsole.test_suite",
    entry_points = """
      [console_scripts]
      fbconsole = fbconsole:shell
    """,
    **extra
    )
