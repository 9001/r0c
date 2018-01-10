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
		self.lock_to_bottom = True
		self.vis = []           # visible messages

	def update_activity_flags(self):
		self.last_read = self.vis[-1].msg.sno if self.vis else 0
		self.hilights = (self.last_read < self.last_ping)
		self.activity = (self.last_read < self.nchan.msgs[-1].sno) \
			if self.nchan.msgs else 0



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
		
		# set serial number based on last message in target
		if to.msgs:
			self.sno = to.msgs[-1].sno + 1
		else:
			self.sno = 0

