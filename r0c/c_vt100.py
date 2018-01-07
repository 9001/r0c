if __name__ == '__main__':
	raise RuntimeError('\n{0}\n{1}\n{2}\n{0}\n'.format('*'*72,
		'  this file is part of retr0chat',
		'  run r0c.py instead'))

import threading
import asyncore
import datetime
import sys

from config import *
from util import *

PY2 = (sys.version_info[0] == 2)

if PY2:
	from Queue import Queue
else:
	from queue import Queue

class Client(asyncore.dispatcher):
	
	def __init__(self, host, socket, address, world, user):
		asyncore.dispatcher.__init__(self, socket)
		self.host = host
		self.socket = socket
		self.world = world
		self.user = user
		self.mutex = threading.RLock()
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
		with self.mutex:
			if self.user.new_active_chan:
				self.user.active_chan = self.user.new_active_chan
				self.user.new_active_chan = None
				full_redraw = True
			
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
		top_bar = u'\033[1H\033[44;48;5;235;38;5;220m{0}\033[K'.format(
			self.user.active_chan.topic)
		
		if self.screen[0] != top_bar:
			self.screen[0] = top_bar
			return trunc(top_bar, self.w)
		return u''

	def update_status_bar(self, full_redraw):
		preface = u'\033[{0}H\033[0;37;44;48;5;235m'.format(self.h-1)
		hhmmss = datetime.datetime.utcnow().strftime('%H:%M:%S')
		nChan = self.user.chans.index(self.user.active_chan)
		nChans = len(self.user.chans)
		nUsers = len(self.user.active_chan.nchan.uchans)
		chan_name = self.user.active_chan.name
		
		hilights = []
		for i, chan in enumerate(self.user.chans):
			if chan.activity:
				activity.append(i)
			if chan.hilights:
				hilights.append(i)
		
		if hilights:
			hilights = u'\033[1;33mh {0}\033[22;39m'.format(','.join(hilights))
		if activity:
			activity = u'\033[1;32ma {0}\033[22;39m'.format(','.join(activity))
		
		line = trunc(u'{0}{1}   {2} #{3}   {4}   {5}\033[K'.format(
			preface, hhmmss, nChan, chan_name, hilights, activity, nUsers), self.w)
		
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
