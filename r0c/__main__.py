#!/usr/bin/env python2
# -*- coding: utf-8 -*-
from __future__ import print_function
from .__init__ import *


"""r0c.py: retr0chat Telnet/Netcat Server"""
__author__    = "ed <a@ocv.me>"
__credits__   = ["stackoverflow.com"]
__license__   = "MIT"
__copyright__ = 2018


import os
import sys
import signal

if not 'r0c' in sys.modules:
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

	def start(self, args=None):
		if args is None:
			args = sys.argv
		
		if len(args) < 3:
			print()
			print('  need argument 1:  Telnet port  (or 0 to disable)')
			print('  need argument 2:  NetCat port  (or 0 to disable)')
			print('  optional arg. 3:  Password')
			print()
			print('  example 1:')
			print('    python -m r0c 2323 1531 hunter2')
			print()
			print('  example 2:')
			print('    python -m r0c 23 531')
			print()
			return False

		for d in ['pm','chan','wire']:
			try: os.makedirs(EP.log + d)
			except: pass

		print('  *  r0c {0}, py {1}'.format(S_VERSION, host_os()))

		self.telnet_port = int(args[1])
		self.netcat_port = int(args[2])

		print('  *  Telnet server on port ' + str(self.telnet_port))
		print('  *  NetCat server on port ' + str(self.netcat_port))

		if not self.read_password(args):
			return False
		
		print('  *  Logs at ' + EP.log)
		compat_chans_in_root()

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

		return True


	def read_password(self, args):
		self.password = ADMIN_PWD
		
		# password as argument overrides all others
		if len(args) > 3:
			self.password = args[3]
			print('  *  Password from argument')
			return True
		
		# password file in home directory overrides config
		pwd_file = os.path.join(EP.app, 'password.txt')
		if os.path.isfile(pwd_file):
			print('  *  Password from ' + pwd_file)
			with open(pwd_file, 'rb') as f:
				self.password = f.read().decode('utf-8').strip()
				return True

		# fallback to config.py
		print('  *  Password from ' + os.path.join(EP.src, 'config.py'))
		if self.password != u'hunter2':
			return True
		
		# default password is verboten
		print()
		print('\033[1;31m  change the ADMIN_PWD in the path above \033[0m')
		print('\033[1;31m  or provide your password as an argument \033[0m')
		print('\033[1;31m  or save it here: ' + pwd_file + '\033[0m')
		print()
		return False


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
			try:
				asyncore.loop(timeout, count=0.5/timeout)
			except Exception as ex:
				if 'Bad file descriptor' in str(ex):
					#print('osx bug ignored')
					continue
				whoops()

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

			with world.mutex:
				#ts = (ts - 1516554584) * 10000
				date = datetime.datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d')
				if date != last_date:
					if last_date:
						world.broadcast_message(
							u"\033[36mday changed to \033[1m{0}".format(date), False)
					last_date = date

				for iface in ifaces:
					for client in iface.clients:
						if client.handshake_sz:
							client.refresh(False)

					#print('next scheduled kick: {0}'.format('x' if iface.next_scheduled_kick is None else iface.next_scheduled_kick - ts))

					if iface.next_scheduled_kick is not None \
					and iface.next_scheduled_kick <= ts:
						to_kick = []
						next_min = None
						for sch in iface.scheduled_kicks:
							if sch[0] <= ts:
								to_kick.append(sch)
							else:
								if next_min is None \
								or next_min > sch[0]:
									next_min = sch[0]
						
						for sch in to_kick:
							timeout, remote, msg = sch
							iface.scheduled_kicks.remove(sch)
							if remote in iface.clients:
								if msg is None:
									iface.part(remote)
								else:
									iface.part(remote, False)
									print(msg)

						iface.next_scheduled_kick = next_min

				nth_iter += 1
				if nth_iter % 600 == 0:

					# flush client configs
					for iface in ifaces:
						iface.save_configs()

						# flush wire logs
						if LOG_RX or LOG_TX:
							for client in iface.clients:
								if client.wire_log:
									try: client.wire_log.flush()
									except: whoops()

					# flush chan logs
					for chan_list in [world.pub_ch, world.priv_ch]:
						for chan in chan_list:
							if chan.log_fh:
								try: chan.log_fh.flush()
								except: whoops()

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


def start_r0c(args):
	core = Core()
	try:
		if core.start(args):
			core.run()
	except:
		whoops()
		os._exit(1)


def main(args=None):
	mode = 'normal'
	#mode = 'profiler'
	#mode = 'unrag-speedtest'
	#mode = 'unrag-layout-test-v1'
	#mode = 'unrag-layout-test-interactive'
	#mode = 'test-ansi-annotation'
	#test_hexdump()


	if mode == 'normal':
		start_r0c(args)

	if mode == 'profiler':
		print('  *  PROFILER ENABLED')
		statfile = 'profiler-results'
		import yappi
		yappi.start()
		start_r0c(args)
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


if __name__ == '__main__':
	main()
