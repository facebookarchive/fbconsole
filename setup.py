#!/usr/bin/env python
#
# Copyright 2010 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from setuptools import setup

setup(
    name='fbconsole',
    version='0.3',
    description='A simple facebook api client for writing command line scripts.',
    author='Paul Carduner, Facebook',
    author_email='pcardune@fb.com',
    url='http://github.com/facebook/fbconsole',
    package_dir={'': 'src'},
    py_modules=[
        'fbconsole',
    ],
    license="Apache 2.0",
    install_requires=['poster'],
    zip_safe=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Topic :: Utilities',
        ],
    test_suite = "fbconsole.test_suite",
    entry_points = """
      [console_scripts]
      fbconsole = fbconsole:shell
    """,

    )
