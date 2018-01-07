# -*- coding: utf-8 -*-
if __name__ == '__main__':
	raise RuntimeError('\n{0}\n{1}\n{2}\n{0}\n'.format('*'*72,
		'  this file is part of retr0chat',
		'  run r0c.py instead'))

import hashlib
import base64
import threading

from .util import *

PY2 = (sys.version_info[0] == 2)



class NChannel(object):
	def __init__(self, name, topic):
		self.uchans = []       # UChannel instances
		self.msgs = []         # messages
		self.name = name
		self.topic = topic



class UChannel(object):
	def __init__(self, user, nchan):
		self.user = user        # the user which this object belongs to
		self.nchan = nchan      # the NChannel object
		self.last_ts = None     # last time the user viewed this channel
		self.last_hl = None     # last hilight
		self.last_draw = None   # last time this channel was sent
		self.hilights = False
		self.activity = False
		self.lock_to_bottom = True
		self.vis = []           # visible messages



class VisMessage(object):
	def __init__(self, msg, txt, im, nv):
		self.msg = msg          # the message object
		self.txt = txt          # the formatted text
		self.im = im            # offset into the channel's message list
		self.nv = nv            # number of visible lines



class Message(object):
	def __init__(self, user, to, ts, text):
		self.user = user        # str username
		self.to = to            # obj nchannel
		self.ts = ts            # int timestamp
		self.text = text        # str text



class User(object):
	def __init__(self, world, address):
		self.world = world
		self.client = None           # the client which this object belongs to
		self.chans = []              # UChannel instances
		self.active_chan = None      # UChannel
		self.new_active_chan = None  # set for channel change
		self.nick = None             # str
		
		plain_base = u'lammo/{0}'.format(address[0])

		for sep in u'/!@#$%^&*()_+-=[]{};:<>,.':

			plain = plain_base
			while True:
				#print(plain)
				nv = hashlib.sha256(plain.encode('utf-8')).digest()
				if PY2:
					nv = int(nv.encode('hex'), 16)
				else:
					nv = int.from_bytes(nv, 'big')
				#nv = base64.b64encode(nv).decode('utf-8')
				nv = b35enc(nv)
				nv = nv.replace('+','').replace('/','')[:6]

				ok = True
				for user in self.world.users:
					if user.nick == nv:
						ok = False
						break

				if ok:
					self.nick = nv
					break
				else:
					if len(plain) > 100:
						break
					plain += '/{0}'.format(address[1])

			if self.nick:
				break
		
		if not self.nick:
			raise RuntimeError("out of legit nicknames")

	def post_init(self):
		# create status channel
		# 
		text = u"""
	\033[1;31m╔═══════════════════╗    \033[0m
\033[1;33m(o─═╣\033[22m r e t r \033[1m0\033[22m c h a t \033[1m╠═─o)\033[0m
	\033[1;32m╚═══════════════════╝    \033[0m

Text formatting:
  \033[36mCTRL-O\033[0m  reset text formatting
  \033[36mCTRL-B\033[0m  bold/bright text on/off
  \033[36mCTRL-C\033[0m  followed by a colour code:
	   \033[36m2\033[0m  \033[32mgreen\033[0m,
	 \033[36m3,1\033[0m  \033[33;41myellow on red\033[0m --
		  say \033[1m/cmap\033[0m to see all options

Switching channels:
  \033[36mCTRL-Z\033[0m  jump to previous channel
  \033[36mCTRL-X\033[0m  jump to next channel
  \033[36m/3\033[0m      go to channel 3
  \033[36m/0\033[0m      go to this channel

Creating or joining the "general" chatroom:
  \033[36m/join #general\033[0m

Leaving a chatroom:
  \033[36m/part #some_room\033[0m

Changing your nickname:
  \033[36m/nick new_name\033[0m

Keybinds:
  \033[36mUp\033[0m / \033[36mDown\033[0m       sent message history
  \033[36mLeft\033[0m / \033[36mRight\033[0m    input field traversing
  \033[36mHome\033[0m / \033[36mEnd\033[0m      input field jump
  \033[36mPgUp\033[0m / \033[36mPgDown\033[0m   chatlog scrolling... \033[1mtry it :-)\033[0m

"""

#  >> if your terminal is blocking the CTRL key,
#  >> press ESC followed by the 2nd key instead
#Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.
#Lorem ipsum dolor sit amet, \033[1;31mconsectetur\033[0m adipiscing elit, sed do eiusmod tempor incididunt ut \033[1;32mlabore et dolore magna\033[0m aliqua. Ut enim ad minim veniam, quis nostrud \033[1;33mexercitation ullamco laboris nisi ut aliquip ex ea\033[0m commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est labo\033[1;35mrum.

		nchan = NChannel('r0c-status', 'r0c readme (and status info)')

		for line in text.splitlines():
			msg = Message('-info-', nchan, time.time(), line)
			nchan.msgs.append(msg)

		self.world.join_chan_obj(self, nchan)
		
		nchan = self.world.join_chan(self, 'general').nchan
		for n in range(1,200):
			txt = u'{0}: {1} EOL'.format(
				n, u', {0}_'.format(n).join(str(v) for v in range(1, min(8, n))))
			self.world.send_chan_msg(self.nick, nchan, txt)



class World(object):
	def __init__(self):
		self.users = []      # User instances
		self.nchans = []     # NChannel instances
		self.mutex = threading.RLock()

	def add_user(self, user):
		with self.mutex:
			self.users.append(user)

	def refresh_chan(self, nchan):
		for uchan in nchan.uchans:
			if uchan.user.active_chan == uchan:
				with uchan.user.client.mutex:
					uchan.user.refresh()

	def send_chan_msg(self, from_nick, nchan, text):
		with self.mutex:
			msg = Message(from_nick, nchan, time.time(), text)
			nchan.msgs.append(msg)
			nchan.latest = msg.ts
			self.refresh_chan(nchan)

	def join_chan_obj(self, user, nchan):
		with self.mutex:
			uchan = UChannel(user, nchan)
			user.chans.append(uchan)
			nchan.uchans.append(uchan)
			user.new_active_chan = uchan
			self.send_chan_msg('--', nchan,
				'\033[32m{0} has joined\033[0m'.format(user.nick))
			return uchan

	def get_nchan(self, name):
		for ch in self.nchans:
			if ch.name == name:
				return ch
		return None

	def join_chan(self, user, name):
		with self.mutex:
			nchan = self.get_nchan(name)
			if nchan is None:
				nchan = NChannel(name, '#{0} - no topic has been set'.format(name))
				self.nchans.append(nchan)
			
			return self.join_chan_obj(user, nchan)

	def part_chan(self, uchan):
		with self.mutex:
			user = uchan.user
			nchan = uchan.nchan
			with user.client.mutex:
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

			send_chan_msg(user.nick, nchan,
				'{0} has left'.format(user.nick))
