#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function


"""r0c.py: retr0chat Telnet/Netcat Server"""
__version__   = "0.9"
__author__    = "ed <a@ocv.me>"
__credits__   = ["stackoverflow.com"]
__license__   = "MIT"
__copyright__ = 2018


import sys
import signal
if sys.version_info[0] == 2:
	sys.dont_write_bytecode = True

fail = False
if __name__ != '__main__':
	fail = True

if fail or not 'r0c' in sys.modules:
	print('\r\n  retr0chat must be launched as a module.\r\n  in the project root, run this:\r\n\r\n    python -m r0c\r\n')
	sys.exit(1)

from .config   import *
from .util     import *
from .c_vt100  import *
from .c_netcat import *
from .c_telnet import *
from .chat     import *


class Core(object):
	def __init__(self):
		try:
			self.start()
		except:
			whoops()
			import os
			os._exit(1)

	def start(self):
		if len(sys.argv) != 3:
			print()
			print('  need argument 1:  Telnet port  (or 0 to disable)')
			print('  need argument 2:  NetCat port  (or 0 to disable)')
			print()
			print('  example 1:')
			print('    python -m r0c 2323 1531')
			print()
			print('  example 2:')
			print('    python -m r0c 23 531')
			print()
			sys.exit(1)

		self.telnet_port = int(sys.argv[1])
		self.netcat_port = int(sys.argv[2])

		print('  *  Telnet server on port ' + str(self.telnet_port))
		print('  *  NetCat server on port ' + str(self.netcat_port))

		self.stopping = False
		self.pushthr_alive = False
		self.asyncore_alive = False

		print('  *  Capturing ^C')
		signal.signal(signal.SIGINT, self.signal_handler)

		print('  *  Creating world')
		self.world = World(self)

		print('  *  Starting Telnet server')
		self.telnet_server = TelnetServer('0.0.0.0', self.telnet_port, self.world)

		print('  *  Starting NetCat server')
		self.netcat_server = NetcatServer('0.0.0.0', self.netcat_port, self.world)

		print('  *  Starting push driver')
		self.push_thr = threading.Thread(target=self.push_worker, args=([self.telnet_server, self.netcat_server],))
		#self.push_thr.daemon = True
		self.push_thr.start()

		print('  *  Handover to asyncore')
		self.asyncore_thr = threading.Thread(target=self.asyncore_worker)
		self.asyncore_thr.start()


	def run(self):
		print('  *  r0c is up')
		
		while not self.stopping:
			time.sleep(0.1)

		print('\r\n  *  asyncore stopping')
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
		self.netcat_server.close()
		self.telnet_server.close()
		
		print('  *  r0c is down')


	def asyncore_worker(self):
		self.asyncore_alive = True

		timeout = 0.05
		while not self.stopping:
			asyncore.loop(timeout, count=0.5/timeout)

		self.asyncore_alive = False


	def push_worker(self, ifaces):
		self.pushthr_alive = True
		
		last_ts = None
		while not self.stopping:
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
					if not client.handshake_sz:
						print('!!! push_worker without handshake_sz')
					client.refresh(False)
		
		self.pushthr_alive = False


	def shutdown(self):
		#monitor_threads()
		self.stopping = True


	def signal_handler(self, signal, frame):
		self.shutdown()


core = Core()
core.run()

