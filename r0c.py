#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function
from __future__ import with_statement

"""r0c.py: retr0chat Telnet/Netcat Server"""
__version__   = "0.9"
__author__    = "ed <a@ocv.me>"
__credits__   = ["stackoverflow.com"]
__license__   = "MIT"
__copyright__ = 2017

import threading
import asyncore
import socket
import signal
import struct
import base64
import hashlib
import datetime
import time
import sys
import os

PY2 = (sys.version_info[0] == 2)

if PY2:
	from Queue import Queue
else:
	from queue import Queue



DBG = True
HEXDUMP_IN = True
HEXDUMP_OUT = False

MSG_LEN = 8192
HEX_WIDTH = 16



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

neg_ok = [
	b'\x01',  # echo
	b'\x03',  # suppress go-ahead
	b'\x1f'   # negotiate window size
]

xff = b'\xff'
xf0 = b'\xf0'

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
	neg_ok   = list_2to3(neg_ok)



def fmt():
	return time.strftime('%d/%m/%Y, %H:%M:%S')

def num(c):
	try:
		return int(c)
	except:
		return None

def b2hex(data):
	if PY2:
		return ' '.join(map(lambda b: format(ord(b), "02x"), data))
	else:
		if type(data) is str:
			return ' '.join(map(lambda b: format(ord(b), "02x"), data))
		else:
			return ' '.join(map(lambda b: format(b, "02x"), data))

def hexdump(pk, prefix=''):
	lpk = len(pk)
	ofs = 0
	hexofs = 0
	hexlen = 0
	hexstr = ''
	ascstr = ''
	ascstr_width = int(HEX_WIDTH * 100 / 32)  # 32h = 100a, 16h = 50a
	while ofs < lpk:
		hexstr += b2hex(pk[ofs:ofs+8])
		hexstr += '  '
		if PY2:
			ascstr += ''.join(map(lambda b: b if ord(b) >= 0x20 and ord(b) < 0x7f else '.', pk[ofs:ofs+8]))
		else:
			ascstr += ''.join(map(lambda b: chr(b) if b >= 0x20 and b < 0x7f else '.', pk[ofs:ofs+8]))
		ascstr += ' '
		hexlen += 8
		ofs += 8
		
		if hexlen >= HEX_WIDTH or ofs >= lpk:
			print('{0}{1:8x}  {2}{3}{4}'.format(
				prefix, hexofs, hexstr,
				' '*(ascstr_width-len(hexstr)), ascstr))
			hexofs = ofs
			hexstr = ''
			hexlen = 0
			ascstr = ''

def trunc(txt, maxlen):
	clen = 0
	ret = u''
	pend = None
	counting = True
	az = 'abcdefghijklmnopqrstuvwxyz'
	for ch in txt:
		if not counting:
			ret += ch
			if ch in az:
				counting = True
		else:
			if pend:
				pend += ch
				if pend.startswith(u'\033['):
					counting = False
				else:
					clen += len(pend)
					counting = True
				ret += pend
				pend = None
			else:
				if ch == u'\033':
					pend = u'{0}'.format(ch)
				else:
					ret += ch
					clen += 1
		if clen >= maxlen:
			return ret
	return ret



class Printer(object):
	
	def __init__(self):
		self.mutex = threading.Lock()
	
	def p(self, data, usercount=None):
		with self.mutex:
			if len(data) < 13:
				data += ' ' * 13
			if usercount:
				sys.stdout.write('%s\n     %d users\r' % (data, usercount))
			else:
				sys.stdout.write('%s\n' % (data,))
			sys.stdout.flush()



class World(object):
	def __init__(self):
		self.users = []      # User instances
		self.chans = []      # NChannel instances

	def add_user(self, user):
		self.users.append(user)
		# announce it



class NChannel(object):
	def __init__(self):
		self.name = u''
		self.users = []      # UChannel instances



class UChannel(object):
	def __init__(self):
		self.user = None     # the user which this object belongs to
		self.chan = None     # the NChannel object
		self.last_ts = None  # last time the user viewed this channel



class User(object):
	def __init__(self, world, address):
		self.world = world
		self.client = None        # the client which this object belongs to
		self.chans = []           # UChannel instances
		self.nick = None
				
		plain_base = u'lammo/{0}'.format(address[0])

		for sep in u'/!@#$%^&*()_+-=[]{};:<>,.':

			plain = plain_base
			while True:
				#print(plain)
				hashed = hashlib.sha256(plain).digest()
				hashed = base64.b64encode(hashed).replace('+','').replace('/','')[:6]
				#print(hashed)

				ok = True
				for user in self.world.users:
					if user.nick == hashed:
						ok = False
						break

				if ok:
					self.nick = hashed
					break
				else:
					if len(plain) > 100:
						break
					plain += '/{0}'.format(address[1])

			if self.nick:
				break
		
		if not self.nick:
			raise RuntimeException("out of legit nicknames")



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
		remote = TelnetClient(self, socket, addr, world, user)
		self.world.add_user(user)
		self.clients.append(remote)
	
	def broadcast(self, message):
		for client in self.clients:
			client.say(message)
	
	def part(self, remote):
		self.clients.remove(remote)
		self.broadcast('User disconnected: {0}'.format(remote.addr))
		self.con('  -', remote.addr)



class Client(asyncore.dispatcher):
	
	def __init__(self, host, socket, address, world, user):
		asyncore.dispatcher.__init__(self, socket)
		self.host = host
		self.socket = socket
		self.world = world
		self.user = user
		self.mutex = threading.Lock()
		self.outbox = Queue()
		self.replies = Queue()
		self.backlog = None
		self.in_bytes = b''
		self.in_text = u''
		self.linebuf = u''
		self.linepos = 0
		self.lineview = 0
		self.screen = []
		
		self.msg_too_small = [
			'your screen is too small',
			'screen is too small',
			'screen too small',
			'screen 2 small',
			'scrn 2 small',
			'too small',
			'2 small',
			'2 smol',
			'2smol',
			':('
		]

		self.esc_tab = {}
		self.add_esc(u'\x1b\x5bD', 'cl')
		self.add_esc(u'\x1b\x5bC', 'cr')
		self.add_esc(u'\x1b\x5bA', 'cu')
		self.add_esc(u'\x1b\x5bB', 'cd')
		self.add_esc(u'\x1b\x5b\x31\x7e', 'home')
		self.add_esc(u'\x1b\x5b\x34\x7e', 'end')
		self.add_esc(u'\x1b\x5b\x35\x7e', 'pgup')
		self.add_esc(u'\x1b\x5b\x36\x7e', 'pgdn')
		self.add_esc(u'\x08', 'bs')
		self.add_esc(u'\x0d\x0a', 'ret')
		self.add_esc(u'\x0d\x00', 'ret')

		self.w = 80
		self.h = 24
		for x in range(self.h):
			self.screen.append(u'*' * self.w)
		
		self.msg_hist = []
		self.msg_hist_n = None

	def add_esc(self, key, act):
		hist = u''
		for c in key:
			hist += c
			if hist == key:
				break
			if hist in self.esc_tab and self.esc_tab[hist]:
				raise RuntimeException('partial escape code [{0}] matching fully defined escape code for [{1}]'.format(
					hist, act))
			self.esc_tab[hist] = False
		if key in self.esc_tab and self.esc_tab[key] != act:
			raise RuntimeException('fully defined escape code [{0}] for [{1}] matches other escape code for [{2}]'.format(
				key, act, self.esc_tab[key]))
		self.esc_tab[key] = act

	def say(self, message):
		self.outbox.put(message)

	def writable(self):
		return (
			self.backlog or
			not self.replies.empty() or
			not self.outbox.empty()
		)

	def handle_write(self):
		if not self.writable():
			return
		
		src = self.replies
		if src.empty():
			src = self.outbox
		
		if self.backlog:
			msg = self.backlog
		else:
			msg = src.get()
		
		if HEXDUMP_OUT:
			if len(msg) < 100:
				hexdump(msg, '<<--')
			else:
				print('<<--       :  [{0} byte]'.format(len(msg)))
		
		sent = self.send(msg)
		self.backlog = msg[sent:]

	def refresh(self, full_redraw, cursor_moved):
		""" compose necessary ansi text and send to client """
		to_send = u''
		to_send += self.update_top_bar(full_redraw)
		to_send += self.update_chat_view(full_redraw)
		to_send += self.update_status_bar(full_redraw)
		to_send += self.update_text_input(full_redraw)
		if to_send or cursor_moved:
			to_send += u'\033[{0};{1}H'.format(self.h, len(self.user.nick) + 2 + self.linepos + 1 - self.lineview)
			self.say(to_send.encode('utf-8'))

	def update_top_bar(self, full_redraw):
		""" no need to optimize this tbh """
		top_bar = u'\033[1H\033[44;48;5;235;38;5;220mtopic goes here\033[K'
		if self.screen[0] != top_bar:
			self.screen[0] = top_bar
			return trunc(top_bar, self.w)
		return u''

	def update_status_bar(self, full_redraw):
		preface = u'\033[{0}H\033[0;37;44;48;5;235m'.format(self.h-1)
		hhmmss = datetime.datetime.utcnow().strftime('%H:%M:%S')
		nChan = 1
		nChans = 3
		nUsers = 17
		chan_name = u'general'
		hilight_chans = u'\033[1;33mh 2,5,8\033[22;39m'
		active_chans = u'\033[1;32ma 1,3,4,6,7\033[22;39m'
		line = trunc(u'{0}{1}   {2} #{3}   {4}   {5}\033[K'.format(
			preface, hhmmss, nChan, chan_name, hilight_chans, active_chans, nUsers), self.w)
		if full_redraw:
			if self.screen[self.h-2] != line:
				self.screen[self.h-2] = line
				return trunc(line, self.w)
		else:
			old = self.screen[self.h-2]
			self.screen[self.h-2] = line
			
			if len(old) != len(line):
				return trunc(line, self.w)

			cutoff = len(preface) + len(hhmmss)
			changed_part1 = old[:cutoff] != line[:cutoff]
			changed_part2 = old[cutoff:] != line[cutoff:]
			
			if changed_part2:
				return trunc(line, self.w)

			if changed_part1:
				return line[:cutoff]
				#return u'\033[{0}H{1}'.format(self.h-1, hhmmss)  # drops colors

		return u''
	
	def update_text_input(self, full_redraw):
		msg_len = len(self.linebuf)
		vis_text = self.linebuf
		free_space = self.w - (len(self.user.nick) + 2 + 1)  # nick chrome + final char on screen
		if msg_len <= free_space:
			self.lineview = 0
		else:
			if self.linepos < self.lineview:
				self.lineview = self.linepos
			elif self.linepos > self.lineview + free_space:
				self.lineview = self.linepos - free_space
			vis_text = vis_text[self.lineview:self.lineview+free_space]
		line = u'\033[0;36m{0}>\033[0m {1}'.format(self.user.nick, vis_text)
		if self.screen[self.h-1] != line:
			self.screen[self.h-1] = line
			return u'\033[{0}H{1}\033[K'.format(self.h, line)
		return u''

	def update_chat_view(self, full_redraw):
		# TODO: naive implementation;
		#       should impl screen scrolling
		ret = u''
		for n in range(self.h - 3):
			line = u'{0}<{1:-4d}>{2}<>'.format(
				u'\033[0m' if n==0 else '',
				n + 1, '*' * (self.w - 8))
			
			if self.screen[n+1] != line:
				self.screen[n+1] = line
				ret += u'\033[{0}H{1}'.format(n+2, self.screen[n+1])
		return ret

	def read_cb(self, full_redraw):
		aside = u''
		old_cursor = self.linepos
		for ch in self.in_text:
			if DBG:
				if ch == '\x03':
					sys.exit(0)
			
			was_esc = None
			if aside and aside in self.esc_tab:
				# text until now is an incomplete escape sequence;
				# if the new character turns into an invalid sequence
				# we'll turn the old one into a plaintext string
				was_esc = aside
			
			aside += ch
			if not aside in self.esc_tab:
				if was_esc:
					# new character made the escape sequence invalid;
					# print old buffer as plaintext and create a new
					# escape sequence buffer for just the new char
					
					if ch in self.esc_tab:
						# ...but only if the new character is
						# potentially the start of a new esc.seq.
						aside = was_esc
					else:
						# in this case it isn't
						was_esc = False
				
				plain = u''
				for pch in aside:
					nch = ord(pch)
					if nch < 0x20 or (nch >= 0x80 and nch < 0x100):
						print('substituting non-printable \\x{0:02x}'.format(nch))
						plain += '?'
					else:
						plain += pch
				
				self.linebuf = self.linebuf[:self.linepos] + plain + self.linebuf[self.linepos:]
				self.linepos += len(plain)
				self.msg_hist_n = None
				
				if was_esc:
					aside = ch
				else:
					aside = u''
			
			else:
				# this is an escape sequence; handle it
				act = self.esc_tab[aside]
				if not act:
					continue
				
				if DBG:
					print('escape sequence [{0}] = {1}'.format(b2hex(aside), act))

				hist_step = 0

				aside = u''
				if act == 'cl':
					self.linepos -= 1
					if self.linepos < 0:
						self.linepos = 0
				elif act == 'cr':
					self.linepos += 1
					if self.linepos > len(self.linebuf):
						self.linepos = len(self.linebuf)
				elif act == 'cu':
					hist_step = -1
				elif act == 'cd':
					hist_step = 1
				elif act == 'home':
					self.linepos = 0
				elif act == 'end':
					self.linepos = len(self.linebuf)
				elif act == 'bs':
					if self.linepos > 0:
						self.linebuf = self.linebuf[:self.linepos-1] + self.linebuf[self.linepos:]
						self.linepos -= 1
				elif act == 'ret':
					if not self.msg_hist or self.msg_hist[-1] != self.linebuf:
						self.msg_hist.append(self.linebuf)
					self.msg_hist_n = None
					self.linebuf = u''
					self.linepos = 0
				else:
					print('unimplemented action: {0}'.format(act))

				if hist_step == 0:
					self.msg_hist_n = None
				else:
					if self.msg_hist_n == None:
						if hist_step < 0:
							self.msg_hist_n = len(self.msg_hist) - 1
					else:
						self.msg_hist_n += hist_step

					if self.msg_hist_n != None:
						if self.msg_hist_n < 0 or self.msg_hist_n >= len(self.msg_hist):
							self.msg_hist_n = None

					if self.msg_hist_n == None:
						self.linebuf = u''
					else:
						self.linebuf = self.msg_hist[self.msg_hist_n]
					self.linepos = 0
		if aside:
			print('need more data for {0} runes: {1}'.format(len(aside), b2hex(aside)))
			self.in_text = aside
		else:
			self.in_text = u''

		if self.w < 20 or self.h < 4:
			msg = 'x'
			for cand in self.msg_too_small:
				print('{0} <= {1}'.format(len(cand), self.w))
				if len(cand) <= self.w:
					msg = cand
					break
			y = int(self.h / 3)
			x = int((self.w - len(msg)) / 2)
			x += 1
			y += 1
			print('2smol @ {0} {1}'.format(x, y))
			msg = u'\033[H\033[1;37;41m\033[J\033[{0};{1}H{2}\033[0m'.format(y,x,msg)
			self.say(msg.encode('utf-8'))
			return

		if full_redraw:
			self.screen = ['x'] * self.h

		self.refresh(full_redraw,
			old_cursor != self.linepos)



class TelnetClient(Client):
	
	def __init__(self, host, socket, address, world, user):
		Client.__init__(self, host, socket, address, world, user)
		self.replies.put(b'\xff\xfe\x22')  # don't linemode
		self.replies.put(b'\xff\xfb\x01')  # will echo
		self.replies.put(b'\xff\xfd\x1f')  # do naws
		
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
					src = u'{0}'.format(self.in_bytes.decode('utf-8'))
					self.in_bytes = self.in_bytes[0:0]
				
				except UnicodeDecodeError as uee:
					
					# first check whether the offending byte is an inband signal
					if len(self.in_bytes) > uee.start and self.in_bytes[uee.start] == xff:
						
						# it is, keep the text before it
						src = u'{0}'.format(self.in_bytes[:uee.start].decode('utf-8'))
						self.in_bytes = self.in_bytes[uee.start:]
					
					else:
						
						# it can't be helped
						print('warning: unparseable data:')
						hexdump(self.in_bytes, 'XXX ')
						src = u'{0}'.format(self.in_bytes[:uee.start].decode('utf-8', 'backslashreplace'))
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
						
						if cmd[:2] == b'\xff\xfe':  # dont
							print('<<-- n.resp:  {0}  DONT -> WILL NOT'.format(b2hex(cmd[:3])))
							self.replies.put(b''.join([b'\xff\xfc', cmd[2:3]]))
							#print('           :  {0}'.format(b2hex(response)))
						
						if cmd[:2] == b'\xff\xfd':  # do
							if cmd[2] in neg_ok:
								print('<<-- n.resp:  {0}  DO -> WILL'.format(b2hex(cmd[:3])))
								response = b'\xfb' # will
							else:
								print('<<-- n.resp:  {0}  DO -> WILL NOT'.format(b2hex(cmd[:3])))
								response = b'\xfd' # wont

							#print('           :  {0}'.format(b2hex(response)))
							self.replies.put(b''.join([b'\xff', response, cmd[2:3]]))
						
						self.in_bytes = self.in_bytes[3:]
					
					elif cmd[1] == b'\xfa'[0] and len(self.in_bytes) >= 3:
						eon = self.in_bytes.find(b'\xff\xf0')
						if eon <= 0 or eon > 16:
							#print('invalid subnegotiation:')
							#hexdump(self.in_bytes, 'XXX ')
							#self.in_bytes = self.in_bytes[0:0]
							print('need more data for sub-negotiation')
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
								
								srch_from = 7
								#print('srch_from {0}'.format(b2hex(cmd[7:])))
								self.w, self.h = struct.unpack('>HH', cmd[3:7])
								print('terminal sz:  {0}x{1}'.format(self.w, self.h))
								if self.w >= 512:
									print('screen width {0} reduced to 80'.format(self.w))
									self.w = 80
								if self.h >= 512:
									print('screen height {0} reduced to 24'.format(self.h))
									self.h = 24
							
					else:
						print('=== invalid negotiation:')
						hexdump(self.in_bytes, 'XXX ')
						self.in_bytes = self.in_bytes[0:0]
				
				if len(self.in_bytes) == len_at_start:
					print('=== unhandled data from client:')
					hexdump(self.in_bytes, 'XXX ')
					self.in_bytes = self.in_bytes[0:0]
			
			self.read_cb(full_redraw)



def push_worker(ifaces):
	last_ts = None
	while True:
		while True:
			ts = time.time()
			its = int(ts)
			if its != last_ts:
				last_ts = its
				#print('=== {0}'.format(its))
				break
			if ts - its < 0.98:
				#print(ts-its)
				time.sleep((1-(ts-its))*0.9)
			else:
				time.sleep(0.01)

		for iface in ifaces:
			for client in iface.clients:
				client.refresh(False, False)



def signal_handler(signal, frame):
	print('\n-(!) SHUTDOWN-')
	sys.exit(0)



if __name__ != '__main__':
	print('this is not a library')
	sys.exit(1)

if len(sys.argv) != 3:
	print('need argument 1:  telnet port (or 0 to disable)')
	print('need argument 2:  netcat port (or 0 to disable)')
	sys.exit(1)

telnet_port = int(sys.argv[1])
netcat_port = int(sys.argv[2])

print('  *  Telnet server on port', telnet_port)
print('  *  NetCat server on port', netcat_port)

p = Printer()

p.p('  *  Capturing ^C')
signal.signal(signal.SIGINT, signal_handler)

p.p('  *  Creating world')
world = World()

p.p('  *  Starting telnet server')
telnet_host = TelnetHost(p, '0.0.0.0', telnet_port, world)

p.p('  *  Starting push driver')
push_thr = threading.Thread(target=push_worker, args=([telnet_host],))
push_thr.daemon = True
push_thr.start()

p.p('  *  Running')
asyncore.loop(0.05)

# while true; do sleep 0.2; t=$(stat -c%Y /free/dev/chatsrv.py); [[ "x$t" != "x$ot" ]] || continue; ot=$t; printf .; ps ax | grep -E 'python[23] \./chatsrv' | awk '{print $1}' | while read pid; do kill -9 $pid; done; done
# cd /free/dev/; while true; do for n in 2 3; do printf '\033[0m'; python$n ./chatsrv.py 23 4312; [[ $? -eq 1 ]] && sleep 1; sleep 0.2; done; done

# cat irc.server.irc.freenode.net.weechatlog | sed -r 's/^....-..-.. ..:..:..[\t ]*--[\t ]*(#[^ ]*)\(([0-9]+)\).*/\2 \1/' | sort -n | grep -vE '^....-..-.. ..:..:..' | uniq -f 1
