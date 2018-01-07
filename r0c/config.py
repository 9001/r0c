# -*- coding: utf-8 -*-
if __name__ == '__main__':
	raise RuntimeError('\n{0}\n{1}\n{2}\n{0}\n'.format('*'*72,
		'  this file is part of retr0chat',
		'  run r0c.py instead'))

DBG = True
#DBG = False

HEXDUMP_IN = True
#HEXDUMP_IN = False

HEXDUMP_OUT = True
#HEXDUMP_OUT = False

HEXDUMP_TRUNC = 65535
HEXDUMP_TRUNC = 128

SLOW_MOTION_TX = True
SLOW_MOTION_TX = False

FORCE_LINEMODE = True
FORCE_LINEMODE = False

CODEC = 'cp437'

MSG_LEN = 8192
HEX_WIDTH = 16
