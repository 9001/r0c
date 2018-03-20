#!/usr/bin/env python
# coding: utf-8
from __future__ import print_function

import io
import os
import sys
from glob import glob
from shutil import rmtree
try:
	# need setuptools to build wheel
    from setuptools import setup, Command
    setuptools_available = True
except ImportError:
	# works in a pinch
    from distutils.core import setup, Command
    setuptools_available = False
from distutils.spawn import spawn

if 'bdist_wheel' in sys.argv and not setuptools_available:
	print('cannot build wheel without setuptools')
	sys.exit(1)


NAME        = 'r0c'
VERSION     = None


manifest = ''
data_files = [
	('share/doc/r0c',         ['README.md','LICENSE']),
	('share/doc/r0c/help',    glob('docs/*.md')),
	('share/doc/r0c/clients', glob('clients/*'))
]

for dontcare, files in data_files:
	for fn in files:
		manifest += "include {0}\n".format(fn)

here = os.path.abspath(os.path.dirname(__file__))

with open(here + '/MANIFEST.in', 'wb') as f:
	f.write(manifest.encode('utf-8'))

with open(here + '/README.md', 'rb') as f:
	LONG_DESCRIPTION = '\n' + f.read().decode('utf-8')

about = {}
if not VERSION:
	with open(os.path.join(here, NAME, '__version__.py'), 'rb') as f:
		exec(f.read().decode('utf-8'), about)
else:
	about['__version__'] = VERSION


if False:
	data_files = {}
	for dest, src, masks in [
		['share/doc/r0c/help',    'docs',    ['.md']],
		['share/doc/r0c/clients', 'clients', ['']]]:
		
		files = []
		src = here + '/' + src
		for (dirpath, dirnames, filenames) in os.walk(src):
			dirnames.sort()
			for fn in sorted(filenames):
				for mask in masks:
					if fn.endswith(mask):
						files.append(fn)
						break
		
		data_files[dest] = files


args = {
	'name'             : NAME,
	'version'          : about['__version__'],
	'description'      : 'retr0chat telnet/vt100 chat server',
	'long_description' : LONG_DESCRIPTION,
	'author'           : 'ed',
	'author_email'     : 'r0c@ocv.me',
	'url'              : 'https://github.com/9001/r0c',
	'license'          : 'MIT',
	'data_files'       : data_files,
	'classifiers'      : [
		'Development Status :: 5 - Production/Stable',
		'License :: OSI Approved :: MIT License',
		'Programming Language :: Python',
		'Programming Language :: Python :: 2',
		'Programming Language :: Python :: 2.6',
		'Programming Language :: Python :: 2.7',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.0',
		'Programming Language :: Python :: 3.1',
		'Programming Language :: Python :: 3.2',
		'Programming Language :: Python :: 3.3',
		'Programming Language :: Python :: 3.4',
		'Programming Language :: Python :: 3.5',
		'Programming Language :: Python :: 3.6',
		'Programming Language :: Python :: 3.7',
		'Programming Language :: Python :: Implementation :: CPython',
		'Programming Language :: Python :: Implementation :: PyPy',
		'Environment :: Console',
		'Topic :: Communications :: Chat'
	]
}


if setuptools_available:
	args.update({
		'install_requires'     : [],
		'include_package_data' : True,
		'py_modules'           : ['r0c'],
		'entry_points'         : {
			'console_scripts'  : [
				'r0c = r0c.__main__:main'
			]
		}
	})
else:
	args.update({
		'packages' : ['r0c'],
		'scripts'  : ['bin/r0c']
	})


#import pprint
#pprint.PrettyPrinter().pprint(args)
#sys.exit(0)

setup(**args)
