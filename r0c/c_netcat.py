# -*- coding: utf-8 -*-
from __future__ import print_function
if __name__ == '__main__':
	raise RuntimeError('\n{0}\n{1}\n{2}\n{0}\n'.format('*'*72,
		'  this file is part of retr0chat',
		'  run r0c.py instead'))

import asyncore
import sys

from .util    import *
from .c_vt100 import *

PY2 = (sys.version_info[0] == 2)



class NetcatServer(VT100_Server):

	def __init__(self, host, port, world):
		VT100_Server.__init__(self, host, port, world)

	def gen_remote(self, socket, addr, user):
		return NetcatClient(self, socket, addr, self.world, user)



class NetcatClient(VT100_Client):
	
	def __init__(self, host, socket, address, world, user):
		VT100_Client.__init__(self, host, socket, address, world, user)
		self.request_terminal_size()

	def handle_read(self):
		with self.mutex:
			if self.dead:
				print('XXX reading when dead')
				return

			data = self.recv(8192)
			if not data and not self.dead:
				self.host.part(self)
				return
			
			if HEXDUMP_IN:
				hexdump(data, '-->>')
			
			self.in_bytes += data
			
			try:
				src = u'{0}'.format(self.in_bytes.decode(self.codec))
				self.in_bytes = self.in_bytes[0:0]
			
			except UnicodeDecodeError as uee:
				if len(self.in_bytes) < uee.start + 6:
					print('need more data to parse unicode codepoint at {0} in {1} ...probably'.format(
						uee.start, len(self.in_bytes)))
					hexdump(self.in_bytes[-8:], 'XXX ')
					return
				else:
					# it can't be helped
					print('warning: unparseable data:')
					hexdump(self.in_bytes, 'XXX ')
					src = u'{0}'.format(self.in_bytes[:uee.start].decode(self.codec, 'backslashreplace'))
					self.in_bytes = self.in_bytes[0:0]  # todo: is this correct?
			
			#self.linebuf = self.linebuf[:self.linepos] + src + self.linebuf[self.linepos:]
			#self.linepos += len(src)
			self.in_text += src
			
			self.read_cb(False)
