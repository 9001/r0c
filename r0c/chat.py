# -*- coding: utf-8 -*-
from __future__ import print_function
if __name__ == '__main__':
	raise RuntimeError('\r\n{0}\r\n\r\n  this file is part of retr0chat.\r\n  enter the parent folder of this file and run:\r\n\r\n    python -m r0c <telnetPort> <netcatPort>\r\n\r\n{0}'.format('*'*72))

import threading

from .util import *

PY2 = (sys.version_info[0] == 2)


class NChannel(object):
	def __init__(self, name, topic):
		self.uchans = []       # UChannel instances
		self.msgs = []         # messages
		self.name = name
		self.topic = topic

		self.log_fh = None     # active log file
		self.log_ctr = 0       # number of messages in file
	
	def get_name(self):
		if self.name:
			return u'#' + self.name
		ret = u', '.join(x.alias for x in self.uchans[:2])
		return ret or '<abandoned private channel>'



class UChannel(object):
	def __init__(self, user, nchan, alias=None):
		self.user = user        # the user which this object belongs to
		self.nchan = nchan      # the NChannel object
		self.alias = alias      # local channel name (private)
		self.last_read = 0      # most recent sno viewed in this channel
		self.last_ping = 0      # most recent sno that was a hilight
		self.hilights = False
		self.activity = False
		self.display_notification = False
		self.lock_to_bottom = True
		self.vis = []           # visible messages

	def update_activity_flags(self, set_last_read=False, last_nchan_msg=0):
		if set_last_read:
			if self.vis:
				self.last_read = max(self.last_read, self.vis[-1].msg.sno)
			else:
				self.last_read = 0
		
		if not last_nchan_msg and self.nchan.msgs:
			last_nchan_msg = self.nchan.msgs[-1].sno

		hilights = self.last_read < self.last_ping
		activity = self.last_read < last_nchan_msg

		self.display_notification = hilights or activity
		
		if self.display_notification \
		and self == self.user.active_chan \
		and self.lock_to_bottom:
			# don't display notifications in the status bar
			# when chan is active and bottom messages are visible
			self.display_notification = False
	
		if self.hilights != hilights \
		or self.activity != activity :
			self.hilights = hilights
			self.activity = activity
			return True
		
		return False


class VisMessage(object):
	def __init__(self):
		pass

	def c_new(self, msg, txt, im, car, cdr, ch):
		self.msg = msg          # the message object
		self.txt = txt          # the formatted text
		self.im  = im           # offset into the channel's message list
		self.car = car          # first visible line
		self.cdr = cdr          # last visible line PLUS ONE
		self.vt100 = ch.user.client.vt100

		if not msg or not msg.user: whoops('msg bad')
		if not ch  or not ch.user:  whoops('user bad')
		
		self.unformatted = txt[0]
		self.hilight = bool(ch.user.nick_re.search(msg.txt))
		self.unread = \
			msg.user != ch.user.nick \
			and msg.sno > ch.last_read

		#print('add msg for {0} which is unread {1}, hilight {2}'.format(
		#	ch.user.nick, self.unread, self.hilight))

		self.apply_markup()
		return self

	def c_segm(self, other, src_car, src_cdr, new_car, new_cdr, ch):
		self.msg = other.msg
		self.txt = other.txt[src_car:src_cdr]
		self.im  = other.im
		self.car = new_car
		self.cdr = new_cdr
		self.vt100 = ch.user.client.vt100

		self.hilight = other.hilight
		self.unread = other.unread
		if src_car == 0:
			self.unformatted = other.unformatted
		else:
			self.unformatted = self.txt[0]

		return self

	def plaintext():
		return [self.unformatted] + self.txt[1:]

	def apply_markup(self):
		if self.vt100:
			postfix = u'\033[0m '
			if self.hilight and self.unread:
				prefix = u'\033[1;35;7m'
			elif self.hilight:
				prefix = u'\033[1;35m'
			elif self.unread:
				prefix = u'\033[7m'
			else:
				prefix = u''
				postfix = None
		else:
			prefix = u''
			if self.hilight:
				postfix = u'='
			else:
				postfix = None

		if postfix and not self.unformatted.startswith(' '):
			#print('applying prefix {0}'.format(b2hex(prefix.encode('utf-8'))))
			ofs = self.unformatted.find(' ')
			self.txt[0] = '{0}{1}{2}{3}'.format(
				prefix, self.unformatted[:ofs], \
				postfix, self.unformatted[ofs+1:])
		else:
			self.txt[0] = self.unformatted


class Message(object):
	def __init__(self, to, ts, user, txt):
		self.ts   = ts          # int timestamp
		self.user = user        # str username
		self.txt  = txt         # str text
		
		# set serial number based on last message in target
		if to and to.msgs:
			self.sno = to.msgs[-1].sno + 1
		else:
			self.sno = 0

