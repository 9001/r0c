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
import datetime
import time
import sys
import os

PY2 = (sys.version_info[0] == 2)

if PY2:
	from Queue import Queue
else:
	from queue import Queue



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
	
	n_verbs = {}
	for k, v in verbs.items():
		n_verbs[k[0]] = v
	verbs = n_verbs
	
	n_subjects = {}
	for k, v in subjects.items():
		n_subjects[k[0]] = v
	subjects = n_subjects

	n_neg_ok = []
	for v in neg_ok:
		n_neg_ok.append(v[0])
	neg_ok = n_neg_ok



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
		ascstr += ''.join(map(lambda b: chr(b) if b >= 0x20 and b < 0x7f else '.', pk[ofs:ofs+8]))
		ascstr += ' '
		hexlen += 8
		ofs += 8
		
		if hexlen >= HEX_WIDTH or ofs >= lpk - 1:
			print('{0}{1:8x}  {2}{3}{4}'.format(
				prefix, hexofs, hexstr,
				' '*(ascstr_width-len(hexstr)), ascstr))
			hexofs = ofs
			hexstr = ''
			hexlen = 0
			ascstr = ''

def trunc(txt, maxlen):
	#print('truncating to {0}: {1}'.format(maxlen, txt))
	clen = 0
	ret = u''
	pend = None
	counting = True
	az = 'abcdefghijklmnopqrstuvwxyz'
	for ch in txt:
		if not counting:
			#print('[{0}] not counted'.format(ch))
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



class Printer:
	
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



class TelnetHost(asyncore.dispatcher):

	def __init__(self, p, host, port):
		asyncore.dispatcher.__init__(self)
		self.p = p
		self.clients = []
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		#help(self)
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
		remote = TelnetClient(self, socket, addr)
		self.clients.append(remote)
	
	def broadcast(self, message):
		for client in self.clients:
			client.say(message)
	
	def part(self, remote):
		self.clients.remove(remote)
		self.broadcast('User disconnected: {0}'.format(remote.addr))
		self.con('  -', remote.addr)



class Client(asyncore.dispatcher):
	
	def __init__(self, host, socket, address):
		asyncore.dispatcher.__init__(self, socket)
		self.host = host
		self.socket = socket
		self.outbox = Queue()
		self.replies = Queue()
		self.backlog = None
		self.incoming = b''
		self.linebuf = u''
		self.linepos = 0
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

		self.w = 80
		self.h = 24
		for x in range(self.h):
			self.screen.append(u'*' * self.w)
		
		self.nick = 'dude'

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
		
		if len(msg) < 100:
			hexdump(msg, 'out ')
		else:
			print('out        :  [{0} byte]'.format(len(msg)))
		
		sent = self.send(msg)
		self.backlog = msg[sent:]
	
	def update_status_line(self):
		hhmmss = datetime.datetime.utcnow().strftime('%H:%M:%S')
		nChan = 1
		nChans = 3
		nUsers = 17
		chan_name = u'general'
		hilight_chans = u'\033[33mH \033[1m2,5,8\033[22;39m'
		active_chans = u'\033[32mA \033[1m1,3,4,6,7\033[22;39m'
		line = trunc(
			u'\033[0;37;44;48;5;235m{0}   {1} #{2}   {3}   {4}'.format(
			hhmmss, nChan, chan_name, hilight_chans, active_chans, nUsers), self.w)
		if self.screen[self.h-2] == line:
			return False
		else:
			self.screen[self.h-2] = line
			return True
	
	def update_text_input(self):
		visible_text = self.linebuf
		line = u'\033[0;36m{0}>\033[0m {1}'.format(self.nick, visible_text)
		if self.screen[self.h-1] == line:
			return False
		else:
			self.screen[self.h-1] = line
			return True
	
	def send_lines(self, to_send):
		print('sending lno.  {0}'.format(to_send))
		msg = u''
		for n in to_send:
			msg += u'\033[{0}H{1}\033[K'.format(n+1, self.screen[n])
		msg += u'\033[{0};{1}H'.format(self.h, len(self.nick) + 3 + self.linepos)
		self.say(msg.encode('utf-8'))
	
	def read_cb(self, full_redraw, text):
		# TODO: parse cursor keys, backspace, etc
		self.linebuf = self.linebuf[:self.linepos] + text + self.linebuf[self.linepos:]
		self.linepos += len(text)
		
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

		to_send = []
		
		if full_redraw:
			self.screen = ['x'] * self.h

		# top bar
		top_bar = u'\033[44;48;5;235;38;5;220mtopic goes here'
		if self.screen[0] != top_bar:
			self.screen[0] = top_bar
			to_send.append(0)
		
		# chat view
		for n in range(self.h - 3):
			line = u'{0}<{1:-4d}>{2}<>'.format(
				u'\033[0m' if n==0 else '',
				n + 1, '*' * (self.w - 8))
			
			if self.screen[n+1] != line:
				self.screen[n+1] = line
				to_send.append(n+1)
		
		if self.update_status_line():
			to_send.append(self.h-2)
		
		if self.update_text_input():
			to_send.append(self.h-1)
		
		self.send_lines(to_send)
		
		## backspace
		#while True:
		#	ofs = txstr.find(u'\x7f')
		#	if ofs < 0:
		#		break
		#	if ofs == 0:
		#		txstr = txstr[ofs+1:]
		#	else:
		#		txstr = txstr[:ofs-1] + txstr[ofs+1:]
		#
		
		## newline
		##
		## putty: 0d 0a
		## winxp: 0d 0a
		## linux: 0d 00
		#if b'\r\0' in self.txbuf:
		#	last_newline = self.txbuf.rfind(b'\r\0')
		#	print('last_newline = {0}'.format(last_newline))
		#	self.txbuf = self.txbuf[last_newline+1:]



class TelnetClient(Client):
	
	def __init__(self, host, socket, address):
		Client.__init__(self, host, socket, address)
		self.replies.put(b'\xff\xfe\x22')  # don't linemode
		self.replies.put(b'\xff\xfb\x01')  # will echo
		self.replies.put(b'\xff\xfd\x1f')  # do naws
		
	def handle_read(self):
		data = self.recv(MSG_LEN)
		if not data:
			self.host.part(self)
		
		hexdump(data, 'in  ')
		
		self.incoming += data
		
		text = u''
		full_redraw = False
		
		while self.incoming:
			
			len_at_start = len(self.incoming)
			
			try:
				src = u'{0}'.format(self.incoming.decode('utf-8'))
				self.incoming = self.incoming[0:0]
			
			except UnicodeDecodeError as uee:
				
				# first check whether the offending byte is an inband signal
				if len(self.incoming) > uee.start and self.incoming[uee.start] == xff:
					
					# it is, keep the text before it
					src = u'{0}'.format(self.incoming[:uee.start].decode('utf-8'))
					self.incoming = self.incoming[uee.start:]
				
				else:
					
					# it can't be helped
					print('warning: unparseable data:')
					hexdump(self.incoming, 'XXX ')
					src = u'{0}'.format(self.incoming[:uee.start].decode('utf-8', 'backslashreplace'))
					self.incoming = self.incoming[0:0]  # todo: is this correct?
			
			#self.linebuf = self.linebuf[:self.linepos] + src + self.linebuf[self.linepos:]
			#self.linepos += len(src)
			text += src
			
			if self.incoming and self.incoming[0] == xff:
				#cmd = b''.join([self.incoming[:3]])
				cmd = self.incoming[:3]
				if len(cmd) < 3:
					print('need more data')
					break
				
				if verbs.get(cmd[1]):
					if not subjects.get(cmd[2]):
						print('[X] subject not implemented: '.format(b2hex(cmd)))
						continue
			
					print('negotiation:  {0} {1} {2}'.format(
						b2hex(cmd), verbs.get(cmd[1]), subjects.get(cmd[2])))
					
					if cmd[:2] == b'\xff\xfe':  # dont
						print('   response:  {0} DONT -> WILL NOT'.format(b2hex(cmd[:3])))
						self.replies.put(b''.join([b'\xff\xfc', cmd[2:3]]))
						#print('           :  {0}'.format(b2hex(response)))
					
					if cmd[:2] == b'\xff\xfd':  # do
						if cmd[2] in neg_ok:
							print('   response:  {0} DO -> WILL'.format(b2hex(cmd[:3])))
							response = b'\xfb' # will
						else:
							print('   response:  {0} DO -> WILL NOT'.format(b2hex(cmd[:3])))
							response = b'\xfd' # wont

						#print('           :  {0}'.format(b2hex(response)))
						self.replies.put(b''.join([b'\xff', response, cmd[2:3]]))
					
					self.incoming = self.incoming[3:]
				
				elif cmd[1] == b'\xfa'[0] and len(self.incoming) >= 3:
					eon = self.incoming.find(b'\xff\xf0')
					if eon <= 0 or eon > 16:
						#print('invalid subnegotiation:')
						#hexdump(self.incoming, 'XXX ')
						#self.incoming = self.incoming[0:0]
						print('need more data')
						break
					else:
						#cmd = b''.join([self.incoming[:12]])  # at least 9
						cmd = self.incoming[:eon]
						self.incoming = self.incoming[eon+2:]
						print('    sub-neg:  {0}'.format(b2hex(cmd)))
						
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
					print('invalid negotiation:')
					hexdump(self.incoming, 'XXX ')
					self.incoming = self.incoming[0:0]
			
			if len(self.incoming) == len_at_start:
				print('unhandled data from client:')
				hexdump(self.incoming, 'XXX ')
				self.incoming = self.incoming[0:0]
			
		self.read_cb(full_redraw, text)


	
def signal_handler(signal, frame):
	print('\n-(!) SHUTDOWN-')
	sys.exit(0)



if __name__ != '__main__':
	print('this is not a library')
	sys.exit(1)

#if True:
#	with open('/home/kog/Documents/telnet.txt', 'rb') as f:
#		d = f.read()
#		print(d)
#		try:
#			print(d.decode('utf-8', 'strict'))
#		except UnicodeDecodeError as uee:
#			print('busted {{{0}..{1}}}'.format(uee.start, uee.end))
#			print(uee)
#			print('bbb')
#		print(d[:9].decode('utf-8', 'strict'))
#		sys.exit(0)

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

p.p('  *  Starting telnet server')
telnet_host = TelnetHost(p, '0.0.0.0', telnet_port)

p.p('  *  Running')
asyncore.loop(0.05)

# while true; do sleep 0.2; t=$(stat -c%Y /free/dev/chatsrv.py); [[ "x$t" != "x$ot" ]] || continue; ot=$t; printf .; ps ax | grep -E 'python[23] \./chatsrv' | awk '{print $1}' | while read pid; do kill -9 $pid; done; done
# cd /free/dev/; while true; do for n in 2 3; do printf '\033[0m'; python$n ./chatsrv.py 23 4312; [[ $? -eq 1 ]] && sleep 1; sleep 0.2; done; done

# cat irc.server.irc.freenode.net.weechatlog | sed -r 's/^....-..-.. ..:..:..[\t ]*--[\t ]*(#[^ ]*)\(([0-9]+)\).*/\2 \1/' | sort -n | grep -vE '^....-..-.. ..:..:..' | uniq -f 1
