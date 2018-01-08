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
	
	def __init__(self, core):
		asyncore.dispatcher.__init__(self)
		self.core = core
		self.explain = True
		#self.explain = False
		self.in_text = u''
		self.outbox = Queue()
		self.backlog = None
		self.dead = False
		self.stage = 'start'
		self.actor_active = False
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.connect(('127.0.0.1', 2323))

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
					self.in_text = u''
					self.tx(u'a')
					
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



	def expl(msg):
		if not self.explain:
			return
		print(msg)
		time.sleep(4)
		
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
			if n % 1000 == 0:
				self.tx(b'at event {0}\n'.format(n))
				
			while True:
				next_act = random.randrange(37)
				
				if next_act <= 9:
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
						print('switching to next channel from {0} to {1} ({2} to {3})'.format(
							changed_from_i, changed_to_i,
							changed_from_t, changed_to_t))
						for act in script:
							self.outbox.put(act)
						script = []
						time.sleep(4)
					break
				
				if next_act <= 14:
					if len(member_of) == len(channels_avail):
						# out of channels to join, try a different act
						continue
					while True:
						to_join = random.choice(channels_avail)
						if to_join not in member_of:
							break
					member_of.append(to_join)
					active_chan = len(member_of) - 1
					script.append(b'/join {0}\n'.format(to_join))
					break
				
				if next_act <= 18:
					if not member_of:
						# out of channels to part, try a different act
						continue
					to_part = random.choice(member_of)
					chan_idx = member_of.index(to_part)
					# jump to the channel to part from
					while active_chan != chan_idx:
						active_chan += 1
						script.append(b'\x18')
						if active_chan >= len(member_of):
							# we do not consider the status channel
							script.append(b'\x18')
							active_chan = 0
					if active_chan == len(member_of) - 1:
						del member_of[active_chan]
						active_chan -= 1
					else:
						del member_of[active_chan]
					script.append(b'/part\n')
					break
				
				if not member_of:
					# not in any channels, try a different act
					continue
				chan_name = member_of[active_chan]
				chan_idx = channels_avail.index(chan_name)
				msg_id[chan_idx] += 1
				script.append(b'{0} {1} {2}\n'.format(chan_name, msg_id[chan_idx], n))
		
		self.tx(b'q\n'.format(n))
	
		while not self.core.stopping:
			if 'fire/' in self.in_text:
				break
			time.sleep(0.01)
				
		for n, ev in enumerate(script):
			if self.core.stopping:
				break
			
			if n % 100 == 0:
				print(b'at event {0}\n'.format(n))
			
			self.outbox.put(ev)
			time.sleep(0.05)
		
		print('done')
		self.tx('done')
	
	

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
		#print(self.in_text)



class Core(object):

	def __init__(self):
		self.stopping = False
		self.asyncore_alive = False

		signal.signal(signal.SIGINT, self.signal_handler)

		self.client = Client(self)

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

