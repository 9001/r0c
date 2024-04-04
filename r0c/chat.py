# coding: utf-8
from __future__ import print_function
from .__init__ import TYPE_CHECKING
from . import util as Util
from .util import t2ymd_hms

from datetime import datetime
import calendar
import operator

if TYPE_CHECKING:
    from . import ivt100 as Ivt100
    from . import user as User
    from .irc import IRC_Chan

print = Util.print
UTC = Util.UTC


class NChannel(object):
    def __init__(self, name, topic):
        # type: (str, str) -> NChannel
        self.uchans = []  # type: list[UChannel]
        self.msgs = []  # type: list[Message]
        self.name = name
        self.topic = topic
        self.topic_bak = None
        self.user_act_ts = {}  # type: dict[str, int]  # str(nick) -> ts(last activity)
        self.usernames = u""  # sorted by activity
        self.immortal = False  # has bridges
        self.ircb = []  # type: list[IRC_Chan]

        self.log_fh = None  # active log file
        self.log_ctr = 0  # number of messages in file

    def get_name(self):
        if self.name:
            return u"#" + self.name
        ret = u", ".join(x.alias for x in self.uchans[:2])
        return ret or u"<abandoned private channel>"

    def __unicode__(self):
        return u"NChannel {0}".format(self.get_name())

    def __str__(self):
        return "NChannel {0}".format(self.get_name())

    def __repr__(self):
        return "NChannel({0}, {1})".format(self.name, repr(self.topic))

    def __lt__(self, other):
        return self.name < other.name

    def update_usernames(self):
        self.usernames = u", ".join(
            [
                k
                for k, _ in sorted(
                    self.user_act_ts.items(),
                    key=operator.itemgetter(1),
                    reverse=True,
                )[:32]
            ]
        )


class UChannel(object):
    def __init__(self, user, nchan, alias=None):
        # type: (Ivt100.VT100_Client, User.User, NChannel, str) -> UChannel
        self.user = user  # the user which this object belongs to
        self.nchan = nchan  # the NChannel object
        self.alias = alias  # local channel name (private)
        self.last_read = 0  # most recent sno viewed in this channel
        self.last_ping = 0  # most recent sno that was a hilight
        self.hilights = False
        self.activity = False
        self.display_notification = False
        self.lock_to_bottom = True
        self.vis = []  # type: list[VisMessage]  # visible messages

    def __unicode__(self):
        return u"UChannel <%s> @ <%s>" % (self.user, self.nchan)

    def __str__(self):
        return "UChannel <%s> @ <%s>" % (self.user, self.nchan)

    def __repr__(self):
        return "UChannel(%r, %r, %r)" % (self.user, self.nchan, self.alias)

    def update_activity_flags(self, set_last_read=False, last_nchan_msg=0):
        if not last_nchan_msg and self.nchan.msgs:
            last_nchan_msg = self.nchan.msgs[-1].sno

        if set_last_read:
            if self.vis:
                self.last_read = max(self.last_read, self.vis[-1].msg.sno)
            else:
                self.last_read = last_nchan_msg

        hilights = self.last_read < self.last_ping
        activity = self.last_read < last_nchan_msg

        self.display_notification = hilights or activity

        if (
            self.display_notification
            and self == self.user.active_chan
            and self.lock_to_bottom
        ):
            # don't display notifications in the status bar
            # when chan is active and bottom messages are visible
            self.display_notification = False

        if hilights:
            self.user.client.notify_new_hilight(self)
        elif activity:
            self.user.client.beep(3)

        if self.hilights != hilights or self.activity != activity:
            self.hilights = hilights
            self.activity = activity
            return True

        return False

    def jump_to_msg(self, msg_n):
        if msg_n >= len(self.nchan.msgs):
            msg_n = len(self.nchan.msgs) - 1

        self.vis = [
            VisMessage().c_new(self.nchan.msgs[msg_n], [u"x"], msg_n, 0, 1, self)
        ]

        self.lock_to_bottom = False
        self.user.client.need_full_redraw = True

    def jump_to_time(self, dt):
        ts = calendar.timegm(dt.timetuple())
        for msg in self.nchan.msgs:
            if msg.ts >= ts:
                i = self.nchan.msgs.index(msg)
                print("jump to {0} of {1}".format(i, len(self.nchan.msgs)))
                return self.jump_to_msg(i)

        return self.jump_to_msg(len(self.nchan.msgs) - 1)


class VisMessage(object):
    def __init__(self):
        pass

    def c_new(self, msg, txt, im, car, cdr, ch):
        # type: (Message, list[str], int, int, int, UChannel) -> VisMessage
        self.msg = msg  # the message object
        self.txt = txt  # the formatted text
        self.im = im  # offset into the channel's message list
        self.car = car  # first visible line
        self.cdr = cdr  # last visible line PLUS ONE
        self.cli = ch.user.client

        if not msg or not msg.user:
            Util.whoops("msg bad")
        if not ch or not ch.user:
            Util.whoops("user bad")

        self.unformatted = txt[0]
        self.hilight = bool(ch.user.nick_re.search(msg.txt))
        self.unread = msg.user != ch.user.nick and msg.sno > ch.last_read

        # print('add msg for {0} which is unread {1}, hilight {2}'.format(
        # 	ch.user.nick, self.unread, self.hilight))

        self.apply_markup()
        return self

    def c_segm(self, other, src_car, src_cdr, new_car, new_cdr, ch):
        self.msg = other.msg
        self.txt = other.txt[src_car:src_cdr]
        self.im = other.im
        self.car = new_car
        self.cdr = new_cdr
        self.cli = ch.user.client

        self.hilight = other.hilight
        self.unread = other.unread
        if src_car == 0:
            self.unformatted = other.unformatted
        else:
            self.unformatted = self.txt[0]

        return self

    def plaintext(self):
        return [self.unformatted] + self.txt[1:]

    def apply_markup(self):
        ln = self.unformatted
        if self.cli.vt100:
            if self.hilight and self.unread:
                prefix = u"\033[1;35;7m"
                postfix = u"\033[0m "
            elif self.hilight:
                prefix = u"\033[1;35m"
                postfix = u"\033[0m "
            elif self.unread:
                prefix = u"\033[7m"
                postfix = u"\033[0m "
            else:
                prefix = None
                postfix = None
        else:
            prefix = u""
            if self.hilight and not self.cli.view:
                postfix = u"="
            else:
                postfix = None

        if self.cli.view:
            if postfix:
                self.txt[0] = u"%s%s%s" % (prefix, ln, postfix)
            elif self.cli.vt100 and u"\033" not in ln:
                ofs = 1 + len(ln) - len(ln.lstrip())
                self.txt[0] = u"\033[0;1m%s\033[0;36m%s\033[0m" % (ln[:ofs], ln[ofs:])
            else:
                self.txt[0] = ln
        elif postfix and not ln.startswith(u" "):
            ofs = ln.find(u" ")
            self.txt[0] = u"%s%s%s%s" % (prefix, ln[:ofs], postfix, ln[ofs + 1 :])
        else:
            self.txt[0] = ln


class Message(object):
    def __init__(self, to, ts, user, txt):
        # type: (NChannel, int, str, str) -> Message
        self.ts = ts  # int timestamp; 1M msgs = 38MiB
        self.dt = datetime.fromtimestamp(ts, UTC)  # 1M msgs = 53MiB
        self.user = user  # str username
        self.txt = txt  # str text

        # set serial number based on last message in target
        if to and to.msgs:
            self.sno = to.msgs[-1].sno + 1
        else:
            self.sno = 0

    def __unicode__(self):
        hhmmss = t2ymd_hms(self.dt, "%04d-%02d%02d-%02d%02d%02d")
        return u"Message {0:x} time({1},{2}) from({3}) body({4})".format(
            id(self), self.ts, hhmmss, self.user, self.txt
        )

    def __str__(self):
        hhmmss = t2ymd_hms(self.dt, "%04d-%02d%02d-%02d%02d%02d")
        return "Message {0:x} time({1},{2}) from({3}) body({4})".format(
            id(self), self.ts, hhmmss, self.user, self.txt
        )

    def __repr__(self):
        return "Message({0}, '{1}', {2})".format(self.ts, self.user, repr(self.txt))
