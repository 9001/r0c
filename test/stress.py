#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function


"""stress.py: retr0chat stress tester"""
__version__   = "0.9"
__author__    = "ed <a@ocv.me>"
__credits__   = ["stackoverflow.com"]
__license__   = "MIT"
__copyright__ = 2018


import threading
import asyncore
import socket
import signal
import random
import time
import sys

PY2 = (sys.version_info[0] == 2)

if PY2:
	from Queue import Queue
else:
	from queue import Queue


class Client(asyncore.dispatcher):
	
	def __init__(self, core, port):
		asyncore.dispatcher.__init__(self)
		self.core = core
		self.explain = True
		self.explain = False
		self.in_text = u''
		self.outbox = Queue()
		self.backlog = None
		self.dead = False
		self.stage = 'start'
		self.actor_active = False
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.connect(('127.0.0.1', port))

		thr = threading.Thread(target=self.actor)
		thr.daemon = True  # for emergency purposes
		thr.start()
	
	def actor(self):
		self.actor_active = True
		print('actor going up')
		while not self.core.stopping:
			time.sleep(0.02)
			
			if self.stage == 'start':
				if 'type the text below, then hit [Enter]:' in self.in_text:
					self.stage = 'qwer'
					self.in_text = u''
					for ch in u'qwer asdf\n':
						self.tx(ch)
						time.sleep(0.02)
				continue

			if self.stage == 'qwer':
				if 'text appeared as you typed' in self.in_text:
					self.stage = 'color'
					self.in_text = u''
					self.tx(u'b')
					self.outbox.put(b'\xff\xfa\x1f\x00\x80\x00\x24\xff\xf0')  # 128x36
				continue

			if self.stage == 'color':
				if 'does colours work?' in self.in_text:
					self.stage = 'codec'
					self.in_text = u''
					self.tx(u'y')
				continue

			if self.stage == 'codec':
				if 'which line looks like' in self.in_text:
					self.stage = 'ready'
					self.tx(u'a')
					
					time.sleep(0.5)
					self.in_text = u''
					
					#return self.flood_single_channel()
					return self.jump_channels()
				
		self.actor_active = False



	def flood_single_channel(self):
		while not self.core.stopping:
			time.sleep(0.02)
			
			if self.stage == 'ready':
				if 'fire/' in self.in_text:
					self.stage = 'main'
					self.in_Text = u''
				continue
			
			if self.stage == 'main':
				self.stage = 'done'
				for n in range(4000):
					time.sleep(0.01)
					self.tx(u'{0} {1}\n'.format(time.time(), n))
				continue
			
			if self.stage == 'done':
				time.sleep(1)
				self.text = u''  # dont care
				if not self.outbox.empty():
					continue
				self.tx(u'{0} done\n'.format(time.time()))



	def expl(self, msg):
		if not self.explain:
			return
		print(msg)
		self.await_continue()

	def await_continue(self):
		self.in_text = u''
		t0 = time.time()
		while not self.core.stopping and not 'zxc mkl' in self.in_text:
			time.sleep(0.1)
			if time.time() - t0 > 10:
				break
		self.in_text = u''
		
	def jump_channels(self):
		script = []
		active_chan = 0
		member_of = ['#general']
		channels_avail = ['#general','#1','#2','#3']
		
		# maps to channels_avail
		msg_id = [0,0,0,0]
		
		# -------- acts ---------
		#  0 -  9: next channel
		# 10 - 14: join a channel
		# 15 - 18: part a channel
		# 19 - 36: send a message
		
		for n in range(100000):
			if self.core.stopping:
				break

			if n % 1000 == 0:
				self.tx(u'at event {0}\n'.format(n))
				
			while not self.core.stopping:
				if not member_of:
					next_act = 13
				else:
					next_act = random.randrange(37)

				if self.explain:
					print('in [{0}], active [{1}:{2}], msgid [{3}], next [{4}]'.format(
						','.join(member_of), active_chan, channels_avail[active_chan],
						','.join(str(x) for x in msg_id), next_act))
				
				if next_act <= 9:
					if not member_of:
						self.expl('tried to jump channel but we are all alone ;_;')
						continue

					changed_from_i = active_chan
					changed_from_t = member_of[active_chan]
					
					active_chan += 1
					script.append(b'\x18')
					if active_chan >= len(member_of):
						# we do not consider the status channel
						script.append(b'\x18')
						active_chan = 0
					
					changed_to_i = active_chan
					changed_to_t = member_of[active_chan]
					
					if self.explain:
						self.expl('switching to next channel from {0} to {1} ({2} to {3})'.format(
							changed_from_i, changed_to_i,
							changed_from_t, changed_to_t))
						for act in script:
							self.outbox.put(act)
						self.outbox.put(b'hello\n')
						self.await_continue()
						script = []
					break
				
				if next_act <= 14:
					if len(member_of) == len(channels_avail):
						self.expl('tried to join channel but filled {0} of {1} possible'.format(
							len(member_of), len(channels_avail)))
						# out of channels to join, try a different act
						continue
					while True:
						to_join = random.choice(channels_avail)
						if to_join not in member_of:
							break
					member_of.append(to_join)
					active_chan = len(member_of) - 1
					self.expl('going to join {0}:{1}, moving from {2}:{3}'.format(
						len(member_of), to_join, active_chan, member_of[active_chan]))

					script.append(u'/join {0}\n'.format(to_join).encode('utf-8'))

					if self.explain:
						for act in script:
							self.outbox.put(act)
						self.outbox.put(b'hello\n')
						self.await_continue()
						script = []
					break
				
				if next_act <= 18:
					if not member_of:
						self.expl('tried to leave channel but theres nothing to leave')
						# out of channels to part, try a different act
						continue
					to_part = random.choice(member_of)
					chan_idx = member_of.index(to_part)
					self.expl('gonna leave {0}:{1}, we are in {2}:{3}'.format(
						chan_idx, to_part, active_chan, member_of[active_chan]))
					# jump to the channel to part from
					while active_chan != chan_idx:
						self.expl('jumping over from {0} to {1}'.format(
							active_chan, active_chan + 1 ))
						active_chan += 1
						script.append(b'\x18')
						if active_chan >= len(member_of):
							self.expl('wraparound; dodging the status chan')
							# we do not consider the status channel
							script.append(b'\x18')
							active_chan = 0
					if active_chan == len(member_of) - 1:
						self.expl('we are at the end of the channel list, decreasing int')
						del member_of[active_chan]
						active_chan -= 1
					else:
						self.expl('we are not at the end of the channel list, keeping it')
						del member_of[active_chan]
					if member_of:
						self.expl('we will end up in {0}:{1}'.format(active_chan, member_of[active_chan]))
					else:
						self.expl('we have now left all our channels')
					
					script.append(b'/part\n')

					if self.explain:
						for act in script:
							self.outbox.put(act)
						self.outbox.put(b'hello\n')
						self.await_continue()
						script = []
					break
				
				if not member_of:
					# not in any channels, try a different act
					continue
				chan_name = member_of[active_chan]
				chan_idx = channels_avail.index(chan_name)
				msg_id[chan_idx] += 1
				self.expl('gonna talk to {0}:{1}, msg #{2}'.format(
					chan_idx, chan_name, msg_id[chan_idx]))
				
				script.append(u'{0} {1} {2}\n'.format(
					chan_name, msg_id[chan_idx], n).encode('utf-8'))

				if self.explain:
					for act in script:
						self.outbox.put(act)
					self.outbox.put(b'hello\n')
					self.await_continue()
					script = []
				break
		
		self.tx(u'q\n')
	
		while not self.core.stopping:
			if 'fire/' in self.in_text:
				break
			time.sleep(0.01)
				
		for n, ev in enumerate(script):
			if self.core.stopping:
				break
			
			if n % 100 == 0:
				print('at event {0}\n'.format(n))
			
			self.outbox.put(ev)
			time.sleep(0.001)
		
		self.tx(u'done')
		print('done')
	
	

	def handle_close(self):
		self.dead = True

	def tx(self, bv):
		self.outbox.put(bv.encode('utf-8'))
	
	def readable(self):
		return not self.dead

	def writable(self):
		return (self.backlog or not self.outbox.empty())

	def handle_write(self):
		msg = self.backlog
		if not msg:
			msg = self.outbox.get()
		sent = self.send(msg)
		self.backlog = msg[sent:]

	def handle_read(self):
		if self.dead:
			print('!!! read when dead')
			return

		data = self.recv(8192)
		if not data:
			self.dead = True
			return
		
		self.in_text += data.decode('utf-8', 'ignore')
		
		#if self.explain:
		#	print(self.in_text)



class Core(object):

	def __init__(self):
		if len(sys.argv) < 2:
			print('need 1 argument:  telnet port')
			sys.exit(1)

		self.stopping = False
		self.asyncore_alive = False

		signal.signal(signal.SIGINT, self.signal_handler)

		self.client = Client(self, int(sys.argv[1]))

		self.asyncore_thr = threading.Thread(target=self.asyncore_worker)
		self.asyncore_thr.start()

	def run(self):
		print('  *  test is running')
		
		while not self.stopping:
			time.sleep(0.1)

		print('\r\n  *  actor stopping')
		clean_shutdown = False
		for n in range(0, 40):  # 2sec
			if not self.client.actor_active:
				print('  *  actor stopped')
				clean_shutdown = True
				break
			time.sleep(0.05)

		if not clean_shutdown:
			print(' -X- actor is stuck')

		print('  *  asyncore stopping')
		clean_shutdown = False
		for n in range(0, 40):  # 2sec
			if not self.asyncore_alive:
				print('  *  asyncore stopped')
				clean_shutdown = True
				break
			time.sleep(0.05)
		
		if not clean_shutdown:
			print(' -X- asyncore is stuck')

		print('  *  asyncore cleanup')
		self.client.close()

		print('  *  test ended')

	def asyncore_worker(self):
		self.asyncore_alive = True

		timeout = 0.05
		while not self.stopping:
			asyncore.loop(timeout, count=0.5/timeout)

		self.asyncore_alive = False

	def shutdown(self):
		self.stopping = True

	def signal_handler(self, signal, frame):
		self.shutdown()


core = Core()
core.run()

