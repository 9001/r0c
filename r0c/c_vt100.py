# -*- coding: utf-8 -*-
from __future__ import print_function
if __name__ == '__main__':
	raise RuntimeError('\r\n{0}\r\n\r\n  this file is part of retr0chat.\r\n  enter the parent folder of this file and run:\r\n\r\n    python -m r0c <telnetPort> <netcatPort>\r\n\r\n{0}'.format('*'*72))

import traceback
import threading
import asyncore
import socket
import datetime
import sys

from .config import *
from .util   import *
from .chat   import *
from .unrag  import *

PY2 = (sys.version_info[0] == 2)

if PY2:
	from Queue import Queue
else:
	from queue import Queue


class VT100_Server(asyncore.dispatcher):

	def __init__(self, host, port, world):
		asyncore.dispatcher.__init__(self)
		self.world = world
		self.clients = []
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		if PY2:
			self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		else:
			self.set_reuse_addr()
		
		self.bind((host, port))
		self.listen(1)

	def con(self, msg, adr, add=0):
		print(' {0} {1}  {2}  {3} :{4}'.format(
			msg, fmt(), len(self.clients)+add, adr[0], adr[1]))
	
	def gen_remote(self, socket, addr, user):
		raise RuntimeError('inherit me')

	def handle_accept(self):
		socket, addr = self.accept()
		self.con(' ++', addr, 1)
		user = User(self.world, addr)
		remote = self.gen_remote(socket, addr, user)
		user.post_init(remote)
		self.world.add_user(user)
		self.clients.append(remote)
		remote.handshake_world = True
		remote.conf_wizard()
	
	def broadcast(self, message):
		for client in self.clients:
			client.say(message)
	
	def part(self, remote):
		remote.dead = True
		with self.world.mutex:
			#print('==[part]' + '='*72)
			#traceback.print_stack()
			#print('==[part]' + '='*71)
			
			remote.close()
			self.con('  -', remote.addr, -1)
			self.clients.remove(remote)
			for uchan in list(remote.user.chans):
				self.world.part_chan(uchan)



class VT100_Client(asyncore.dispatcher):
	
	def __init__(self, host, socket, address, world, user):
		asyncore.dispatcher.__init__(self, socket)
		#self.mutex = threading.RLock()
		self.host = host
		self.socket = socket
		self.world = world
		self.user = user
		self.dead = False      # set true at disconnect (how does asyncore work)

		# config
		self.y_input = 0       # offset from bottom of screen
		self.y_status = 1      # offset from bottom of screen
		self.linemode = False  # set true by buggy clients
		self.echo_on = False   # set true by buffy clients
		self.vt100 = True      # set nope by butty clients
		self.slowmo_tx = SLOW_MOTION_TX
		self.codec = 'utf-8'

		# outgoing data
		self.outbox = Queue()
		self.replies = Queue()
		self.last_tx = None

		# incoming data
		self.backlog = None
		self.in_bytes = b''
		self.in_text = u''

		# incoming requests
		self.scroll_cmd = None

		# input buffer
		self.linebuf = u''
		self.linepos = 0
		self.lineview = 0
		self.msg_hist = []
		self.msg_hist_n = None

		# state registers
		self.wizard_stage = 'start'
		self.wizard_lastlen = 0
		self.wizard_maxdelta = 0
		self.handshake_sz = False
		self.handshake_world = False
		self.need_full_redraw = False
		self.too_small = False
		self.screen = []
		self.w = 80
		self.h = 24
		
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
		self.add_esc(u'\x09', 'tab')
		self.add_esc(u'\x0d\x0a', 'ret')
		self.add_esc(u'\x0d\x00', 'ret')

		# inetutils-1.9.4
		self.add_esc(u'\x7f', 'bs')
		self.add_esc(u'\x1b\x4f\x48', 'home')
		self.add_esc(u'\x1b\x4f\x46', 'end')

		# hotkeys
		self.add_esc(u'\x12', 'redraw')
		self.add_esc(u'\x01', 'prev-chan')
		self.add_esc(u'\x18', 'next-chan')

		thr = threading.Thread(target=self.handshake_timeout)
		thr.daemon = True
		thr.start()



	def handshake_timeout(self):
		time.sleep(1)
		self.handshake_sz = True

	def add_esc(self, key, act):
		hist = u''
		for c in key:
			hist += c
			if hist == key:
				break
			if hist in self.esc_tab and self.esc_tab[hist]:
				raise RuntimeError('partial escape code [{0}] matching fully defined escape code for [{1}]'.format(
					b2hex(hist), act))
			self.esc_tab[hist] = False
		if key in self.esc_tab and self.esc_tab[key] != act:
			raise RuntimeError('fully defined escape code [{0}] for [{1}] matches other escape code for [{2}]'.format(
				b2hex(key), act, self.esc_tab[key]))
		self.esc_tab[key] = act

	def request_terminal_size(self):
		pass

	def say(self, message):
		self.outbox.put(message)

	def readable(self):
		return not self.dead

	def writable(self):
		#if self.slowmo_tx:
		#	#print('x')
		#	now = time.time()
		#	if self.last_tx is not None and now - self.last_tx < 0.01:
		#		return False
		#	#print('ooo')
		
		return not self.dead and (
			self.backlog or
			not self.replies.empty() or
			not self.outbox.empty()
		)

	def handle_close(self):
		if not self.dead:
			self.host.part(self)

	def handle_error(self):
		whoops()
		if not self.dead:
			self.host.part(self)



	def handle_write(self):
		if not self.writable():
			return
		
		#if self.slowmo_tx:
		#	self.last_tx = time.time()
		
		src = self.replies
		if src.empty():
			src = self.outbox
		
		if self.backlog:
			msg = self.backlog
		else:
			msg = src.get()
		
		if HEXDUMP_OUT:
			if len(msg) < HEXDUMP_TRUNC:
				hexdump(msg, '<<--')
			else:
				print('<<--       :  [{0} byte]'.format(len(msg)))
		
		if self.slowmo_tx:
			end_pos = next((i for i, ch in enumerate(msg) \
				if i > 128 and ch in [ b' '[0], b'\033'[0] ]), len(msg))
			self.backlog = msg[end_pos:]
			sent = self.send(msg[:end_pos])
			self.backlog = msg[sent:]
			#hexdump(msg[:sent])
			time.sleep(0.02)
			#print('@@@ sent = {0}    backlog = {1}'.format(sent, len(self.backlog)))
		else:
			sent = self.send(msg)
			self.backlog = msg[sent:]
			#print('@@@ sent = {0}    backlog = {1}'.format(sent, len(self.backlog)))



	def refresh(self, cursor_moved):
		""" compose necessary ansi text and send to client """
		with self.world.mutex:
			if  self.too_small or \
				not self.handshake_sz or \
				not self.handshake_world or \
				self.wizard_stage is not None:
				return

			full_redraw = self.need_full_redraw
			self.need_full_redraw = False

			if not self.screen or len(self.screen) != self.h:
				full_redraw = True

			if self.user.new_active_chan:
				self.user.active_chan = self.user.new_active_chan
				self.user.new_active_chan = None
				full_redraw = True
			
			to_send = u''
			fix_color = False

			if full_redraw:
				self.screen = ['x'] * self.h
				if not self.vt100:
					to_send = u'\r\n' * self.h

			to_send += self.update_chat_view(full_redraw)
			if to_send:
				full_redraw = True

			if self.vt100:
				to_send += self.update_top_bar(full_redraw)

			to_send += self.update_status_bar(full_redraw)
			if to_send:
				fix_color = True

			if self.vt100:
				to_send += self.update_text_input(full_redraw)

				if '\033[' in self.linebuf or fix_color:
					to_send += '\033[0m'
				
			#to_send += u'\033[10H' + u'qwertyuiopasdfghjklzxcvbnm'*3

			if not self.vt100:
				self.say(to_send.encode(self.codec, 'backslashreplace'))

			elif to_send or cursor_moved:
				to_send += u'\033[{0};{1}H'.format(self.h - self.y_input,
					len(self.user.nick) + 2 + self.linepos + 1 - self.lineview)
				self.say(to_send.encode(self.codec, 'backslashreplace'))



	def update_top_bar(self, full_redraw):
		""" no need to optimize this tbh """
		uchan = self.user.active_chan
		nchan = uchan.nchan
		topic = nchan.topic
		if nchan.name is None:
			topic = topic.replace('[[uch_a]]', uchan.alias)

		top_bar = u'\033[1H\033[44;48;5;235;38;5;220m{0}\033[K'.format(topic)
		
		if self.screen[0] != top_bar:
			self.screen[0] = top_bar
			return trunc(top_bar, self.w)
		return u''



	def update_status_bar(self, full_redraw):
		preface = u'\033[{0}H\033[0;37;44;48;5;235m'.format(self.h - self.y_status)
		hhmmss = datetime.datetime.utcnow().strftime('%H%M%S')
		uchan = self.user.active_chan
		
		#print('@@@ active chan = {0}, other chans {1}'.format(
		#	self.user.active_chan.alias or self.user.active_chan.nchan.name,
		#	u', '.join(x.alias or x.nchan.name for x in self.user.chans)))

		nbuf  = self.user.chans.index(uchan)
		nchan = uchan.nchan
		chan_name = self.user.active_chan.nchan.name
		chan_hash = '#'
		if chan_name is None:
			# private chat
			chan_hash = '\033[1;37m'
			chan_name = self.user.active_chan.alias

		hilights = []
		activity = []
		for i, chan in enumerate(self.user.chans):
			if chan.hilights:
				hilights.append(i)
			if chan.activity:
				activity.append(i)
		
		if hilights:
			hilights = u'   \033[1;33mh {0}\033[22;39m'.format(','.join(hilights))
		
		if activity:
			activity = u'   \033[1;32ma {0}\033[22;39m'.format(','.join(activity))
		
		offscreen = None
		if not uchan.lock_to_bottom and uchan.vis[-1].im < len(nchan.msgs):
			offscreen = u'  \033[1;36m+{0}\033[22;39m'.format(
				len(nchan.msgs) - uchan.vis[-1].im)

		line = trunc(u'{0}{1}   {2}: {3}{4}{5}{6}{7}\033[K'.format(
			preface, hhmmss,
			nbuf, chan_hash, chan_name,
			offscreen or '',
			hilights or '',
			activity or '',
			len(nchan.uchans)), self.w)
		
		if not self.vt100:
			now = int(time.time())
			if full_redraw or (now % 5 == 1) or ((hilights or activity) and now % 2 == 1):
				return '\r{0}   {1}> '.format(strip_ansi(line), self.user.nick)
				#pad_sz = len(self.user.nick) + 3
				#return '\r{0}{1}\r{2}> '.format(
				#	' '*pad_sz,
				#	strip_ansi(line)[:self.w-pad_sz],
				#	self.user.nick)
			return u''

		elif full_redraw:
			if self.screen[  self.h - (self.y_status + 1) ] != line:
				self.screen[ self.h - (self.y_status + 1) ] = line
				return trunc(line, self.w)

		else:
			old = self.screen[ self.h - (self.y_status + 1) ]
			self.screen[       self.h - (self.y_status + 1) ] = line
			
			if len(old) != len(line):
				return trunc(line, self.w)

			cutoff = len(preface) + len(hhmmss)
			changed_part1 = old[:cutoff] != line[:cutoff]
			changed_part2 = old[cutoff:] != line[cutoff:]
			
			if changed_part2:
				# send all of it
				return trunc(line, self.w)

			if changed_part1:
				if int(time.time()) % 5 == 0:
					# send just the timestamp
					return line[:cutoff]
					#return u'\033[{0}H{1}'.format(self.h - self.y_status, hhmmss)  # drops colors

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
		if self.screen[  self.h - (self.y_input + 1) ] != line:
			self.screen[ self.h - (self.y_input + 1) ] = line
			return u'\033[{0}H{1}\033[K'.format(self.h - self.y_input, line)
		return u''
	


	def msg2ansi(self, msg, msg_fmt, ts_fmt, msg_nl, msg_w, nick_w):
		ts = datetime.datetime.utcfromtimestamp(msg.ts).strftime(ts_fmt)
		
		#if not self.vt100:
		#	if u'\033' in msg.txt:
		#		txt = strip_ansi(msg.txt)
		#	else:
		#		txt = msg.txt
		#	return [u'\r{0} <{1}> {2}\n'.format(ts, msg.user, txt)]

		if msg.txt.startswith(u'  ') or u'\n' in msg.txt:
			txt = msg.txt.split('\n')  # splitlines removes trailing newline
			for n in range(len(txt)):
				txt[n] = trunc(txt[n], msg_w)
		else:
			txt = unrag(msg.txt, msg_w) or [' ']
		
		for n, line in enumerate(txt):
			if u'\033' in line:
				if self.vt100:
					line += u'\033[0m'
				else:
					line = strip_ansi(line)

			if n == 0:
				c1 = ''
				c2 = ''
				if self.vt100:
					if msg.user == '-info-':
						c1 = '\033[0;32m'
						c2 = '\033[0m'
					elif msg.user == '-err-':
						c1 = '\033[1;33m'
						c2 = '\033[0m'
					elif msg.user == '***':
						c1 = '\033[36m'
						c2 = '\033[0m'

				txt[n] = msg_fmt.format(ts, c1, msg.user[:nick_w], c2, line)
			else:
				txt[n] = msg_nl + line
		
		return txt
	


	def update_chat_view(self, full_redraw):
		ret = u''
		ch = self.user.active_chan
		nch = ch.nchan

		debug_scrolling = False

		#if not self.vt100:
		#	if self.scroll_cmd is not None:
		#		if self.scroll_cmd < 0:
		#			#self.lock_to_bottom = False
		#			# this doesn't work
		#			full_redraw = True
		
		#print('\n@@@ update chat view @@@ {0}'.format(time.time()))
		
		if self.w >= 140:
			nick_w = 18
			msg_w = self.w - 29
			msg_nl = u' ' * 29
			msg_fmt = u'{0}  {1}{2:18}{3} {4}'
			ts_fmt = '%H:%M:%S'
		elif self.w >= 100:
			nick_w = 14
			msg_w = self.w - 25
			msg_nl = u' ' * 25
			msg_fmt = u'{0}  {1}{2:14}{3} {4}'
			ts_fmt = '%H:%M:%S'
		elif self.w >= 80:
			nick_w = 12
			msg_w = self.w - 20
			msg_nl = u' ' * 20
			msg_fmt = u'{0} {1}{2:12}{3} {4}'
			ts_fmt = '%H%M%S'
		elif self.w >= 60:
			nick_w = 8
			msg_w = self.w - 15
			msg_nl = u' ' * 15
			msg_fmt = u'{0} {1}{2:8}{3} {4}'
			ts_fmt = '%H:%M'
		else:
			nick_w = 8
			msg_w = self.w - 9
			msg_nl = u' ' * 9
			msg_fmt = u'{1}{2:8}{3} {4}'
			ts_fmt = '%H%M'
		
		# first ensure our cache is sane
		if not ch.vis or \
			len(nch.msgs) <= ch.vis[0].im or \
			nch.msgs[ch.vis[0].im] != ch.vis[0].msg:
			
			try:
				# some messages got pruned from the channel message list
				for vis in ch.vis:
					vis.im = nch.msgs.index(vis.msg)
			except:
				# the pruned messages included the visible ones,
				# scroll client to bottom
				ch.lock_to_bottom = True
				full_redraw = True
		
		if full_redraw:
			lines = []
			lines_left = self.h - 3

			if ch.lock_to_bottom:
				# lock to bottom, full redraw:
				# newest/bottom message will be added first
				ch.vis = []
				for n, msg in enumerate(reversed(nch.msgs)):
					imsg = len(nch.msgs) - n
					txt = self.msg2ansi(msg, msg_fmt, ts_fmt, msg_nl, msg_w, nick_w)
					
					n_vis = len(txt)
					car = 0
					cdr = n_vis
					if n_vis >= lines_left:
						n_vis = lines_left
						car = cdr - n_vis
					
					ch.vis.append(
						VisMessage(msg, txt, imsg, car, cdr))
					
					for ln in reversed(txt[car:]):
						lines.append(ln)
					
					imsg -= 1
					lines_left -= n_vis
					if lines_left <= 0:
						break
				
				ch.vis.reverse()
				lines.reverse()
			
			else:
				# fixed scroll position:
				# oldest/top message will be added first
				top_msg = ch.vis[0]
				imsg = top_msg.im
				ch.vis = []
				for n, msg in enumerate(nch.msgs[ imsg : imsg + self.h-3 ]):
					txt = self.msg2ansi(msg, msg_fmt, ts_fmt, msg_nl, msg_w, nick_w)
					
					#if top_msg is not None:
						# we can keep the exact scroll position
						# as long as the top message has the exact
						# same layout as when it was last displayed
						
						#if len(top_msg.txt) == len(txt):
						#	for n, ln in enumerate(txt):
						#		if top_msg.txt[n] != ln:
						#			top_msg = None
						#			break

					# actually this test is probably accurate enough
					# and still passes chrome changes (padding etc)
					if (top_msg is not None and
						len(top_msg.txt) == len(txt)):

						car = top_msg.car
						cdr = top_msg.cdr
						n_vis = cdr - car
						top_msg = None
						if n_vis > lines_left:
							delta = lines_left - n_vis
							n_vis -= delta
							cdr -= delta

					else:
						# not top message,
						# or no previous top message to compare,
						# or layout changed
						n_vis = len(txt)
						car = 0
						cdr = n_vis
						if n_vis > lines_left:
							n_vis = lines_left
							cdr = n_vis
					
					ch.vis.append(
						VisMessage(msg, txt, imsg, car, cdr))
					
					for ln in txt[car:cdr]:
						lines.append(ln)
					
					imsg += 1
					lines_left -= n_vis
					if lines_left <= 0:
						break
			
			if not self.vt100:
				#ret = u'\r==========================\r\n'
				#print(lines)
				for ln in lines:
					#print('sending {0} of {1}'.format(ln, len(lines)))
					#if isinstance(lines, list):
					#	print('lines is list')
					ret += u'\r{0}{1}\r\n'.format(ln, ' '*((self.w-len(ln))-2))
				return ret

			while len(lines) < self.h - 3:
				lines.append('--')
			
			for n in range(self.h - 3):
				if self.screen[n+1] != lines[n]:
					self.screen[n+1] = lines[n]
					ret += u'\033[{0}H\033[K{1}'.format(n+2, self.screen[n+1])
		
		else:
			# full_redraw = False,
			# do relative scrolling if necessary
			
			t_steps = self.scroll_cmd   # total number of scroll steps
			n_steps = 0                 # number of scroll steps performed
			self.scroll_cmd = None

			lines_in_use = 0
			for msg in ch.vis:
				lines_in_use += msg.cdr - msg.car
			
			if t_steps:
				#print('@@@ have scroll steps')
				ch.lock_to_bottom = False
			else:
				#print('@@@ no scroll steps')
				if not ch.lock_to_bottom:
					# fixed viewport
					#print('@@@ not lock to bottom')
					return ret
				
				if nch.msgs[-1] == ch.vis[-1].msg:
					# no new messages
					#print('@@@ no new messages: {0}'.format(ch.vis[-1].txt[0][:40]))
					return ret
				
				# push all new messages
				t_steps = 99999999999
			
			abs_steps = abs(t_steps)    # abs(total steps)
			
			#print('@@@ gonna scroll {0} lines'.format(abs_steps))

			if False:
				for msg in ch.vis:
					for ln in msg.txt[msg.car:msg.cdr]:
						print(ln)

			# set scroll region:  chat pane
			if self.vt100:
				ret += u'\033[2;{0}r'.format(self.h - 2)

			
			# first / last visible message might have lines off-screen;
			# check those first
			partial = None      # currently offscreen text
			partial_org = None  # unmodified original
			partial_old = None  # currently visible segment
			partial_new = None  # currently invisible segment
			
			# scrolling up; grab offscreen text at top
			if t_steps < 0:
				ref = ch.vis[0]
				if ref.car != 0:

					partial = ref.txt[:ref.car]
					partial_org = ref
					partial_old = VisMessage(
						ref.msg, ref.txt[ref.car:ref.cdr],
						ref.im, 0, ref.cdr-ref.car)
					ch.vis[0] = partial_old

					if debug_scrolling:
						print('@@@ slicing len({0}) car,cdr({1},{2}) into nlen({3})+olen({4}), ncar,ncdr({5},{6})? ocar,ocdr({7},{8})'.format(
							len(partial_org.txt), partial_org.car, partial_org.cdr,
							len(partial), len(partial_old.txt),
							0, len(partial), partial_old.car, partial_old.cdr))
						for ln in partial:
							print(ln, '+new')
						for ln in partial_old.txt:
							print(ln, '---old')
			else:
				ref = ch.vis[-1]
				if ref.cdr != len(ref.txt):

					if debug_scrolling:
						for n, ln in enumerate(ref.txt):
							print('{0:2} {1} {2}'.format(n, ln,
								'== car' if n == ref.car else \
								'== cdr' if n == ref.cdr - 1 else ''))

					partial = ref.txt[ref.cdr:]
					partial_org = ref
					partial_old = VisMessage(
						ref.msg, ref.txt[ref.car:ref.cdr],
						ref.im, 0, ref.cdr-ref.car)
					ch.vis[-1] = partial_old

					if debug_scrolling:
						print('@@@ slicing len({0}) car,cdr({1},{2}) into olen({3})+nlen({4}), ocar,ocdr({5},{6}) ncar,ncdr({7},{8})?'.format(
							len(partial_org.txt), partial_org.car, partial_org.cdr,
							len(partial_old.txt), len(partial),
							partial_old.car, partial_old.cdr, 0, len(partial)))
						for ln in partial_old.txt:
							print(ln, '---old')
						for ln in partial:
							print(ln, '+new')
			
			# get message offset to start from
			if t_steps < 0:
				imsg = ch.vis[0].im
			else:
				imsg = ch.vis[-1].im
			
			if debug_scrolling:
				print('@@@ num chan messages {0}, num vis messages {1}, retained {2} = {3}'.format(
					len(nch.msgs), len(ch.vis), imsg, nch.msgs[imsg].txt[:6]))
				dbg = ''
				for m in ch.vis:
					dbg += '{0}, '.format(m.im)
				print('@@@ {0}'.format(dbg))
			
			# scroll until n_steps reaches abs_steps
			while n_steps < abs_steps:
				if partial:
					txt = partial
					msg = None
				else:
					if t_steps < 0:
						imsg -= 1
						if imsg < 0:
							break
					else:
						imsg += 1
						if imsg >= len(nch.msgs):
							break
					
					msg = nch.msgs[imsg]
					txt = self.msg2ansi(msg, msg_fmt, ts_fmt, msg_nl, msg_w, nick_w)
					
				if t_steps < 0:
					txt_order = reversed(txt)
				else:
					txt_order = txt
				
				# write lines to send buffer
				n_vis = 0
				for ln in txt_order:
					#print(u'@@@ vis{0:2} stp{1:2} += {2}'.format(n_vis, n_steps, ln))

					if not self.vt100:
						ret += u'\r{0}{1}\r\n'.format(ln, ' '*((self.w-len(ln))-2))

					elif lines_in_use < self.h - 3:
						ret += u'\033[{0}H\033[K{1}'.format(lines_in_use + 2, ln)
						lines_in_use += 1

					elif t_steps > 0:
						# official way according to docs,
						# doesn't work on windows
						#ret += u'\033[{0}H\033[S\033[K{1}'.format(self.h - 2, ln)
						
						# also works
						ret += u'\033[{0}H\033D\033[K{1}'.format(self.h - 2, ln)
						
					else:
						# official way according to docs,
						# doesn't work on inetutils-1.9.4
						#ret += u'\033[2H\033[T\033[K{0}'.format(ln)
						
						# also works
						ret += u'\033[2H\033M\033[K{0}'.format(ln)

					n_vis += 1
					n_steps += 1
					if n_steps >= abs_steps:
						break

				if t_steps < 0:
					new_cdr = len(txt)
					new_car = new_cdr - n_vis
				else:
					new_car = 0
					new_cdr = n_vis

				vmsg = VisMessage(msg, txt, imsg, new_car, new_cdr)
				#print('@@@ vismsg len({0}) car,cdr({1},{2}) -- {3}'.format(len(txt), new_car, new_cdr, txt[0][-30:]))

				if t_steps < 0:
					ch.vis.insert(0, vmsg)
				else:
					ch.vis.append(vmsg)

				if partial:
					partial = None
					partial_new = vmsg
		
			# release scroll region
			if self.vt100:
				ret += u'\033[r'
			
			# trim away messages that went off-screen
			if t_steps < 0:
				vis_order = ch.vis
			else:
				vis_order = reversed(ch.vis)
			
			n_msg = 0
			ln_left = self.h - 3
			
			for i, vmsg in enumerate(vis_order):
				if ln_left <= 0:
					break
				
				n_msg += 1
				msg_sz = vmsg.cdr - vmsg.car
				
				if msg_sz >= ln_left:
					if msg_sz > ln_left:
						if t_steps < 0:
							vmsg.cdr -= msg_sz - ln_left
						else:
							vmsg.car += msg_sz - ln_left
					msg_sz = ln_left

				ln_left -= msg_sz

				#print('@@@ 1 {0}'.format('\r\n@@@ 1 '.join(vmsg.txt[vmsg.car : vmsg.cdr])))

			if t_steps < 0:
				ch.vis = ch.vis[:n_msg]
			else:
				ch.vis = ch.vis[-n_msg:]

			# glue together the 2 parts forming the formerly off-screen message
			if partial_old:
				if partial_old not in ch.vis:
					# old segment is gone, discard it
					if t_steps > 0:
						partial_new.car += len(partial_old.txt)
						partial_new.cdr += len(partial_old.txt)
				else:
					# old segment is partially or fully visible
					ch.vis.remove(partial_old)
					if t_steps < 0:
						partial_new.cdr += partial_old.cdr
					else:
						if debug_scrolling:
							print('@@@ merging old({0},{1}) new({2},{3}) olen({4}) org({5},{6})'.format(
								partial_old.car, partial_old.cdr,
								partial_new.car, partial_new.cdr,
								len(partial_old.txt),
								partial_org.car, partial_org.cdr))
							for n, ln in enumerate(partial_old.txt):
								print(ln, '---old', n)
							for n, ln in enumerate(partial_new.txt):
								print(ln, '+new', n)
						partial_new.car += partial_old.car
						partial_new.cdr += partial_old.cdr

						partial_new.car += partial_org.car
						partial_new.cdr += partial_org.car

				partial_new.txt = partial_org.txt
				partial_new.msg = partial_org.msg

				if debug_scrolling:
					print('@@@ car,cdr ({0},{1})'.format(partial_new.car, partial_new.cdr))

			# update the server-side screen buffer
			new_screen = [self.screen[0]]
			for i, vmsg in enumerate(ch.vis):
				for ln in vmsg.txt[vmsg.car:vmsg.cdr]:
					new_screen.append(ln)

					#print('@@@ 2 {0}'.format(ln))
			
			while len(new_screen) < self.h - 2:
				new_screen.append('--')

			new_screen.append(self.screen[-2])
			new_screen.append(self.screen[-1])
			old_screen = self.screen
			self.screen = new_screen
			
			ch.lock_to_bottom = (
				ch.vis[-1].msg == nch.msgs[-1] and \
				ch.vis[-1].cdr == len(ch.vis[-1].txt) )

			#print('@@@ lock_to_bottom:', ch.lock_to_bottom)

			if len(self.screen) != self.h:
				print('!!! new screen is {0} but client is {1}'.format(len(self.screen), self.h))
				for n, ln in enumerate(old_screen): print('o',   ln, n)
				for n, ln in enumerate(new_screen): print('new', ln, n)
				time.sleep(100000)
		
			if not self.vt100:
				if t_steps < 0:
					# rely on vt100 code to determine the new display
					# then retransmit the full display  (good enough)
					return u'\r\n'*self.h + self.update_chat_view(True)

		return ret





	def conf_wizard(self):
		if DBG:
			if u'\x03' in self.in_text:
				self.world.core.shutdown()

		sep = u'{0}{1}{0}\033[2A'.format(u'\n', u'/'*71)
		ftop = u'\n'*20 + u'\033[H\033[J'
		top = ftop + ' [ r0c configurator ]\n'

		if self.wizard_stage == 'start':
			self.wizard_stage = 'qwer_read'
			self.in_text = u''
			self.say((top + u"""
 type the text below, then hit [Enter]:  

   qwer asdf

 """).replace(u"\n", u"\r\n").encode('utf-8'))
#\033[10Hasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdf

			return


		if self.wizard_stage == 'qwer_read':
			nline = b'\x0d\x0a\x00'
			btext = self.in_text.encode('utf-8')
			delta = len(self.in_text) - self.wizard_lastlen
			self.wizard_lastlen = len(self.in_text)
			if delta > 1:
				# acceptable if delta is exactly 2
				# and the final characters are newline-ish
				print('qwer delta = {0}'.format(delta))
				if delta > 2 or btext[-1] not in nline:
					if self.wizard_maxdelta < delta:
						self.wizard_maxdelta = delta

			#if any(ch in btext for ch in nline):
			nl_a = next((i for i, ch in enumerate(btext) if ch in nline), None)
			if nl_a is not None:
				nl_b = next((i for i, ch in enumerate(reversed(btext)) if ch in nline), None)
				if nl_b is not None:
					etab = self.esc_tab.iteritems if PY2 else self.esc_tab.items
					nl = btext[nl_a:len(btext)-nl_b]
					drop = []
					for key, value in etab():
						if value == 'ret':
							drop.append(key)
					for key in drop:
						del self.esc_tab[key]
					self.esc_tab[nl.decode('utf-8')] = 'ret'
					print('qwer newline = {0}'.format(b2hex(nl)))

				if self.wizard_maxdelta >= nl_a / 2:
					self.echo = True
					self.linemode = True
					print('setting linemode+echo since d{0} and {1}ch; {2}'.format(
						self.wizard_maxdelta, len(self.in_text),
						b2hex(self.in_text.encode('utf-8'))))

				self.wizard_stage = 'echo'
				if self.in_text.startswith('wncat'):
					self.linemode = True
					self.echo_on = True
					self.vt100 = False
					self.codec = 'cp437'
					self.wizard_stage = 'end'
				#if self.in_text.startswith('no ansi'):

			#print('now, last = {0}, {1}'.format(len(self.in_text), self.wizard_lastlen))
			#if len(self.in_text) - self.wizard_lastlen > 1:
			#	ofs = self.in_text.lower().find(u'y')
			#	ex_len = None
			#	if ofs >= 0:
			#		ex_len = ofs + 3
			#	else:
			#		ofs = self.in_text.lower().find(u'n')
			#		if ofs >= 0:
			#			ex_len = ofs + 3
			#
			#	if self.wizard_lastlen < 2 or \
			#		(ex_len is not None and ex_len >= self.wizard_lastlen):
			#
			#		print('setting linemode since d{0} and ex({1}) >= in({2}); {3}'.format(
			#			len(self.in_text) - self.wizard_lastlen,
			#			ex_len, len(self.in_text),
			#			b2hex(self.in_text.encode('utf-8'))))
			#
			#		self.linemode = True


		if self.wizard_stage == 'echo':
			if self.linemode:
				# echo is always enabled if linemode, skip this stage
				self.wizard_stage = 'linemode'
				return
			self.wizard_stage = 'echo_answer'
			self.in_text = u''
			self.say((u"""

   A:  your text appeared as you typed

   B:  nothing happened

 press A or B&lm
 """).replace(u'\n', u'\r\n').replace(u'&lm', u', followed by [Enter]' if self.linemode else u':').encode('utf-8'))
			return


		if self.wizard_stage == 'echo_answer':
			self.wizard_stage = 'linemode'
			text = self.in_text.lower()
			if u'a' in text:
				self.echo_on = True
			elif u'b' not in text:
				self.wizard_stage = 'echo_answer'


		if self.wizard_stage == 'linemode':
			if self.linemode:
				self.wizard_stage = 'linemode_warn'
				self.in_text = u''
				self.say((top + u"""
 WARNING:  
   your client is stuck in line-buffered mode,
   this will cause visual glitches in text input.
   Keys like PgUp and CTRL-Z are also buggy;
   you must press the key twice followed by Enter.

 if you are using Linux or Mac OSX, disconnect and
 run the following command before reconnecting:
   Mac OSX:  stty -f /dev/stdin -icanon
   Linux:    stty -icanon

 press A to accept or Q to quit&lm
 """).replace(u'\n', u'\r\n').replace(u'&lm', u', followed by [Enter]' if self.linemode else u':').encode('utf-8'))
				return

			self.wizard_stage = 'color'


		if self.wizard_stage == 'linemode_warn':
			text = self.in_text.lower()
			if u'a' in text:
				self.wizard_stage = 'color'
			elif u'q' in text:
				self.host.part(self)


		if self.wizard_stage == 'color':
			self.wizard_stage = 'color_answer'
			self.in_text = u''
			self.say((top + u"""
 does colours work?  
 \033[1;31mred, \033[32mgreen, \033[33myellow, \033[34mblue\033[0m

 press Y or N&lm
 """).replace(u'\n', u'\r\n').replace(u'&lm', u', followed by [Enter]' if self.linemode else u':').encode('utf-8'))
			return


		if self.wizard_stage == 'color_answer':
			
			text = self.in_text.lower()
			if u'y' in text:
				self.wizard_stage = 'codec'
				self.in_text = u''
			
			elif u'n' in text:
				self.wizard_stage = 'vt100'
				self.in_text = u''
				
				self.say((sep + u"""
 what did you see instead?  

   A:  "red, green, yellow, blue"
       -- either in just one colour
          or otherwise incorrect colours

   B:  "[1;31mred, [32mgreen, [33myellow, [36mblue[0m"

 press A or B&lm
 """).replace(u'\n', u'\r\n').replace(u'&lm', u', followed by [Enter]' if self.linemode else u':').encode('utf-8'))
				return


		if self.wizard_stage == 'vt100':
			text = self.in_text.lower()
			if u'a' in text:
				# vt100 itself is probably fine, don't care
				self.wizard_stage = 'codec'
				self.in_text = u''

			elif u'b' in text:
				self.wizard_stage = 'vt100_warn'
				self.vt100 = False
				self.in_text = u''
				self.say((top + u"""
 WARNING:  
   your client or terminal is not vt100 compatible!
   I will reduce features to a bare minimum,
   but this is gonna be bad regardless
 
   whenever the screen turns too glitchy
   you can press CTRL-R and Enter to redraw
 
 press A to accept or Q to quit&lm
 """).replace(u'\n', u'\r\n').replace(u'&lm', u', followed by [Enter]' if self.linemode else u':').encode('utf-8'))
				return


		if self.wizard_stage == 'vt100_warn':
			text = self.in_text.lower()
			if u'a' in text:
				self.wizard_stage = 'codec'
				self.in_text = u''
			elif u'q' in text:
				self.host.part(self)


		encs = [ 'utf-8',0,  'cp437',0,  'shift_jis',0,  'latin1',1,  'ascii',2 ]
		unis = [ u'├┐ ┌┬┐ ┌ ',  u'Ð Ñ Ã ',  u'all the above are messed up ' ]
		AZ = u'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
		
		if self.wizard_stage == 'codec':
			self.wizard_stage = 'codec_answer'
			self.in_text = u''
			def u8(tx):
				return tx.encode('utf-8', 'backslashreplace')

			to_send = u8((ftop + u'\n which line looks like  "hmr"  or  "dna" ?').replace(u'\n', u'\r\n'))

			if not self.vt100:
				for nth, (enc, uni) in enumerate(zip(encs[::2], encs[1::2])):
					to_send += u8(u'\r\n\r\n   {0}:  '.format(AZ[nth]))
					try:
						to_send += unis[uni].encode(enc, 'backslashreplace')
					except:
						to_send += u8('<codec not available>')
				to_send += u8(u'\r\n')
			else:
				for nth, (enc, uni) in enumerate(zip(encs[::2], encs[1::2])):
					to_send += u8(u'\033[{0}H   {1}:  '.format(nth*2+4, AZ[nth]))
					try:
						to_send += unis[uni].encode(enc, 'backslashreplace')
					except:
						to_send += u8('<codec not available>')
					to_send += u8(u'\033[J\033[{0}H\033[J'.format(nth*2+5))

			to_send += u8(u'\r\n press {0}{1}\r\n'.format(u'/'.join(AZ[:nth+1]),
				u', followed by [Enter]' if self.linemode else u':'))
			
			self.say(to_send)
			return


		if self.wizard_stage == 'codec_answer':
			found = False
			text = self.in_text.lower()
			for n, letter in enumerate(AZ[:int(2+len(encs)/2)].lower()):
				if letter in text:
					self.wizard_stage = 'end'
					self.codec = encs[n*2]
					break


		if self.wizard_stage == 'end':
			# if echo enabled, swap status and input:
			# that way the screen won't scroll on enter
			if self.echo_on:
				self.y_input, self.y_status = self.y_status, self.y_input

			print('client conf:  linemode({0})  vt100({1})  echo_on({2})  codec({3})'.format(
				self.linemode, self.vt100, self.echo_on, self.codec))

			self.wizard_stage = None
			self.in_text = u''
			
			#print('{0} is going to sleep'.format(threading.current_thread()))
			#monitor_threads()
			#time.sleep(3)

			self.user.create_channels()





	def read_cb(self, full_redraw):
		# only called by (telnet|netcat).py:handle_read,
		# only called within locks on self.world.mutex

		#self.wizard_stage = None
		if self.wizard_stage is not None:
			self.conf_wizard()
			
			if self.wizard_stage is not None:
				return

			full_redraw = True

		aside = u''
		old_cursor = self.linepos
		for ch in self.in_text:
			if DBG:
				if ch == '\x03':
					self.world.core.shutdown()
			
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
					#print('read_cb inner  {0} / {1}'.format(b2hex(pch.encode('utf-8', 'backslashreplace')), nch))
					if nch < 0x20:  # or (self.codec == 'utf-8' and nch >= 0x80 and nch < 0x100):
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
					print(' escape seq:  {0} = {1}'.format(b2hex(aside), act))

				hist_step = 0
				chan_shift = 0

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
					if self.linebuf:
						# add this to the message/command ("input") history
						if not self.msg_hist or self.msg_hist[-1] != self.linebuf:
							self.msg_hist.append(self.linebuf)
						
						single = self.linebuf.startswith('/')
						double = self.linebuf.startswith('//')
						if single and not double:
							# this is a command
							self.user.exec_cmd(self.linebuf[1:])
						else:
							if double:
								# remove escape character
								self.linebuf = self.linebuf[1:]
							
							self.world.send_chan_msg(
								self.user.nick, self.user.active_chan.nchan, self.linebuf)

						self.msg_hist_n = None
						self.linebuf = u''
						self.linepos = 0
				elif act == 'pgup':
					self.scroll_cmd = -(self.h - 4)
					#self.scroll_cmd = -10
				elif act == 'pgdn':
					self.scroll_cmd = +(self.h - 4)
					#self.scroll_cmd = +10
				elif act == 'redraw':
					self.need_full_redraw = True
				elif act == 'prev-chan':
					chan_shift = -1
				elif act == 'next-chan':
					chan_shift = +1
				else:
					print('unimplemented action: {0}'.format(act))

				if chan_shift != 0:
					i = self.user.chans.index(self.user.active_chan) + chan_shift
					if i < 0:
						i = len(self.user.chans) - 1
					if i >= len(self.user.chans):
						i = 0
					self.user.new_active_chan = self.user.chans[i]
				
				elif hist_step == 0:
					self.msg_hist_n = None
				
				else:
					if self.msg_hist_n is None:
						if hist_step < 0:
							self.msg_hist_n = len(self.msg_hist) - 1
					else:
						self.msg_hist_n += hist_step

					if self.msg_hist_n is not None:
						if self.msg_hist_n < 0 or self.msg_hist_n >= len(self.msg_hist):
							self.msg_hist_n = None

					if self.msg_hist_n is None:
						self.linebuf = u''
					else:
						self.linebuf = self.msg_hist[self.msg_hist_n]
					self.linepos = len(self.linebuf)
		if aside:
			if DBG:
				print('need more data for {0} runes: {1}'.format(len(aside), b2hex(aside)))
			self.in_text = aside
		else:
			self.in_text = u''

		if self.w < 20 or self.h < 4:
			msg = 'x'
			for cand in self.msg_too_small:
				#print('{0} <= {1}'.format(len(cand), self.w))
				if len(cand) <= self.w:
					msg = cand
					break
			y = int(self.h / 3)
			x = int((self.w - len(msg)) / 2)
			x += 1
			y += 1
			print('2smol @ {0} {1}'.format(x, y))
			msg = u'\033[H\033[1;37;41m\033[J\033[{0};{1}H{2}\033[0m'.format(y,x,msg)
			self.say(msg.encode(self.codec, 'backslashreplace'))
			self.too_small = True
			return
		self.too_small = False

		with self.world.mutex:
			if full_redraw or self.need_full_redraw:
				self.need_full_redraw = True
			
			if not self.handshake_sz:
				if DBG:
					print('!!! read_cb without handshake_sz')
			else:
				self.refresh(old_cursor != self.linepos)

