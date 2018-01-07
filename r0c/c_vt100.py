# -*- coding: utf-8 -*-
if __name__ == '__main__':
	raise RuntimeError('\n{0}\n{1}\n{2}\n{0}\n'.format('*'*72,
		'  this file is part of retr0chat',
		'  run r0c.py instead'))

import threading
import asyncore
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

class Client(asyncore.dispatcher):
	
	def __init__(self, host, socket, address, world, user):
		asyncore.dispatcher.__init__(self, socket)
		self.mutex = threading.RLock()
		self.host = host
		self.socket = socket
		self.world = world
		self.user = user
		self.outbox = Queue()
		self.replies = Queue()
		self.backlog = None
		self.last_tx = None
		self.slowmo_tx = SLOW_MOTION_TX
		self.in_bytes = b''
		self.in_text = u''
		self.linebuf = u''
		self.linepos = 0
		self.lineview = 0
		self.scroll_cmd = None
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

		# inetutils-1.9.4
		self.add_esc(u'\x7f', 'bs')
		self.add_esc(u'\x1b\x4f\x48', 'home')
		self.add_esc(u'\x1b\x4f\x46', 'end')

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
				raise RuntimeError('partial escape code [{0}] matching fully defined escape code for [{1}]'.format(
					b2hex(hist), act))
			self.esc_tab[hist] = False
		if key in self.esc_tab and self.esc_tab[key] != act:
			raise RuntimeError('fully defined escape code [{0}] for [{1}] matches other escape code for [{2}]'.format(
				b2hex(key), act, self.esc_tab[key]))
		self.esc_tab[key] = act

	def say(self, message):
		self.outbox.put(message)

	def writable(self):
		#if self.slowmo_tx:
		#	#print('x')
		#	now = time.time()
		#	if self.last_tx is not None and now - self.last_tx < 0.01:
		#		return False
		#	#print('ooo')
		
		return (
			self.backlog or
			not self.replies.empty() or
			not self.outbox.empty()
		)

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
			if len(msg) < 100:
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

	def refresh(self, full_redraw, cursor_moved):
		""" compose necessary ansi text and send to client """
		with self.mutex:
			if self.user.new_active_chan:
				self.user.active_chan = self.user.new_active_chan
				self.user.new_active_chan = None
				full_redraw = True
			
			to_send = u''
			fix_color = False

			to_send += self.update_chat_view(full_redraw)
			if to_send:
				full_redraw = True

			to_send += self.update_top_bar(full_redraw)
			to_send += self.update_status_bar(full_redraw)
			if to_send:
				fix_color = True

			to_send += self.update_text_input(full_redraw)
			if '\033[' in self.linebuf or fix_color:
				to_send += '\033[0m'
			
			if to_send or cursor_moved:
				to_send += u'\033[{0};{1}H'.format(self.h, len(self.user.nick) + 2 + self.linepos + 1 - self.lineview)
				self.say(to_send.encode('utf-8'))

	def update_top_bar(self, full_redraw):
		""" no need to optimize this tbh """
		top_bar = u'\033[1H\033[44;48;5;235;38;5;220m{0}\033[K'.format(
			self.user.active_chan.nchan.topic)
		
		if self.screen[0] != top_bar:
			self.screen[0] = top_bar
			return trunc(top_bar, self.w)
		return u''

	def update_status_bar(self, full_redraw):
		preface = u'\033[{0}H\033[0;37;44;48;5;235m'.format(self.h-1)
		hhmmss = datetime.datetime.utcnow().strftime('%H%M%S')
		nChan = self.user.chans.index(self.user.active_chan)
		nChans = len(self.user.chans)
		nUsers = len(self.user.active_chan.nchan.uchans)
		chan_name = self.user.active_chan.nchan.name
		
		hilights = []
		activity = []
		for i, chan in enumerate(self.user.chans):
			if chan.hilights:
				hilights.append(i)
			if chan.activity:
				activity.append(i)
		
		if hilights:
			hilights = u'\033[1;33mh {0}\033[22;39m'.format(','.join(hilights))
		if activity:
			activity = u'\033[1;32ma {0}\033[22;39m'.format(','.join(activity))
		
		line = trunc(u'{0}{1}   {2}: #{3}   {4}   {5}\033[K'.format(
			preface, hhmmss, nChan, chan_name, hilights or '', activity or '', nUsers), self.w)
		
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
				# send all of it
				return trunc(line, self.w)

			if changed_part1:
				# send just the timestamp
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
	
	def msg2ansi(self, msg, msg_fmt, ts_fmt, msg_nl, msg_w, nick_w):
		ts = datetime.datetime.utcfromtimestamp(msg.ts).strftime(ts_fmt)
		if msg.text.startswith(u' '):
			txt = msg.text.splitlines()
			for n in range(len(txt)):
				txt[n] = trunc(txt[n], msg_w)
		else:
			txt = unrag(msg.text, msg_w) or [' ']
		
		for n in range(len(txt)):
			if n == 0:
				txt[n] = msg_fmt.format(ts, msg.user[:nick_w], txt[n])
			else:
				txt[n] = msg_nl + txt[n]
		
		return txt
	
	def update_chat_view(self, full_redraw):
		ret = u''
		ch = self.user.active_chan
		nch = ch.nchan
		
		#print('\n@@@ update chat view @@@ {0}'.format(time.time()))
		
		if self.w >= 140:
			nick_w = 18
			msg_w = self.w - 28
			msg_nl = u' ' * 28
			msg_fmt = u'{0}  {1:18} {2}'
			ts_fmt = '%H:%M:%S'
		elif self.w >= 100:
			nick_w = 14
			msg_w = self.w - 24
			msg_nl = u' ' * 24
			msg_fmt = u'{0}  {1:14} {2}'
			ts_fmt = '%H:%M:%S'
		elif self.w >= 80:
			nick_w = 12
			msg_w = self.w - 20
			msg_nl = u' ' * 20
			msg_fmt = u'{0} {1:12} {2}'
			ts_fmt = '%H%M%S'
		elif self.w >= 60:
			nick_w = 8
			msg_w = self.w - 15
			msg_nl = u' ' * 15
			msg_fmt = u'{0} {1:8} {2}'
			ts_fmt = '%H:%M'
		else:
			nick_w = 8
			msg_w = self.w - 9
			msg_nl = u' ' * 9
			msg_fmt = u'{1:8} {2}'
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
			if ch.lock_to_bottom:
				# lock to bottom, full redraw:
				# last message will be added first
				# and will always be partially visible
				lines_left = self.h - 3
				ch.vis = []
				for n, msg in enumerate(reversed(nch.msgs)):
					imsg = len(nch.msgs) - n
					txt = self.msg2ansi(msg, msg_fmt, ts_fmt, msg_nl, msg_w, nick_w)
					
					car = 0
					cdr = len(txt) - 1
					n_vis = cdr + 1
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
			
			while len(lines) < self.h - 3:
				lines.append('--')
			
			for n in range(self.h - 3):
				if self.screen[n+1] != lines[n]:
					self.screen[n+1] = lines[n]
					ret += u'\033[{0}H{1}\033[K'.format(n+2, self.screen[n+1])
		
		else:
			# full_redraw = False,
			# do relative scrolling if necessary
			
			t_steps = self.scroll_cmd   # total number of scroll steps
			n_steps = 0                 # number of scroll steps performed
			self.scroll_cmd = None
			
			if t_steps:
				ch.lock_to_bottom = False
			else:
				if not ch.lock_to_bottom:
					# fixed viewport
					return ret
				
				if nch.msgs[-1] == ch.vis[-1].msg:
					# no new messages
					return ret
				
				#print('@@@ len(nch) {0}, len(ch.vis) {1}, -1={2}, 0={3}'.format(
				#	len(nch.msgs), len(ch.vis),
				#	nch.msgs[-1] == ch.vis[-1].msg,
				#	nch.msgs[-1] == ch.vis[0].msg))
				
				# push all new messages
				t_steps = 99999999999
			
			# set scroll region:  chat pane
			ret += u'\033[2;{0}r'.format(self.h - 2)
			
			abs_steps = abs(t_steps)    # abs(total steps)
			
			print('@@@ gonna scroll {0} lines'.format(abs_steps))

			# first / last visible message might have lines off-screen;
			# check those first
			if t_steps < 0:
				ref = ch.vis[0]
			elif t_steps > 0:
				ref = ch.vis[-1]
			
			txt = []

			# number of visible lines != total number of lines
			if t_steps < 0 and ref.car != 0:
				# scrolling up; grab offscreen text at top
				#print('\ncar {0}   cdr {1}   len {2}'.format(ref.car, ref.cdr, len(ref.txt)))
				#print('lines retained {0} - {1} = {2}'.format(self.h-3, abs_steps, (self.h - 3) - abs_steps))

				# (h-3)-abs is number of lines retained from last screen
				ref.cdr = ref.car + (self.h - 3) - abs_steps
				if ref.cdr >= len(ref.txt):
					ref.cdr = len(ref.txt) - 1

				ref.car -= abs_steps
				if ref.car < 0:
					ref.car = 0

				txt = ref.txt[ref.car:ref.cdr+1]

				#print('need to add {0}'.format(txt))
				#time.sleep(20)

			elif t_steps > 0 and ref.cdr != len(ref.txt) - 1:
				# grab n last lines; scrolling down
				ref.car = ref.cdr - ((self.h - 3) - abs_steps)
				if ref.car < 0:
					ref.car = 0
				
				ref.cdr += abs_steps
				if ref.cdr >= len(ref.txt):
					ref.cdr = len(ref.txt) - 1

				txt = ref.txt[ref.car:ref.cdr+1]

			n_steps += len(txt)
		
			# write lines to send buffer
			for ln in txt:
				print('@@@ PARTIAL += {0}'.format(ln))
				if t_steps > 0:
					ret += u'\033[S\033[{0}H{1}\033[K'.format(
						self.h - 2, ln)
				else:
					ret += u'\033[T\033[2H{0}\033[K'.format(ln)
			
			# get message offset to start from
			if t_steps < 0:
				imsg = ch.vis[0].im
			else:
				imsg = ch.vis[-1].im
			
			print('@@@ num chan messages {0}, num vis messages {1}, retained {2} = {3}'.format(
				len(nch.msgs), len(ch.vis), imsg, nch.msgs[imsg].text[:6]))
			dbg = ''
			for m in ch.vis:
				dbg += '{0}, '.format(m.im)
			print('@@@ {0}'.format(dbg))
			
			# scroll until n_steps reaches abs_steps
			while n_steps < abs_steps:
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
					print(u'@@@ += {0}'.format(ln))
					if t_steps > 0:
						# official way according to docs
						ret += u'\033[{0}H\033[S{1}\033[K'.format(self.h - 2, ln)
						
						# also works
						#ret += u'\033[{0}H\033D{1}\033[K'.format(self.h - 2, ln)
							
					else:
						# official way according to docs
						#ret += u'\033[2H\033[T{0}\033[K'.format(ln)
						
						# also works
						ret += u'\033[2H\033M{0}\033[K'.format(ln)

					n_vis += 1
					n_steps += 1
					if n_steps >= abs_steps:
						break
				
				if t_steps < 0:
					new_cdr = len(txt) - 1
					new_car = new_cdr - n_vis
				else:
					new_car = 0
					new_cdr = n_vis - 1

				vmsg = VisMessage(msg, txt, imsg, new_car, new_cdr)

				if t_steps < 0:
					ch.vis.insert(0, vmsg)
				else:
					ch.vis.append(vmsg)
			
			# trim away messages that went off-screen
			if t_steps < 0:
				vis_order = reversed(ch.vis)
			else:
				vis_order = ch.vis
			
			n_msg = 0
			screen_buf = []
			ln_left = self.h - 3
			
			for i, vmsg in enumerate(vis_order):
				if ln_left <= 0:
					break
				
				n_msg += 1
				msg_sz = (vmsg.cdr - vmsg.car) + 1
				
				if msg_sz >= ln_left:
					if msg_sz > ln_left:
						if t_steps < 0:
							vmsg.cdr -= msg_sz - ln_left
						else:
							vmsg.car += msg_sz - ln_left
					msg_sz = ln_left

				ln_left -= msg_sz

			if t_steps < 0:
				ch.vis = ch.vis[:n_msg]
			else:
				ch.vis = ch.vis[-n_msg:]
			
			# update the server-side screen buffer
			new_screen = [self.screen[0]]
			for i, vmsg in enumerate(ch.vis):
				for ln in vmsg.txt[vmsg.car:vmsg.cdr+1]:
					new_screen.append(ln)
			
			new_screen.append(self.screen[-2])
			new_screen.append(self.screen[-1])
			self.screen = new_screen
			
			print('@@@ done - new screen is {0}'.format(len(self.screen)))
			if len(self.screen) != self.h:
				print('!!! but client is {0} wtf'.format(self.h))
				time.sleep(10)
		
		return ret

	def dummy_update_chat_view(self, full_redraw):
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
				elif act == 'pgup':
					self.scroll_cmd = -(self.h - 4)
				elif act == 'pgdn':
					self.scroll_cmd = +(self.h - 4)
				else:
					print('unimplemented action: {0}'.format(act))

				if hist_step == 0:
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
