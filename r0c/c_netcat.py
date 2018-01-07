# -*- coding: utf-8 -*-
if __name__ == '__main__':
	raise RuntimeError('\n{0}\n{1}\n{2}\n{0}\n'.format('*'*72,
		'  this file is part of retr0chat',
		'  run r0c.py instead'))

import asyncore
import socket
import sys

from .util    import *
from .c_vt100 import *

PY2 = (sys.version_info[0] == 2)



class NetcatHost(asyncore.dispatcher):

	def __init__(self, p, host, port, world):
		asyncore.dispatcher.__init__(self)
		self.p = p
		self.world = world
		self.clients = []
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		if PY2:
			self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		else:
			self.set_reuse_addr()
		
		self.bind((host, port))
		self.listen(1)

	def con(self, msg, adr, cli=None):
		if (cli is None):
			cli = len(self.clients)
		msg = ' %s %s - %s :%s' % (msg, fmt(), adr[0], adr[1])
		self.p.p(msg, cli)
	
	def handle_accept(self):
		socket, addr = self.accept()
		self.con(' ++', addr, len(self.clients) + 1)
		user = User(self.world, addr)
		remote = TelnetClient(self, socket, addr, self.world, user)
		user.post_init(remote)
		self.world.add_user(user)
		self.clients.append(remote)
		remote.handshake_world = True
	
	def broadcast(self, message):
		for client in self.clients:
			client.say(message)
	
	def part(self, remote):
		self.clients.remove(remote)
		self.broadcast('User disconnected: {0}'.format(remote.addr))
		self.con('  -', remote.addr)



class TelnetClient(VT100_Client):
	
	def __init__(self, host, socket, address, world, user):
		VT100_Client.__init__(self, host, socket, address, world, user)
		self.request_terminal_size()

	def handle_read(self):
		with self.mutex:
			data = self.recv(MSG_LEN)
			if not data:
				self.host.part(self)
			
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
