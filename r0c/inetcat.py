# -*- coding: utf-8 -*-
from __future__ import print_function
from .__init__ import *
if __name__ == '__main__':
	raise RuntimeError('\r\n{0}\r\n\r\n  this file is part of retr0chat.\r\n  enter the parent folder of this file and run:\r\n\r\n    python -m r0c <telnetPort> <netcatPort>\r\n\r\n{0}'.format('*'*72))

import asyncore
import sys

from .util   import *
from .ivt100 import *



class NetcatServer(VT100_Server):

	def __init__(self, host, port, world, other_if):
		VT100_Server.__init__(self, host, port, world, other_if)
		self.user_config_path = EP.log + 'cfg.netcat'

	def gen_remote(self, socket, addr, user):
		return NetcatClient(self, socket, addr, self.world, user)



class NetcatClient(VT100_Client):
	
	def __init__(self, host, socket, address, world, user):
		VT100_Client.__init__(self, host, socket, address, world, user)
		
		self.looks_like_telnet = {
			b'\xff\xfe': 1,
			b'\xff\xfd': 1,
			b'\xff\xfc': 1,
			b'\xff\xfb': 1
		}
		# trick telnet into revealing itself:
		# request client status and location
		self.replies.put(b'\xff\xfd\x05\xff\xfd\x17')
		

	def handle_read(self):
		with self.world.mutex:
			if self.dead:
				print('XXX reading when dead')
				return

			data = self.recv(8192)
			if not data:
				if not self.dead:
					self.host.part(self)
				return
			
			if HEXDUMP_IN:
				hexdump(data, '-->>')

			if self.wire_log and LOG_RX:
				self.wire_log.write('{0:.0f}\n'.format(
					time.time()*1000).encode('utf-8'))
				hexdump(data, '>', self.wire_log)
			
			self.in_bytes += data

			if b'\xff' in data:
				ofs = 0
				while ofs >= 0:
					ofs = data.find(b'\xff', ofs)
					if ofs < 0:
						break
					if data[ofs:ofs+2] in self.looks_like_telnet:
						self.num_telnet_negotiations += 1
					ofs = ofs + 1
			
			try:
				src = u'{0}'.format(self.in_bytes.decode(self.codec))
				self.in_bytes = self.in_bytes[0:0]
			
			except UnicodeDecodeError as uee:
				if len(self.in_bytes) < uee.start + 6:
					print('need more data to parse unicode codepoint at {0} in {1}'.format(
						uee.start, len(self.in_bytes)))
					hexdump(self.in_bytes[-8:], 'XXX ')
					src = u'{0}'.format(self.in_bytes[:uee.start].decode(self.codec))
					self.in_bytes = self.in_bytes[uee.start:]
				else:
					# it can't be helped
					print('warning: unparseable data:')
					hexdump(self.in_bytes, 'XXX ')
					src = u'{0}'.format(self.in_bytes[:uee.start].decode(self.codec, 'backslashreplace'))
					self.in_bytes = self.in_bytes[0:0]  # todo: is this correct?
			
			self.in_text += src

			if self.wizard_stage is not None \
			and len(self.in_text_full) < 1024:
				self.in_text_full += src
			
			self.read_cb(False, len(src))

