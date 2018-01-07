#!/usr/bin/env python2
# -*- coding: utf-8 -*-



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

from r0c.config   import *
from r0c.util     import *
from r0c.c_vt100  import *
from r0c.c_netcat import *
from r0c.c_telnet import *
from r0c.chat     import *



if __name__ != '__main__':
	print('this is not a library')
	sys.exit(1)



class Core(object):
	def __init__(self):
		if len(sys.argv) != 3:
			print()
			print('  need argument 1:  Telnet port  (or 0 to disable)')
			print('  need argument 2:  NetCat port  (or 0 to disable)')
			print()
			print('  example:')
			print('    {0} 23 531'.format(sys.argv[0]))
			print()
			sys.exit(1)

		self.telnet_port = int(sys.argv[1])
		self.netcat_port = int(sys.argv[2])

		print('  *  Telnet server on port ' + str(self.telnet_port))
		print('  *  NetCat server on port ' + str(self.netcat_port))

		self.stopped = False
		self.stopping = False
		self.pushthr_alive = False
		self.asyncore_alive = False

		self.p = Printer()

		self.p.p('  *  Capturing ^C')
		signal.signal(signal.SIGINT, self.signal_handler)

		self.p.p('  *  Creating world')
		self.world = World(self)

		self.p.p('  *  Starting Telnet server')
		self.telnet_server = TelnetServer(self.p, '0.0.0.0', self.telnet_port, self.world)

		self.p.p('  *  Starting NetCat server')
		self.netcat_server = NetcatServer(self.p, '0.0.0.0', self.netcat_port, self.world)

		self.p.p('  *  Starting push driver')
		self.push_thr = threading.Thread(target=self.push_worker, args=([self.telnet_server, self.netcat_server],))
		#self.push_thr.daemon = True
		self.push_thr.start()

		self.p.p('  *  Handover to asyncore')
		self.asyncore_thr = threading.Thread(target=self.asyncore_worker)
		self.asyncore_thr.start()


	def run(self):
		core.p.p('  *  r0c is up')
		while not self.stopped:
			time.sleep(0.1)
		core.p.p('  *  bye')


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
		self.stopping = True

		self.p.p('  *  Stopping asyncore')
		while self.asyncore_alive:
			time.sleep(0.05)
		
		self.p.p('  *  Terminating asyncore')
		self.netcat_server.close()
		self.telnet_server.close()
		
		self.p.p('  *  r0c is down')
		self.stopped = True


	def signal_handler(self, signal, frame):
		self.shutdown()


core = Core()
core.run()
