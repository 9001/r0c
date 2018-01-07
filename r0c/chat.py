# -*- coding: utf-8 -*-
if __name__ == '__main__':
	raise RuntimeError('\n{0}\n{1}\n{2}\n{0}\n'.format('*'*72,
		'  this file is part of retr0chat',
		'  run r0c.py instead'))

import hashlib
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
	def __init__(self, user, nchan, alias=None):
		self.user = user        # the user which this object belongs to
		self.nchan = nchan      # the NChannel object
		self.alias = alias      # local channel name (private)
		self.last_ts = None     # last time the user viewed this channel
		self.last_hl = None     # last hilight
		self.last_draw = None   # last time this channel was sent
		self.hilights = False
		self.activity = False
		self.lock_to_bottom = True
		self.vis = []           # visible messages



class VisMessage(object):
	def __init__(self, msg, txt, im, car, cdr):
		self.msg = msg          # the message object
		self.txt = txt          # the formatted text
		self.im  = im           # offset into the channel's message list
		self.car = car          # first visible line
		self.cdr = cdr          # last visible line PLUS ONE



class Message(object):
	def __init__(self, user, to, ts, txt):
		self.user = user        # str username
		self.to   = to          # obj nchannel
		self.ts   = ts          # int timestamp
		self.txt  = txt         # str text



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

	def post_init(self, client):
		self.client = client

	def create_channels(self):
		if self.client.codec in ['utf-8','cp437','shift_jis']:
			text = u"""
	\033[1;31m╔═══════════════════╗    \033[0m
\033[1;33m(o─═╣\033[22m r e t r \033[1m0\033[22m c h a t \033[1m╠═─o)\033[0m
	\033[1;32m╚═══════════════════╝    \033[0m
"""
			
		else:
			text = u"""
	 \033[1;31m/=================\\   \033[0m
\033[1;33m(o-=]\033[22m r e t r \033[1m0\033[22m c h a t \033[1m[=-o)\033[0m
	 \033[1;32m\\=================/   \033[0m
"""
		
		text += u"""
Useful commands:
   \033[36m/nick\033[0m  change your nickname
   \033[36m/help\033[0m  full commands listing

Text formatting:
  \033[36mCTRL-O\033[0m  reset text formatting
  \033[36mCTRL-B\033[0m  bold/bright text on/off
  \033[36mCTRL-K\033[0m  followed by a colour code:
	   \033[36m2\033[0m  \033[32mgreen\033[0m,
	 \033[36m3,1\033[0m  \033[33;41myellow on red\033[0m --
		  say \033[1m/cmap\033[0m to see all options

Switching channels:
  \033[36mCTRL-A\033[0m  jump to previous channel
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
  \033[36mUp\033[0m / \033[36mDown\033[0m       input history
  \033[36mLeft\033[0m / \033[36mRight\033[0m    input field traversing
  \033[36mHome\033[0m / \033[36mEnd\033[0m      input field jump
  \033[36mPgUp\033[0m / \033[36mPgDown\033[0m   chatlog scrolling... \033[1mtry it :-)\033[0m

if you are using a mac, PgUp is fn-Shift-PgUp

"""

# cp437 box æøå
#\xc9\xcd\xcd\xcd\xcd\xcd\xbb
#\xba \x91\x94\x86 \xba
#\xc8\xcd\xcd\xcd\xcd\xcd\xbc

#  >> if your terminal is blocking the CTRL key,
#  >> press ESC followed by the 2nd key instead

# æ     ø     å
# c3 a6 c3 b8 c3 a5 utf-8 to putty, works
# c3 a6 c3 b8 c3 a5 utf-8 from putty, fucked

		if False:
			lipsum1 = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
			lipsum2 = "Lorem ipsum dolor sit amet, \033[1;31mconsectetur\033[0m adipiscing elit, sed do eiusmod tempor incididunt ut \033[1;32mlabore et dolore magna\033[0m aliqua. Ut enim ad minim veniam, quis nostrud \033[1;33mexercitation ullamco laboris nisi ut aliquip ex ea\033[0m commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est labo\033[1;35mrum."
			for n in range(10):
				text += lipsum1 + "\n"
				text += lipsum2 + "\n"

		uchan = self.world.join_priv_chan(self, 'r0c-status')
		nchan = uchan.nchan
		nchan.topic = 'r0c readme (and status info)'

		for line in text.splitlines():
			msg = Message('-info-', nchan, time.time(), line)
			nchan.msgs.append(msg)

		self.new_active_chan = uchan
		


		if True:
			uchan = self.world.join_pub_chan(self, 'general')
			nchan = uchan.nchan
			if len(nchan.msgs) < 100:
				for n in range(1,200):
					#txt = u'{0:03}_{1} EOL'.format(
					#	n, u'_dsfarg, {0:03}_'.format(n).join(
					#		str(v).rjust(3, '0') for v in range(1, min(48, n))))
					txt = u'{1}_{0:03}     \\\\\\\\'.format(n,
						u'_{0:03}     \\\\\\\\\n'.format(n).join(
							str(v).rjust(v+4, ' ') for v in range(0, 12)))
					self.world.send_chan_msg(self.nick, nchan, txt)

		if False:
			uchan = self.world.join_pub_chan(self, 'smalltalk')
			nchan = uchan.nchan
			for n in range(1,3):
				txt = u'  message {0}\n      mes {0}'.format(n)
				self.world.send_chan_msg(self.nick, nchan, txt)



	def exec_cmd(self, cmd_str):
		inf = self.world.get_priv_chan(self, 'r0c-status').nchan
		cmd = cmd_str # the command keyword
		arg = None    # single argument with spaces
		arg1 = None   # 1st of 2 arguments
		arg2 = None   # 2nd of 2 arguments
		
		ofs = cmd.find(' ')
		if ofs > 0:
			cmd = cmd_str[:ofs]
			arg = cmd_str[ofs+1:]
		cmd = cmd.lower()

		if arg:
			ofs = arg.find(' ')
			if ofs > 0:
				arg1 = arg[:ofs].lower()
				arg2 = arg[ofs+1:]

		if cmd == 'me':
			self.world.send_chan_msg('***', self.active_chan.nchan,
				'\033[1m{0}\033[22m {1}'.format(self.nick, arg))

		elif cmd == 'nick' or cmd == 'n':
			if not arg:
				self.world.send_chan_msg('-err-', inf, """[invalid argument]
  usage:     /nick  new_nickname
  example:   /nick  spartacus
""")
				return

			if arg.startswith('-'):
				self.world.send_chan_msg('-err-', inf, """[invalid argument]
  nicks cannot start with "-" (dash)
""")
				return

			if u' ' in arg or u'\t' in arg:
				self.world.send_chan_msg('-err-', inf, """[invalid argument]
  nicks cannot contain whitespace
""")
				return

			other_user = None
			with self.world.mutex:
				for usr in self.world.users:
					if usr.nick == arg:
						other_user = usr
						break
				
				if other_user is not None:
					self.world.send_chan_msg('-err-', inf, """[invalid argument]
  that nick is taken
""")
					return

				for uchan in self.chans:
					self.world.send_chan_msg('--', uchan.nchan,
						'\033[1;36m{0}\033[22m changed nick to \033[1m{1}'.format(self.nick, arg))
				
				# update title in DM windows
				for nchan in self.world.privchans:
					for usr in nchan.uchans:
						if usr.alias == self.nick:
							usr.alias = arg

				self.nick = arg



		elif cmd == 'topic' or cmd == 't':
			if not arg:
				self.world.send_chan_msg('-err-', inf, """[invalid argument]
  usage:     /topic  the_new_topic
  example:   /topic  cooking recipes
""")
				return

			uchan = self.active_chan
			nchan = uchan.nchan
			if nchan in self.world.privchans:
				self.world.send_chan_msg('-err-', inf, """[error]
  cannot change the topic of private channels
""")
				return

			old_topic = nchan.topic
			nchan.topic = arg
			self.world.send_chan_msg('--', nchan,
				'\033[36m{0} has changed the topic from [\033[0m{1}\033[36m] -to-> [\033[0m{2}\033[36m]\033[0m'.format(
				self.nick, old_topic, arg))



		elif cmd == 'join' or cmd == 'j':
			if not arg or len(arg) < 2:
				self.world.send_chan_msg('-err-', inf, """[invalid arguments]
  usage:     /join  #channel_name
  example:   /join  #general
""")
				return
			
			if not arg.startswith('#'):
				self.world.send_chan_msg('-err-', inf, """[error]
  illegal channel name:  {0}
  channel names must start with #
""".format(arg))
				return

			nchan = self.world.join_pub_chan(self, arg[1:]).nchan



		elif cmd == 'part' or cmd == 'p':
			if self.active_chan.alias == 'r0c-status':
				self.world.send_chan_msg('-err-', inf, """[error]
  cannot part the status channel
""".format(arg))
				return

			self.world.part_chan(self.active_chan)



		elif cmd == 'msg' or cmd == 'm':
			if not arg1 or not arg2:
				self.world.send_chan_msg('-err-', inf, """[invalid arguments]
  usage:     /msg   nickname   your message text
  example:   /msg   ed   hello world
""")
				return

			found = None
			for usr in self.world.users:
				if usr.nick == arg1:
					found = usr
					break

			if not found:
				self.world.send_chan_msg('-err-', inf, """[user not found]
  "{0}" is not online
""".format(arg1))
				return

			uchan = self.world.join_priv_chan(self, arg1)
			self.new_active_chan = uchan
			self.world.send_chan_msg(self.nick, uchan.nchan, arg2)



		elif cmd == 'up' or cmd == 'u':
			self.client.scroll_cmd = -(self.client.h - 4)
		
		elif cmd == 'down' or cmd == 'd':
			self.client.scroll_cmd = +(self.client.h - 4)
		
		elif cmd == 'latest' or cmd == 'l':
			self.active_chan.lock_to_bottom = True
			self.client.need_full_redraw = True
			self.client.refresh(False)



		elif cmd == 'sw':
			try: arg = int(arg)
			except: pass
			
			if not arg:
				self.world.send_chan_msg('-err-', inf, """[invalid arguments]
  usage:     /sw  your_screen_width
  example:   /sw  80
""")
				return

			self.client.w = arg



		elif cmd == 'sh':
			try: arg = int(arg)
			except: pass
			
			if not arg:
				self.world.send_chan_msg('-err-', inf, """[invalid arguments]
  usage:     /sh  your_screen_height
  example:   /sh  24
""")
				return

			self.client.h = arg



		elif cmd == 'sd':
			msg = "\033[31mserver shutdown requested by \033[1m{0}".format(self.nick)
			visited = {}
			for user in self.world.users:
				for uchan in user.chans:
					chan = uchan.nchan
					if chan in visited:
						continue
					visited[chan] = 1
					self.world.send_chan_msg('-err-', chan, msg)
			
			def killer():
				time.sleep(0.5)
				self.world.core.shutdown()
			
			thr = threading.Thread(target=killer)
			thr.daemon = True
			thr.start()



		else:
			self.world.send_chan_msg('-err-', inf, """invalid command:  /{0}
  if you meant to send that as a message,
  escape the leading "/" by adding another "/"
""".format(cmd_str))











class World(object):
	def __init__(self, core):
		self.core = core
		self.users = []      # User instances
		self.pubchans = []   # NChannel instances (public)
		self.privchans = []  # NChannel instances (private)
		self.mutex = threading.RLock()

	def add_user(self, user):
		with self.mutex:
			self.users.append(user)

	def refresh_chan(self, nchan):
		for uchan in nchan.uchans:
			if uchan.user.active_chan == uchan:
				if not uchan.user.client.handshake_sz or \
					uchan.user.client.wizard_stage is not None:

					print('!!! refresh_chan without handshake_sz')
					continue
				uchan.user.client.refresh(False)

	def send_chan_msg(self, from_nick, nchan, text):
		with self.mutex:
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
			self.refresh_chan(nchan)

	def join_chan_obj(self, user, nchan, alias=None):
		with self.mutex:
			uchan = UChannel(user, nchan, alias)
			user.chans.append(uchan)
			#print('@@@ user {0} chans {1}, {2}'.format(user.nick, len(user.chans), user.chans[-1].alias or user.chans[-1].nchan.name))
			nchan.uchans.append(uchan)
			self.send_chan_msg('--', nchan,
				'\033[1;32m{0}\033[22m has joined'.format(user.nick))
			return uchan

	def get_pub_chan(self, name):
		for ch in self.pubchans:
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
			nchan = self.get_pub_chan(name)
			if nchan is None:
				nchan = NChannel(name, '#{0} - no topic has been set'.format(name))
				self.pubchans.append(nchan)
			
			ret = self.join_chan_obj(user, nchan)
			user.new_active_chan = ret
			return ret

	def join_priv_chan(self, user, alias):
		with self.mutex:
			uchan = self.get_priv_chan(user, alias)
			if uchan is None:
				nchan = NChannel(None, 'DM with [[uch_a]]')
				self.privchans.append(nchan)
				uchan = self.join_chan_obj(user, nchan)
				uchan.alias = alias
			return uchan

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

			self.send_chan_msg('--', nchan,
				'\033[1;33m{0}\033[22m has left'.format(user.nick))
