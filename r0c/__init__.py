# -*- coding: utf-8 -*-
from __future__ import print_function
#print('### hello from __init__.py #################################')

import platform
import sys
import os

WINDOWS = platform.system() == 'Windows'
PY2     = (sys.version_info[0] == 2)
if PY2:
	sys.dont_write_bytecode = True

from .__version__ import *

###
### determine runtime environment
#
# setting the following members:
# env: top of the python environment
# doc: help files and documentation
# src: our source code directory
# app: ~/.r0c || %appdata%/r0c
# log: logfiles and client config

class Pod(object):
	pass

EP = Pod()

def init_envpaths():
	# look for our documentation in PYTHONPATH
	found = False
	for env_root in sys.path:
		doc_rel = 'share/doc/r0c/help/'
		if env_root.endswith('/test/..'):
			return
		
		if env_root.endswith(os.sep + 'site-packages'):
			for n in range(4):
				dirname = os.path.realpath(env_root + '/' + ('../'*n)) + '/'
				if os.path.isfile(dirname + doc_rel + 'help-topics.md'):
					EP.env = dirname
					EP.doc = dirname + doc_rel
					EP.src = env_root + '/r0c/'
					found = True
					break
			
			if found:
				break

	if found:
		if WINDOWS:
			EP.app = os.environ['APPDATA'] + '/r0c/'
		else:
			EP.app = os.path.expanduser("~") + '/.r0c/'

	else:
		# check if we're running from source tree
		if os.path.isfile('./docs/help-topics.md'):
			EP.env = '/'
			EP.doc = './docs/'
			EP.src = './r0c/'
			EP.app = './'
		else:
			raise RuntimeError('\n\n   could not find "help-topics.md", your r0c is broken\n')

	# frequently used paths derived from those detected above
	EP.log = os.path.realpath(EP.app + '/log')

	# ensure they're all absolute
	for key in 'env doc src app log'.split(' '):
		path = os.path.realpath(getattr(EP, key))
		setattr(EP, key, path.rstrip('/\\') + os.sep)

	# what seems to be the officer problem
	# raise RuntimeError('\n' + '\n'.join(key + ': ' + getattr(EP, key) for key in 'env src app doc log'.split(' ')) + '\n')


init_envpaths()
