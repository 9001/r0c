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
	def __init__(self, name):
		self.uchans = []       # UChannel instances
		self.msgs = []         # messages
		self.topic = u''
		self.name = u''



class UChannel(object):
	def __init__(self, user, nchan):
		self.user = user        # the user which this object belongs to
		self.nchan = nchan      # the NChannel object
		self.last_ts = None     # last time the user viewed this channel
		self.last_hl = None     # last hilight
		self.last_draw = None   # last time this channel was sent
		self.hilights = False
		self.activity = False
		self.scroll_pos = None  # locked to bottom, otherwise ts of top msg
		self.car_im = None      # first visible message, int
		self.car_ts = None      # first visible message, timestamp
		self.car_lv = None      # first visible message, num lines
		self.cdr_im = None      # last visible message, int
		self.cdr_ts = None      # last visible message, timestamp
		self.cdr_lv = None      # last visible message, num lines



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

		# create status channel
		# 
		nchan = NChannel('r0c-status')
		nchan.topic = 'r0c readme (and status info)'
		text = """
Welcome to retr0chat

Text formatting:
  CTRL-O  reset text formatting
  CTRL-B  bold/bright text on/off
  CTRL-C  followed by a color code:
	   1  \033[31mred\033[0m
	   2  \033[32mgreen\033[0m
	   3  \033[33myellow\033[0m
	   4  \033[34mblue\033[0m
	   5  \033[35mpurple\033[0m
	   6  \033[36mcyan\033[0m
	   7  \033[37mwhite\033[0m
	 3,4  \033[1;33;44myellow on blue\033[0m

Switching channels:
  CTRL-Z  jump to previous channel
  CTRL-X  jump to next channel
  /3      go to channel 3
  /0      go to this channel

Creating or joining the "general" chatroom:
  /join #general

Leaving a chatroom:
  /part #some_room

Changing your nickname:
  /nick new_name

if your terminal is blocking the CTRL key,
press ESC followed by the 2nd key instead

"""
		for line in text.splitlines():
			msg = Message('sys', nchan, time.time(), line)
			nchan.msgs.append(msg)

		self.world.join_chan(self, nchan)



class World(object):
	def __init__(self):
		self.users = []      # User instances
		self.nchans = []     # NChannel instances
		self.mutex = threading.RLock()

	def add_user(self, user):
		with self.mutex:
			self.users.append(user)

	def add_chan(self, nchan, user):
		with self.mutex:
			for ch in self.nchans:
				if ch.name == nchan.name:
					raise RuntimeError('add_chan already exists')
			self.nchans.append(nchan)
			join_chan(user, nchan)

	def refresh_chan(self, nchan):
		for uchan in nchan.uchans:
			if uchan.user.active_chan == uchan:
				with uchan.user.mutex:
					uchan.user.refresh()

	def send_chan_msg(self, from_nick, nchan, text):
		with self.mutex:
			msg = Message(from_nick, nchan, time.time(), text)
			nchan.msgs.append(msg)
			nchan.latest = msg.ts
			self.refresh_chan(nchan)

	def join_chan(self, user, nchan):
		with self.mutex:
			uchan = UChannel(user, nchan)
			user.chans.append(uchan)
			nchan.uchans.append(uchan)
			user.new_active_chan = uchan
			self.send_chan_msg(user.nick, nchan,
				'\033[32m{0} has joined\033[0m'.format(user.nick))

	def part_chan(self, uchan):
		with self.mutex:
			user = uchan.user
			nchan = uchan.nchan
			with user.mutex:
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
