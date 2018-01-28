#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function


"""r0c.py: retr0chat Telnet/Netcat Server"""
__version__   = "0.9"
__author__    = "ed <a@ocv.me>"
__credits__   = ["stackoverflow.com"]
__license__   = "MIT"
__copyright__ = 2018


import os
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
from .ivt100   import *
from .inetcat  import *
from .itelnet  import *
from .chat     import *
from .user     import *
from .world    import *

if not PY2:
	from .diag import *


class Core(object):
	def __init__(self):
		pass

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

		try: os.makedirs('log/pm')
		except: pass

		print('  *  py {0}'.format(host_os()))

		self.telnet_port = int(sys.argv[1])
		self.netcat_port = int(sys.argv[2])

		print('  *  Telnet server on port ' + str(self.telnet_port))
		print('  *  NetCat server on port ' + str(self.netcat_port))

		self.stopping = 0
		self.threadmon = False
		self.pushthr_alive = False
		self.asyncore_alive = False

		print('  *  Capturing ^C')
		signal.signal(signal.SIGINT, self.signal_handler)

		print('  *  Creating world')
		self.world = World(self)

		print('  *  Starting Telnet server')
		self.telnet_server = TelnetServer('0.0.0.0', self.telnet_port, self.world, self.netcat_port)

		print('  *  Starting NetCat server')
		self.netcat_server = NetcatServer('0.0.0.0', self.netcat_port, self.world, self.telnet_port)

		print('  *  Loading user configs')
		self.telnet_server.load_configs()
		self.netcat_server.load_configs()

		print('  *  Starting push driver')
		self.push_thr = threading.Thread(target=self.push_worker, args=(
			self.world, [self.telnet_server, self.netcat_server],), name='push')
		#self.push_thr.daemon = True
		self.push_thr.start()

		print('  *  Handover to asyncore')
		self.asyncore_thr = threading.Thread(target=self.asyncore_worker, name='ac_mgr')
		self.asyncore_thr.start()


	def run(self):
		print('  *  r0c is up')
		
		if not BENCHMARK:
			while not self.stopping:
				time.sleep(0.1)
		else:
			last_joins = 0
			last_parts = 0
			last_messages = 0
			while not self.stopping:
				for n in range(20):
					if self.stopping:
						break
					time.sleep(0.1)

				print('{0:.3f}  j {1}  p {2}  m {3}  d {4},{5},{6}'.format(time.time(),
					self.world.num_joins, self.world.num_parts, self.world.num_messages,
					self.world.num_joins - last_joins,
					self.world.num_parts - last_parts,
					self.world.num_messages - last_messages))
				
				last_joins = self.world.num_joins
				last_parts = self.world.num_parts
				last_messages = self.world.num_messages

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

		print('  *  Saving user configs')
		self.telnet_server.save_configs()
		self.netcat_server.save_configs()

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


	def push_worker(self, world, ifaces):
		self.pushthr_alive = True
		
		nth_iter = 0
		last_ts = None
		last_date = None
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

			#ts = (ts - 1516554584) * 10000
			date = datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
			if date != last_date:
				if last_date:
					world.broadcast_message(
						"\033[36mday changed to \033[1m{0}".format(date))
				last_date = date

			for iface in ifaces:
				for client in iface.clients:
					if client.handshake_sz:
						client.refresh(False)

			nth_iter += 1
			if nth_iter % 600 == 0:
				for iface in ifaces:
					iface.save_configs()
		
		self.pushthr_alive = False


	def shutdown(self):
		#monitor_threads()
		self.stopping += 1
		if self.stopping >= 3:
			os._exit(1)


	def signal_handler(self, signal, frame):
		if THREADMON and not self.threadmon:
			self.threadmon = True
			monitor_threads()
		else:
			self.shutdown()


def run():
	core = Core()
	try:
		core.start()
		core.run()
	except:
		whoops()
		os._exit(1)


mode = 'normal'
#mode = 'profiler'
#mode = 'unrag-speedtest'
#mode = 'unrag-layout-test-v1'
#mode = 'unrag-layout-test-interactive'
#mode = 'test-ansi-annotation'


if mode == 'normal':
	run()

if mode == 'profiler':
	print('  *  PROFILER ENABLED')
	statfile = 'profiler-results'
	import yappi
	yappi.start()
	run()
	yappi.stop()
	
	fn_stats = yappi.get_func_stats()
	thr_stats = yappi.get_thread_stats()

	print()
	for ext in ['pstat','callgrind','ystat']:
		print('writing {0}.{1}'.format(statfile, ext))
		fn_stats.save('{0}.{1}'.format(statfile, ext), type=ext)

	with open('{0}.func'.format(statfile), 'w') as f:
		fn_stats.print_all(out=f)

	with open('{0}.thr'.format(statfile), 'w') as f:
		thr_stats.print_all(out=f)

	print('\n\n{0}\n  func stats\n{0}\n'.format('-'*72))
	fn_stats.print_all()
	
	print('\n\n{0}\n  thread stats\n{0}\n'.format('-'*72))
	thr_stats.print_all()


if mode == 'unrag-speedtest':
	bench_unrag('../radio.long')

if mode == 'unrag-layout-test-v1':
	unrag_layout_test_dump()

if mode == 'unrag-layout-test-interactive':
	unrag_layout_test_interactive()

if mode == 'test-ansi-annotation':
	test_ansi_annotation()
