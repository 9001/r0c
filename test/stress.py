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
import time
import sys

PY2 = (sys.version_info[0] == 2)

if PY2:
	from Queue import Queue
else:
	from queue import Queue


class Client(asyncore.dispatcher):
	
	def __init__(self):
		asyncore.dispatcher.__init__(self)
		self.in_text = u''
		self.outbox = Queue()
		self.backlog = None
		self.dead = False
		self.slp = None
		self.stage = 'start'
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.connect(('127.0.0.1', 23))

	def handle_close(self):
		self.dead = True

	def tx(self, bv):
		self.outbox.put(bv.encode('utf-8'))

	def readable(self):
		return not self.dead

	def writable(self):
		return self.backlog or not self.outbox.empty()

	def handle_write(self):
		msg = self.backlog
		if not msg:
			msg = self.outbox.get()
		sent = self.send(msg)
		self.backlog = msg[sent:]
		if self.slp is not None:
			time.sleep(self.slp)

	def handle_read(self):
		if self.dead:
			print('!!! read when dead')
			return

		data = self.recv(8192)
		if not data:
			self.dead = True
			return
		
		self.in_text += data.decode('utf-8', 'ignore')
		print(self.in_text)

		if self.stage == 'start':
			if 'type the text below, then hit [Enter]:' in self.in_text:
				self.stage = 'qwer'
				self.in_text = u''
				self.slp = 0.01
				for ch in u'qwer asdf\n':
					self.tx(ch)

		elif self.stage == 'qwer':
			if 'text appeared as you typed' in self.in_text:
				self.stage = 'color'
				self.in_text = u''
				self.slp = None
				self.tx(u'b')
				self.outbox.put(b'\xff\xfa\x1f\x00\x80\x00\x24\xff\xf0')  # 128x36

		elif self.stage == 'color':
			if 'does colours work?' in self.in_text:
				self.stage = 'codec'
				self.in_text = u''
				self.slp = None
				self.tx(u'y')

		elif self.stage == 'codec':
			if 'which line looks like' in self.in_text:
				self.stage = 'main'
				self.in_text = u''
				self.slp = None
				self.tx(u'a')

class Core(object):

	def __init__(self):
		self.clients = []
		for n in range(1):
			self.clients.append(Client())

		signal.signal(signal.SIGINT, self.signal_handler)

		self.stopping = False
		self.asyncore_alive = False
		self.asyncore_thr = threading.Thread(target=self.asyncore_worker)
		self.asyncore_thr.start()

	def run(self):
		print('  *  test is running')
		
		while not self.stopping:
			time.sleep(0.1)

		print('  *  asyncore terminating')
		clean_shutdown = False
		for n in range(0, 40):  # 2sec
			if not self.asyncore_alive:
				print('  *  asyncore stopped cleanly')
				clean_shutdown = True
				break
			time.sleep(0.05)
		
		if not clean_shutdown:
			print(' -X- asyncore is stuck')

		print('  *  asyncore cleanup')
		for c in self.clients:
			c.close()

		print('  *  bye')

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
