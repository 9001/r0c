# -*- coding: utf-8 -*-
if __name__ == '__main__':
	raise RuntimeError('\n{0}\n{1}\n{2}\n{0}\n'.format('*'*72,
		'  this file is part of retr0chat',
		'  run r0c.py instead'))

import asyncore
import socket
import struct
import sys

from .util    import *
from .c_vt100 import *

PY2 = (sys.version_info[0] == 2)

# from net::telnet (telnet.rb) doc by William Webber and Wakou Aoyama
# OPT_([^ ]*) .*("\\x..") # (.*)
# \2 = "\1 \3",
subjects = {
	b"\x00": "BINARY (Binary Transmission)",
	b"\x01": "ECHO (Echo)",
	b"\x02": "RCP (Reconnection)",
	b"\x03": "SGA (Suppress Go Ahead)",
	b"\x04": "NAMS (Approx Message Size Negotiation)",
	b"\x05": "STATUS (Status)",
	b"\x06": "TM (Timing Mark)",
	b"\x07": "RCTE (Remote Controlled Trans and Echo)",
	b"\x08": "NAOL (Output Line Width)",
	b"\x09": "NAOP (Output Page Size)",
	b"\x0a": "NAOCRD (Output Carriage-Return Disposition)",
	b"\x0b": "NAOHTS (Output Horizontal Tab Stops)",
	b"\x0c": "NAOHTD (Output Horizontal Tab Disposition)",
	b"\x0d": "NAOFFD (Output Formfeed Disposition)",
	b"\x0e": "NAOVTS (Output Vertical Tabstops)",
	b"\x0f": "NAOVTD (Output Vertical Tab Disposition)",
	b"\x10": "NAOLFD (Output Linefeed Disposition)",
	b"\x11": "XASCII (Extended ASCII)",
	b"\x12": "LOGOUT (Logout)",
	b"\x13": "BM (Byte Macro)",
	b"\x14": "DET (Data Entry Terminal)",
	b"\x15": "SUPDUP (SUPDUP)",
	b"\x16": "SUPDUPOUTPUT (SUPDUP Output)",
	b"\x17": "SNDLOC (Send Location)",
	b"\x18": "TTYPE (Terminal Type)",
	b"\x19": "EOR (End of Record)",
	b"\x1a": "TUID (TACACS User Identification)",
	b"\x1b": "OUTMRK (Output Marking)",
	b"\x1c": "TTYLOC (Terminal Location Number)",
	b"\x1d": "3270REGIME (Telnet 3270 Regime)",
	b"\x1e": "X3PAD (X.3 PAD)",
	b"\x1f": "NAWS (Negotiate About Window Size)",
	b"\x20": "TSPEED (Terminal Speed)",
	b"\x21": "LFLOW (Remote Flow Control)",
	b"\x22": "LINEMODE (Linemode)",
	b"\x23": "XDISPLOC (X Display Location)",
	b"\x24": "OLD_ENVIRON (Environment Option)",
	b"\x25": "AUTHENTICATION (Authentication Option)",
	b"\x26": "ENCRYPT (Encryption Option)",
	b"\x27": "NEW_ENVIRON (New Environment Option)",
	b"\xff": "EXOPL (Extended-Options-List)"
}

verbs = {
	b"\xfe": "DONT",
	b"\xfd": "DO",
	b"\xfc": "WONT",
	b"\xfb": "WILL"
}

xff = b'\xff'
xf0 = b'\xf0'



if not FORCE_LINEMODE:
	# standard operation procedure;
	# we'll handle all rendering

	neg_will = [
		b'\x1f',  # negotiate window size
		b'\x01',  # echo
		b'\x03'   # suppress go-ahead
	]

	neg_wont = [
	]

	neg_dont = [
		b'\x25'   # authentication
	]

	initial_neg =  b''
	initial_neg += b'\xff\xfb\x03'  # will sga
	initial_neg += b'\xff\xfb\x01'  # will echo
	initial_neg += b'\xff\xfd\x1f'  # do naws

else:
	# debug / negative test;
	# have client linebuffer
	
	neg_will = [
		b'\x1f'   # negotiate window size
	]

	neg_wont = [
		b'\x01',  # echo
		b'\x03'   # suppress go-ahead
	]

	initial_neg =  b''
	#initial_neg += b'\xff\xfc\x03'  # won't sga
	#initial_neg += b'\xff\xfc\x01'  # won't echo
	initial_neg += b'\xff\xfd\x01'  # do echo
	initial_neg += b'\xff\xfd\x22'  # do linemode
	initial_neg += b'\xff\xfd\x1f'  # do naws





if not PY2:
	xff = 0xff
	xf0 = 0xf0
	
	def dict_2to3(src):
		ret = {}
		for k, v in src.items():
			ret[k[0]] = v
		return ret

	def list_2to3(src):
		ret = []
		for v in src:
			ret.append(v[0])
		return ret
	
	verbs    = dict_2to3(verbs)
	subjects = dict_2to3(subjects)
	neg_will = list_2to3(neg_will)
	neg_wont = list_2to3(neg_wont)



class TelnetHost(asyncore.dispatcher):

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
		remote.conf_wizard()
	
	def broadcast(self, message):
		for client in self.clients:
			client.say(message)
	
	def part(self, remote):
		self.clients.remove(remote)
		#print('{0} was in {1} chans, {2}'.format(remote.user.nick, len(remote.user.chans), remote.user.chans[-1].alias or remote.user.chans[-1].nchan.name))
		for uchan in list(remote.user.chans):
			#print('leaving {0}'.format(uchan.alias or uchan.nchan.name))
			self.world.part_chan(uchan)
			#self.world.send_chan_msg('--', uchan.nchan, '\033[36m{0} has left\033[22m')
		#self.broadcast('User disconnected: {0}'.format(remote.addr))
		#self.con('  -', remote.addr)



class TelnetClient(VT100_Client):
	
	def __init__(self, host, socket, address, world, user):
		VT100_Client.__init__(self, host, socket, address, world, user)
		
		#if FORCE_LINEMODE:
		#	self.y_input, self.y_status = self.y_status, self.y_input

		self.neg_done = []
		self.replies.put(initial_neg)

	def handle_read(self):
		with self.mutex:
			data = self.recv(MSG_LEN)
			if not data:
				self.host.part(self)
			
			if HEXDUMP_IN:
				hexdump(data, '-->>')
			
			self.in_bytes += data
			
			full_redraw = False
			
			while self.in_bytes:
				
				len_at_start = len(self.in_bytes)
				
				try:
					src = u'{0}'.format(self.in_bytes.decode(self.codec))
					#print('got {0} no prob'.format(src))
					#print('got {0} runes: {1}'.format(len(src),
					#	b2hex(src.encode('utf-8'))))
					self.in_bytes = self.in_bytes[0:0]
				
				except UnicodeDecodeError as uee:
					
					# first check whether the offending byte is an inband signal
					if len(self.in_bytes) > uee.start and self.in_bytes[uee.start] == xff:
						
						# it is, keep the text before it
						src = u'{0}'.format(self.in_bytes[:uee.start].decode(self.codec))
						self.in_bytes = self.in_bytes[uee.start:]

					elif len(self.in_bytes) < uee.start + 6 and self.codec != 'ascii':
						
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
				
				if self.in_bytes and self.in_bytes[0] == xff:
					#cmd = b''.join([self.in_bytes[:3]])
					cmd = self.in_bytes[:3]
					if len(cmd) < 3:
						print('need more data for generic negotiation')
						break
					
					if verbs.get(cmd[1]):
						if not subjects.get(cmd[2]):
							print('[X] subject not implemented: '.format(b2hex(cmd)))
							continue

						print('-->> negote:  {0}  {1} {2}'.format(
							b2hex(cmd), verbs.get(cmd[1]), subjects.get(cmd[2])))

						response = None
						if cmd in self.neg_done:
							print('-><- n.loop:  {0}'.format(b2hex(cmd)))

						elif cmd[:2] == b'\xff\xfe':  # dont
							response = b'\xfc'        # will not
							if cmd[2] in neg_will:
								response = b'\xfb'    # will

						elif cmd[:2] == b'\xff\xfd':  # do
							response = b'\xfb'        # will
							if cmd[2] in neg_wont:
								response = b'\xfc'    # will not
						
						if response is not None:
							print('<<-- n.resp:  {0}  {1} -> {2}'.format(
								b2hex(cmd[:3]), verbs.get(cmd[1]), verbs.get(response[0])))
							self.replies.put(b''.join([b'\xff', response, cmd[2:3]]))
							self.neg_done.append(cmd)
					
						self.in_bytes = self.in_bytes[3:]
					
					elif cmd[1] == b'\xfa'[0] and len(self.in_bytes) >= 3:
						eon = self.in_bytes.find(b'\xff\xf0')
						if eon <= 0:
							#print('invalid subnegotiation:')
							#hexdump(self.in_bytes, 'XXX ')
							#self.in_bytes = self.in_bytes[0:0]
							print('need more data for sub-negotiation: {0}'.format(
								b2hex(self.in_bytes)))
							break
						else:
							#cmd = b''.join([self.in_bytes[:12]])  # at least 9
							cmd = self.in_bytes[:eon]
							self.in_bytes = self.in_bytes[eon+2:]
							print('-->> subneg:  {0}'.format(b2hex(cmd)))
							
							if cmd[2] == b'\x1f'[0]:
								full_redraw = True
								
								# spec says to send \xff\xff in place of \xff
								# for literals in negotiations, some clients do
								while True:
									ofs = cmd.find(b'\xff\xff')
									if ofs < 0:
										break
									cmd = cmd[:ofs] + cmd[ofs+1:]
								print('           :  {0}'.format(b2hex(cmd)))
								
								self.w, self.h = struct.unpack('>HH', cmd[3:7])
								print('terminal sz:  {0}x{1}'.format(self.w, self.h))
								if self.w >= 512:
									print('screen width {0} reduced to 80'.format(self.w))
									self.w = 80
								if self.h >= 512:
									print('screen height {0} reduced to 24'.format(self.h))
									self.h = 24

								self.handshake_sz = True
							
					else:
						print('=== invalid negotiation:')
						hexdump(self.in_bytes, 'XXX ')
						self.in_bytes = self.in_bytes[0:0]
				
				if len(self.in_bytes) == len_at_start:
					print('=== unhandled data from client:')
					hexdump(self.in_bytes, 'XXX ')
					self.in_bytes = self.in_bytes[0:0]
			
			self.read_cb(full_redraw)
