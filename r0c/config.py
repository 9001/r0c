# -*- coding: utf-8 -*-
if __name__ == '__main__':
	raise RuntimeError('\r\n{0}\r\n\r\n  this file is part of retr0chat.\r\n  enter the parent folder of this file and run:\r\n\r\n    python -m r0c <telnetPort> <netcatPort>\r\n\r\n{0}'.format('*'*72))


# the admin password
ADMIN_PWD = u'hunter2'


import platform
import sys
import os

PY2 = (sys.version_info[0] == 2)
WINDOWS = platform.system() == 'Windows'


# two example values are listed for each config attribute;
# the first for debug purposes, the second for regular use

# log incoming traffic from clients
LOG_RX = True
LOG_RX = False

# log outgoing traffic to clients
LOG_TX = True
LOG_TX = False

# show negotiations etc
DBG = True
DBG = False

# start monitoring threads on ctrl-c
THREADMON = True
THREADMON = False

# show all traffic from clients
HEXDUMP_IN = True
HEXDUMP_IN = False

# show all traffic to clients
HEXDUMP_OUT = True
HEXDUMP_OUT = False

# filter packets larger than N bytes from being hexdumped
HEXDUMP_TRUNC = 65535
HEXDUMP_TRUNC = 1
HEXDUMP_TRUNC = 128

# set true for a really bad "slow network" simulation
SLOW_MOTION_TX = True
SLOW_MOTION_TX = False

# force clients into linemode (to debug linemode UI)
FORCE_LINEMODE = True
FORCE_LINEMODE = False

# dump statistics every 2 seconds
BENCHMARK = True
BENCHMARK = False

# logrotate
MESSAGES_PER_LOG_FILE = 16
MESSAGES_PER_LOG_FILE = 512
MESSAGES_PER_LOG_FILE = 131072

# max number of messages to load from disk when joining a channel
MAX_HIST_LOAD = 64
MAX_HIST_LOAD = 65536

# max number of messages in channel scrollback before truncating
MAX_HIST_MEM = 80
MAX_HIST_MEM = 98304

# number of messages to remove every time the chan gets 2big
# (may cause a full redraw of some clients focused on chan)
MSG_TRUNC_SIZE = 8
MSG_TRUNC_SIZE = 16384

# width of the hexdump, in bytes per line
HEX_WIDTH = 16

##
## end of config
##


# determine directories
SYS_ROOT = None
APP_ROOT = None
DOC_ROOT = None
LOG_ROOT = None
for dirname in sys.path:
	doc_rel = 'share/doc/r0c/help/'
	if dirname.endswith('/site-packages'):
		dirname = os.path.realpath(dirname + '/../../../') + '/'
		if os.path.isfile(dirname + doc_rel + 'help-topics.md'):
			SYS_ROOT = dirname
			DOC_ROOT = dirname + doc_rel

if SYS_ROOT is not None:
	if WINDOWS:
		APP_ROOT = os.environ['APPDATA'] + '/r0c/'
	else:
		APP_ROOT = os.path.expanduser("~") + '/.r0c/'

else:
	if os.path.isfile('./docs/help-topics.md'):
		SYS_ROOT = '/'
		APP_ROOT = './'
		DOC_ROOT = './docs/'
	else:
		raise RuntimeError('\n\n   could not find "help-topics.md", your installation is broken\n')

LOG_ROOT = APP_ROOT + '/log/'
