# -*- coding: utf-8 -*-
from __future__ import print_function
if __name__ == '__main__':
	raise RuntimeError('\r\n{0}\r\n\r\n  this file is part of retr0chat.\r\n  enter the parent folder of this file and run:\r\n\r\n    python -m r0c <telnetPort> <netcatPort>\r\n\r\n{0}'.format('*'*72))

from .util import *
from .chat import *

PY2 = (sys.version_info[0] == 2)



class World(object):
	def __init__(self, core):
		self.core = core
		self.users = []      # User instances
		self.pub_ch = []     # NChannel instances (public)
		self.priv_ch = []    # NChannel instances (private)
		self.dirty_ch = []   # Channels that have pending tx
		self.mutex = threading.RLock()

		# stats for benchmarking
		self.num_joins = 0
		self.num_parts = 0
		self.num_messages = 0

		threading.Thread(target=self.refresh_chans).start()

	def add_user(self, user):
		with self.mutex:
			self.users.append(user)

	def refresh_chans(self):
		self.chan_sync_active = True
		while not self.core.stopping:
			time.sleep(0.05)
			with self.mutex:
				for chan in self.dirty_ch:
					self.refresh_chan(chan)
				self.dirty_ch = []
		self.chan_sync_active = False
	
	def refresh_chan(self, nchan):
		for uchan in nchan.uchans:
			if uchan.user.active_chan == uchan:
				if not uchan.user.client.handshake_sz or \
					uchan.user.client.wizard_stage is not None:

					if DBG:
						print('!!! refresh_chan without handshake_sz')
					continue
				uchan.user.client.refresh(False)

	def send_chan_msg(self, from_nick, nchan, text):
		with self.mutex:
			self.num_messages += 1
			if nchan.name is None and not from_nick.startswith('-'):
				# private chan, check if we have anyone to send to
				if len(nchan.uchans) == 1:
					if nchan.uchans[0].alias == 'r0c-status':
						if nchan.uchans[0].user.nick == from_nick:
							self.send_chan_msg('-err-', nchan, 'this buffer does not accept messages, only commands\n')
							return
					
					else:
						# private chat without the other user added yet;
						# pull in the other user
						utarget = None
						target = nchan.uchans[0].alias
						if target != from_nick:
							for usr in self.users:
								if usr.nick == target:
									utarget = usr
									break

							if utarget is None:
								self.send_chan_msg('-err-', nchan,
									'\033[1;31mfailed to locate user "{0}"'.format(
										nchan.uchans[0].alias))
								return

							self.join_chan_obj(utarget, nchan, from_nick)
							# fallthrough to send message

			msg = Message(from_nick, nchan, time.time(), text)
			nchan.msgs.append(msg)
			nchan.latest = msg.ts
			#self.refresh_chan(nchan)
			if nchan not in self.dirty_ch:
				self.dirty_ch.append(nchan)

	def join_chan_obj(self, user, nchan, alias=None):
		with self.mutex:
			for uchan in user.chans:
				if uchan.nchan == nchan:
					return uchan
			
			self.num_joins += 1
			uchan = UChannel(user, nchan, alias)
			user.chans.append(uchan)
			#print('@@@ user {0} chans {1}, {2}'.format(user.nick, len(user.chans), user.chans[-1].alias or user.chans[-1].nchan.name))
			nchan.uchans.append(uchan)
			self.send_chan_msg('--', nchan,
				'\033[1;32m{0}\033[22m has joined'.format(user.nick))
			return uchan

	def get_pub_chan(self, name):
		for ch in self.pub_ch:
			if ch.name == name:
				return ch
		return None

	def get_priv_chan(self, user, alias):
		for ch in user.chans:
			if ch.alias == alias:
				return ch
		return None

	def join_pub_chan(self, user, name):
		with self.mutex:
			name = name.strip()
			nchan = self.get_pub_chan(name)
			if nchan is None:
				nchan = NChannel(name, '#{0} - no topic has been set'.format(name))
				self.pub_ch.append(nchan)
			
			ret = self.join_chan_obj(user, nchan)
			user.new_active_chan = ret
			return ret

	def join_priv_chan(self, user, alias):
		with self.mutex:
			uchan = self.get_priv_chan(user, alias)
			if uchan is None:
				nchan = NChannel(None, 'DM with [[uch_a]]')
				self.priv_ch.append(nchan)
				uchan = self.join_chan_obj(user, nchan)
				uchan.alias = alias
			return uchan

	def broadcast(self, msg, severity=1):
		""" 1=append, 2=append+scroll, 3=fullscreen? """
		with self.mutex:
			visited = {}
			for user in self.users:
				for uchan in user.chans:
					chan = uchan.nchan
					if chan in visited:
						continue
					visited[chan] = 1
					self.send_chan_msg('-err-', chan, msg)
				
				if severity > 1:
					if user.active_chan:
						if not user.active_chan.lock_to_bottom:
							user.active_chan.lock_to_bottom = True
							user.client.need_full_redraw = True
					else:
						user.client.say("\n [[ broadcast message ]]\n {0}\n".format(
							msg).replace(u"\n", u"\r\n").encode('utf-8'))

	def part_chan(self, uchan):
		with self.mutex:
			self.num_parts += 1
			user = uchan.user
			nchan = uchan.nchan
			i = None
			if user.active_chan == uchan:
				i = user.chans.index(uchan)
			user.chans.remove(uchan)
			nchan.uchans.remove(uchan)
			if i:
				if len(user.chans) <= i:
					i -= 1
				user.new_active_chan = user.chans[i]
			del uchan

			self.send_chan_msg('--', nchan,
				'\033[1;33m{0}\033[22m has left'.format(user.nick))

