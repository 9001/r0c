# coding: utf-8
from __future__ import print_function
from .__version__ import S_VERSION, S_BUILD_DT
from .__init__ import EP, PY2, TYPE_CHECKING, unicode
from . import util as Util
from . import chat as Chat
from . import diag as Diag

import re
import time
import base64
import hashlib
import threading
from datetime import datetime

# debug imports
import code
import gc

if TYPE_CHECKING:
    from . import world as World
    from .ivt100 import VT100_Client

print = Util.print


HELP_INTRO = u"""\
Useful commands:
   \033[36m/nick\033[0m  change your nickname
   \033[36m/help\033[0m  how-to and about

Text formatting:
  \033[36mCTRL-O\033[0m  reset to default
  \033[36mCTRL-B\033[0m  enable bold/bright
  \033[36mCTRL-K\033[0m  followed by a colour code:
       \033[36m2\033[0m  - \033[32mgreen\033[0m,
    \033[36m15,4\033[0m  - \033[1;37;44mbold white on blue\033[0m --
            say \033[1m/cmap\033[0m to see all options

Switching channels:
  \033[36mCTRL-E\033[0m  jump to active channel
  \033[36mCTRL-A\033[0m  jump to previous channel
  \033[36mCTRL-X\033[0m  jump to next channel
  \033[36m/3\033[0m      go to channel 3
  \033[36m/0\033[0m      go to this channel

Creating or joining the "g" (general) chatroom:
  \033[36m/join #g\033[0m

Leaving a chatroom:
  \033[36m/part\033[0m

Changing your nickname:
  \033[36m/nick new_name\033[0m

Keybinds:
  \033[36mUp\033[0m / \033[36mDown\033[0m       input history
  \033[36mLeft\033[0m / \033[36mRight\033[0m    input field traversing
  \033[36mHome\033[0m / \033[36mEnd\033[0m      input field jump
  \033[36mPgUp\033[0m / \033[36mPgDown\033[0m   chatlog scrolling... \033[1mtry it :-)\033[0m

* if your terminal is tiny, try commands \033[36m/mn\033[0m and \033[36m/cy\033[0m
* Cannot scroll? try these:  \033[36mCTRL-U\033[0m  \033[36mCTRL-D\033[0m  \033[36m/u\033[0m  \033[36m/d\033[0m
"""


class User(object):
    def __init__(self, world, address):
        # type: (World.World, tuple[str, int]) -> User
        self.ar = world.ar
        self.world = world
        self.admin = False  # set true after challenge success
        self.client = None  # type: VT100_Client  # the connected client
        self.chans = []  # type: list[Chat.UChannel]
        self.active_chan = None  # type: Chat.UChannel
        self.new_active_chan = None  # set for channel change
        self.old_active_chan = None  # last focused channel
        self.nick = None  # type: str
        self.lnick = None  # type: str
        self.nick_re = None  # regex object for ping assert
        self.nick_rep = ""  # nickname part of nick_re pattern
        self.nick_len = None  # visible segment for self

    def __unicode__(self):
        return u"User {0} {1}".format(self.nick, self.client.adr[0])

    def __str__(self):
        return "User {0} {1}".format(self.nick, self.client.adr[0])

    def __repr__(self):
        return "User({0}, {1})".format(repr(self.nick), repr(self.client.adr[0]))

    def __lt__(self, other):
        return self.nick < other.nick

    def pattern_gen(self, depth=0):
        charset = u"/!@#$%^&*()_+-=[]{};:<>,."
        for ch in charset:
            yield ch

        if depth < 2:  # <= 3 chars
            for ch1 in charset:
                for ch2 in self.pattern_gen(depth + 1):
                    yield ch1 + ch2

    def set_rand_nick(self):
        plain_base = self.ar.nsalt + unicode(self.client.adr[0])
        for suffix in self.pattern_gen():
            plain = plain_base + suffix
            zb = hashlib.sha512(plain.encode("utf-8")).digest()
            zb = base64.b32encode(zb[:20]).lower()
            zs = re.sub("[^a-km-z]", "", zb.decode("utf-8"))
            nv = zs[:6]

            if not self.world.find_user(nv):
                self.set_nick(nv)
                break

    def create_channels(self):
        # while true; do tail -n +3 ansi | iconv -t 'cp437//IGNORE' | iconv -f cp437 | while IFS= read -r x; do printf "$x\n"; done | sed -r "s/$/$(printf '\033[K')/"; printf '\033[J'; sleep 0.2; printf '\033[H'; done

        if self.client.codec in ["utf-8", "cp437", "shift_jis"]:

            # the simple version
            text = u"""\
`1;30m________ ___ ________
`1;30m░▒▓█▀▀▀▀`37m █▀█ `30m▀▀▀▀█▓▒░   `0;36m┌pad1[`0mretr0chat r0c_ver`36m]pad2┐
`1;30m ░▒▓`36m █▀█ █ █ █▀▀ `30m▓▒░    `0;36m│`0mgithub.com/9001/r0c`36m│
`1;30m  ░▒`34m █   █▄█ █▄▄ `30m▒░     `0;36m╘═══════════════════╛
                             `34m  b. r0c_build `0m
"""
            # the messy version
            text = u"""
`1;30m________ `37m__`36m_ `30m________
`1;30m░▒▓█▀▀▀▀`37m █▀`46m▓`0;1;30m ▀▀▀▀█▓▒░   `0;36m┌pad1[`0mret`1mr0c`22mhat r0c_ver`36m]pad2┐
`1;30m ░▒▓ `34;46m▒`0;1;36m▀█ `37;46m▓`0m `1;37;46m▓`0m `1;36m█▀`34m▀ `30m▓▒░    `0;36m│`0mgithub.com/9001/r0c`36m│
`1;30m  ░▒ `34m█   `36m█▄█ `34;46m▒`0;1;34m▄▄ `30m▒░     `0;36m╘═══════════════════╛
                             `34m  b. r0c_build `0m
"""

        else:
            # the simple version
            text = u"""
  `1;37m     /^\\           `0mretr0chat r0c_ver `36m-----
  `1;36m/^^  | |  /^^      `0mgithub.com/9001/r0c
  `1;34m|    \\_/  \\__      `0;36m------b. r0c_build `0m
"""

            # the messy version
            text = u"""
`1;30m______    `37m_`30m    ______
`1;30m\\\\\\\\\\\\\\  `37m/ \\  `30m///////   `0mret`1mr0c`22mhat r0c_ver `36m---
 `1;30m\\\\ `36m/`37m^^  | |  `36m/^`0;36m^`1;30m //    `0mgithub.com/9001/r0c
  `1;30m\\ `0;36m|    `1m\\_/  `0;36m\\__ `1;30m/     `0;36m------b. r0c_build `0m
"""

        pad1 = pad2 = u"──"
        if len(S_VERSION) > 3:
            pad1 = pad1[1:]
        if len(S_VERSION) > 4:
            pad2 = pad2[1:]
        if len(S_VERSION) > 5:
            pad1 = pad1[1:]
        if len(S_VERSION) > 6:
            pad2 = pad2[1:]

        text = (
            text.replace(u"`", u"\033[")
            .replace(u"r0c_build", S_BUILD_DT)
            .replace(u"r0c_ver", S_VERSION)
            .replace(u"pad1", pad1)
            .replace(u"pad2", pad2)
        )
        text += HELP_INTRO

        if self.ar.motd:
            try:
                with open(self.ar.motd, "rb") as f:
                    text += f.read().replace(b"\r", b"").decode("utf-8", "replace")[:-1]
            except Exception as ex:
                t = "WARNING: could not read motd-file [%s]: %s"
                print(t % (self.ar.motd, ex))

        # x = u"`1;30m░▒▓█▀▀▀▀`37m█▀`46m▓`0;1;30m▀▀▀▀█▓▒░`0;36m┌ "
        # text += x.replace(u"`", u"\033[") * 66

        uchan = self.world.join_priv_chan(self, u"r0c-status")
        nchan = uchan.nchan
        nchan.topic = u"r0c readme (and status info)"

        msg = Chat.Message(nchan, time.time(), u"-nfo-", text)
        nchan.msgs.append(msg)

        self.new_active_chan = uchan

        self.client.handshake_world = True

    def admin_test(self, cmd, arg):
        if self.admin:
            return True

        print(
            "denied exec:  /{0} {1} from {2} ({3})".format(
                cmd, arg, self.nick, self.client.adr
            )
        )

        inf = self.world.get_priv_chan(self, u"r0c-status").nchan

        self.world.send_chan_msg(
            u"-err-",
            inf,
            u"""\033[1;31m[denied]\033[0m
  don't move, the police are on the way
""",
        )

        return False

    def exec_cmd(self, cmd_str):
        # print('handle {0}'.format(cmd_str))
        inf = self.world.get_priv_chan(self, u"r0c-status").nchan
        cmd = cmd_str  # the command keyword
        arg = None  # single argument with spaces
        arg1 = None  # 1st of 2 arguments
        arg2 = None  # 2nd of 2 arguments

        ofs = cmd.find(u" ")
        if ofs > 0:
            cmd = cmd_str[:ofs]
            arg = cmd_str[ofs + 1 :]
        cmd = cmd.lower()

        if arg:
            arg1 = arg
            ofs = arg.find(u" ")
            if ofs > 0:
                arg1 = arg[:ofs].lower()
                arg2 = arg[ofs + 1 :]

        if cmd == u"help":
            self.help(arg, inf)

        elif cmd == u"me":
            self.world.send_chan_msg(
                u"***",
                self.active_chan.nchan,
                u"\033[1m{0}\033[22m {1}".format(self.nick, arg),
            )

        elif cmd == u"auth":
            if arg == self.ar.pw:
                self.admin = True
                self.world.send_chan_msg(u"-nfo-", inf, u"please don't break anything")
            else:
                self.world.send_chan_msg(u"-err-", inf, u"wrong password")

        elif cmd == u"nick" or cmd == u"n":
            if not arg:
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[invalid argument]
  usage:     /nick  new_nickname
  example:   /nick  spartacus
""",
                )
                return

            legit_chars = Util.azAZ
            legit_chars += u"0123456789"
            legit_within = u"`~!@#$%^&*()_+-=[]{};':\"|,./<>?"
            new_nick = u""
            err_extra = u""
            for ch in arg:
                if ch in legit_chars or (ch in legit_within and new_nick):
                    new_nick += ch
                elif not new_nick:
                    err_extra = u"  (nicks must begin with an alphanumeric character)\n"

            if not new_nick:
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"[invalid argument]\n  "
                    + u"yooo EXCLUSIVELY illegal chars in new nick\n",
                )
                return

            if new_nick != arg:
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"[invalid argument]\n  "
                    + u"some illegal characters were removed\n"
                    + err_extra,
                )

            if len(new_nick) > 32:
                self.world.send_chan_msg(
                    u"-err-", inf, u"[invalid argument]\n  " + u"too long\n"
                )
                return

            with self.world.mutex:
                if self.world.find_user(new_nick):
                    self.world.send_chan_msg(
                        u"-err-",
                        inf,
                        u"[invalid argument]\n  " + u"that nick is taken\n",
                    )
                    return

                print(
                    "nick change:  {2} {0} -> {1}".format(
                        self.nick, new_nick, self.client.adr[0]
                    )
                )

                for uchan in self.chans:
                    self.world.send_chan_msg(
                        u"--",
                        uchan.nchan,
                        u"\033[1;36m{0}\033[22m changed nick to \033[1m{1}".format(
                            self.nick, new_nick
                        ),
                        False,
                    )

                # update last-spoke tables
                now = time.time()
                for nchan in [x.nchan for x in self.chans]:
                    nchan.user_act_ts[new_nick] = now
                    nchan.user_act_ts.pop(self.nick, None)
                    nchan.update_usernames()

                # update title in DM windows
                for nchan in self.world.priv_ch:
                    for usr in nchan.uchans:
                        if usr.alias == self.nick:
                            usr.alias = new_nick

                self.set_nick(new_nick)

        elif cmd == u"topic" or cmd == u"t":
            if not arg:
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[invalid argument]
  usage:     /topic  the_new_topic
  example:   /topic  cooking recipes
""",
                )
                return

            uchan = self.active_chan
            nchan = uchan.nchan
            if nchan in self.world.priv_ch:
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[error]
  cannot change the topic of private channels
""",
                )
                return

            old_topic = nchan.topic
            nchan.topic = arg
            self.world.send_chan_msg(
                u"--",
                nchan,
                u"\033[36m{0} has changed the topic from [\033[0m{1}\033[36m] -to-> [\033[0m{2}\033[36m]\033[0m".format(
                    self.nick, old_topic, arg
                ),
            )

        elif cmd == u"join" or cmd == u"j":
            if arg and not arg.startswith(u"#"):
                arg = u"#" + arg

            if not arg or len(arg) < 2:
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[invalid arguments]
  usage:     /join  #channel_name
  example:   /join  #general
""",
                )
                return

            print("     ->join:  %s  %s" % (arg, self.nick))
            nchan = self.world.join_pub_chan(self, arg[1:]).nchan
            # this is in charge of activating the new channel,
            # rapid part/join will crash us without this
            self.client.refresh(False)

        elif cmd == u"part" or cmd == u"p":
            if self.active_chan.alias == u"r0c-status":
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[error]
  cannot part the status channel
""",
                )
                return

            ac = self.active_chan
            ch_name = "#" + ac.nchan.name if ac.nchan.name else ac.alias
            print("     <-part:  %s  %s" % (ch_name, self.nick))
            self.world.part_chan(self.active_chan)
            # this is in charge of activating the new channel,
            # rapid part/join will crash us without this
            self.client.refresh(False)

        elif cmd.isdigit():
            nch = int(cmd)
            if nch >= len(self.chans):
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[error]
  you only have {0} channels my dude
""".format(
                        len(self.chans)
                    ),
                )
                return

            self.new_active_chan = self.chans[nch]
            self.client.refresh(False, True)

        elif cmd == u"msg" or cmd == u"m":
            if not arg1 or not arg2:
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[invalid arguments]
  usage:     /msg   nickname   your message text
  example:   /msg   ed   hello world
""",
                )
                return

            if not self.world.find_user(arg1):
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[user not found]
  "{0}" is not online
""".format(
                        arg1
                    ),
                )
                return

            print("       /msg:  %s  %s" % (self.nick, arg1))
            uchan = self.world.join_priv_chan(self, arg1)
            self.new_active_chan = uchan
            self.world.send_chan_msg(self.nick, uchan.nchan, arg2)
            self.client.refresh(False, True)

        elif cmd == u"up" or cmd == u"u" or cmd == u"down" or cmd == u"d":
            cli = self.client
            steps = cli.h - 4
            if cli.scroll_i is not None:
                steps = cli.scroll_i
            elif cli.scroll_f is not None:
                steps = int(steps * cli.scroll_f)
            else:
                print("no scroll size?!")

            if cmd == u"up" or cmd == u"u":
                steps *= -1

            cli.scroll_cmd += steps

        elif cmd == u"latest" or cmd == u"l":
            self.active_chan.lock_to_bottom = True
            self.client.need_full_redraw = True
            self.client.refresh(False)

        elif cmd == u"view" or cmd == u"v":
            self.client.view = not self.client.view
            self.client.need_full_redraw = True
            self.client.refresh(False)

        elif cmd == u"redraw" or cmd == u"r":
            if self.client.request_terminal_size("redraw"):
                # returns true if event was scheduled for later
                return

            self.client.need_full_redraw = True
            self.client.refresh(False)

        elif cmd == u"cls" or cmd == u"clear":
            if not self.active_chan.alias and not self.admin:
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[error]
  private channels only
""",
                )
                return

            msg = u"\033[33mchannel wiped by \033[1m{0}".format(self.nick)
            if self.active_chan.alias:
                msg = u""

            self.active_chan.nchan.msgs = []
            self.world.send_chan_msg(u"***", self.active_chan.nchan, msg)

        elif cmd == u"fill":
            if not self.admin_test(cmd, arg):
                return

            try:
                nt = int(arg1)
                _ = u"a" in arg2
            except:
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[error]
  bad syntax
""",
                )
                return

            for n in range(int(arg1)):
                self.world.send_chan_msg(
                    self.nick, self.active_chan.nchan, u"{0} {1}".format(arg2, n)
                )

        elif cmd == u"names" or cmd == u"na":
            self.world.send_chan_msg(
                u"--",
                inf,
                u"{1} users in {0}: {2}".format(
                    self.active_chan.nchan.get_name(),
                    len(self.active_chan.nchan.uchans),
                    u", ".join(
                        sorted([x.user.nick for x in self.active_chan.nchan.uchans])
                    ),
                ),
            )

        elif cmd == u"status" or cmd == u"st":
            n_wizard = sum(1 for x in self.world.users if not x.active_chan)
            n_users = len(self.world.users) - n_wizard
            n_pub = len(self.world.pub_ch)
            n_priv = len(self.world.priv_ch) - n_users

            n_in_chans = 0
            seen_users = {}

            for chan in self.world.pub_ch:
                for user in [x.user for x in chan.uchans]:
                    if user not in seen_users:
                        seen_users[user] = 1
                        n_in_chans += 1

            for chan in self.world.priv_ch:
                if len(chan.uchans) == 1:
                    continue
                for user in [x.user for x in chan.uchans]:
                    if user not in seen_users:
                        seen_users[user] = 1
                        n_in_chans += 1

            self.world.send_chan_msg(
                u"--",
                inf,
                u"{0} users + {1} in wizard, {2} in chans, {3} public + {4} private chans".format(
                    n_users, n_wizard, n_in_chans, n_pub, n_priv
                ),
            )

            if self.admin:
                self.world.send_chan_msg(u"--", inf, u"----- users -----")
                for user in sorted(self.world.users):
                    self.world.send_chan_msg(
                        u"--",
                        inf,
                        u"{0} {1} {2}".format(
                            user.client.adr[0].ljust(15),
                            u"ok " if user.active_chan else u"wiz",
                            user.nick,
                        ),
                    )
                self.world.send_chan_msg(u"--", inf, u"----- chans -----")
                for chan in sorted(self.world.pub_ch):
                    self.world.send_chan_msg(
                        u"--",
                        inf,
                        u"{0}: {1}".format(
                            chan.name,
                            u", ".join(sorted([x.user.nick for x in chan.uchans])),
                        ),
                    )
                self.world.send_chan_msg(u"--", inf, u"-----------------")
            else:
                for n, uch in enumerate(self.chans):
                    nch = uch.nchan
                    if not nch.name:
                        continue

                    t = u"%d users in /%d #%s:  " % (len(nch.uchans), n, nch.name)
                    t += u", ".join(sorted([x.user.nick for x in nch.uchans]))
                    self.world.send_chan_msg(u"--", inf, t)

        elif cmd == u"a":
            activity = {}  # type: dict[int, Chat.UChannel]
            for uchan in self.chans:
                if uchan.hilights and uchan != self.active_chan:
                    activity[uchan.last_ping] = uchan
            for uchan in self.chans:
                if uchan.activity and uchan != self.active_chan:
                    activity[uchan.nchan.msgs[-1].ts] = uchan

            if activity:
                x, uchan = sorted(activity.items())[0]
                self.new_active_chan = uchan
                nchan = uchan.nchan
                for msg in nchan.msgs:
                    if uchan.lock_to_bottom:
                        # skip to end of buffer, users can rely on the
                        # unread-message markers to scroll up if they want
                        break

                    if msg.sno > uchan.last_read:
                        # print('1st unread msg ({0} > {1}) = {2}'.format(
                        # 	msg.sno, uchan.last_read, msg))
                        jump_to = nchan.msgs.index(msg) - 5
                        if jump_to < 0:
                            jump_to = 0
                        uchan.jump_to_msg(jump_to)
                        break
                # print('jumping to activity in {0}'.format(
                # 	self.new_active_chan.nchan.get_name()))

            elif self.old_active_chan:
                ch = self.old_active_chan
                if ch.nchan in self.world.priv_ch or ch.nchan in self.world.pub_ch:
                    self.new_active_chan = ch
                else:
                    self.new_active_chan = self.chans[0]

                # print('jumping to last active, {0}'.format(
                # 	self.new_active_chan.nchan.get_name()))
            else:
                print("cannot jump, no hilights or prev chan")
                return

            if self.new_active_chan not in self.chans:
                t = "/a tried to new_active_chan (%s) not in self.chans (%s |%d|)"
                Util.whoops(t % (self.new_active_chan, self, len(self.chans)))
                self.new_active_chan = self.chans[0]

            self.client.need_full_redraw = True
            self.client.refresh(False)

        elif cmd == u"goto" or cmd == u"g":
            ch = self.active_chan
            nch = self.active_chan.nchan
            if not arg:
                self.world.send_chan_msg(
                    u"--",
                    inf,
                    u"""[goto]
  {1} msgs since {2} in {0}

  command usage:
    /g 19:47             jump to time
    /g 2018-01-21        jump to date
    /g 2018-01-21 19:47  jump to datetime
    /g 3172              jump to message
    /g 34%               jump to offset
    /l                   jump to most recent
""".format(
                        nch.get_name(),
                        len(nch.msgs),
                        nch.msgs[0].dt.strftime("%Y-%m-%d, %H:%M"),
                    ),
                )

            else:
                tfmt = "%Y-%m-%dT%H:%M:%S"

                m = re.match(r"(^[0-9]+)$", arg)
                if m:
                    ch.jump_to_msg(int(m.group(1)))
                    return

                m = re.match(r"(^[0-9\.]+)%$", arg)
                if m:
                    ch.jump_to_msg(int(float(m.group(1)) * len(nch.msgs) / 100.0))
                    return

                m = re.match(r"(^[0-9]{4}-[0-9]{2}-[0-9]{2}) ([0-9]{2}:[0-9]{2})$", arg)
                if m:
                    ht = u"{0}T{1}:00".format(*m.groups())
                    ch.jump_to_time(datetime.strptime(ht, tfmt))
                    return

                m = re.match(r"(^[0-9]{4}-[0-9]{2}-[0-9]{2})$", arg)
                if m:
                    ht = u"{0}T00:00:00".format(m.group(1))
                    ch.jump_to_time(datetime.strptime(ht, tfmt))
                    return

                m = re.match(r"(^[0-9]{2}:[0-9]{2})$", arg)
                if m:
                    ht = u"{0}T{1}:00".format(time.strftime("%Y-%m-%d"), m.group(1))
                    ch.jump_to_time(datetime.strptime(ht, tfmt))
                    return

                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[goto]
  invalid argument format, see /g for help
""",
                )

        elif cmd == u"sw":
            try:
                arg = int(arg)
            except:
                arg = None

            if not arg:
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[invalid arguments]
  usage:     /sw  your_screen_width
  example:   /sw  80
""",
                )
                return

            self.client.w = arg
            self.world.send_chan_msg(
                u"-nfo-", inf, u"screen width: {0} letters".format(self.client.w), False
            )

        elif cmd == u"sh":
            try:
                arg = int(arg)
            except:
                arg = None

            if not arg:
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[invalid arguments]
  usage:     /sh  your_screen_height
  example:   /sh  24
""",
                )
                return

            self.client.h = arg
            self.world.send_chan_msg(
                u"-nfo-",
                inf,
                u"screen height: {0} letters".format(self.client.h),
                False,
            )

        elif cmd == u"ss":
            if arg == u"0":
                arg = u"100%"

            try:
                int_arg = int(arg)
            except:
                int_arg = None

            perc_arg = None
            if arg and arg.endswith(u"%"):
                try:
                    perc_arg = int(arg[:-1])
                except:
                    pass

            if int_arg is not None:
                if int_arg > 9000:
                    self.world.send_chan_msg(u"-err-", inf, u"whoa dude")
                    return

                self.client.scroll_f = None
                self.client.scroll_i = int_arg
                self.world.send_chan_msg(
                    u"-nfo-",
                    inf,
                    u"scroll size: {0} lines".format(self.client.scroll_i),
                    False,
                )

            elif perc_arg is not None:
                if perc_arg > 200:
                    self.world.send_chan_msg(u"-err-", inf, u"whoa dude")
                    return

                self.client.scroll_i = None
                self.client.scroll_f = perc_arg / 100.0
                self.world.send_chan_msg(
                    u"-nfo-",
                    inf,
                    u"scroll size: {0}% of screen".format(self.client.scroll_f * 100),
                    False,
                )

            else:
                self.world.send_chan_msg(
                    u"-err-",
                    inf,
                    u"""[invalid arguments]
  usage:     /ss  lines_scrolled_per_pgup_pgdn
  example:   /ss  0     (entire screen)
  example:   /ss  10    (10 lines)
  example:   /ss  50%   (half the screen)
""",
                )
            return

        elif cmd in (u"b?", u"b0", u"b1", u"b2", u"b3"):
            zi = self.client.bell if cmd == u"b?" else int(cmd[1:])
            if zi == 0:
                t = u"disabled. Enable with /b1 or /b2"
            elif zi == 1:
                t = u"enabled for hilights in other channels. Disable with /b0"
            elif zi == 2:
                t = u"enabled for all hilights, even in active channel. Disable with /b0"
            elif zi == 3:
                t = u"enabled for every message, not just hilights. Disable with /b0"

            self.world.send_chan_msg(u"--", inf, u"Audible alerts %s" % (t,), False)
            if self.client.bell != zi:
                self.client.bell = zi
                self.client.save_config()

        elif cmd == u"ey":
            t = u"Hilight on @all / @everyone enabled. Disable with /en"
            self.client.atall = True
            self.world.send_chan_msg(u"--", inf, t, False)
            self.build_nick_re()
            self.client.save_config()

        elif cmd == u"en":
            t = u"Hilight on @all / @everyone disabled. Enable with /ey"
            self.client.atall = False
            self.world.send_chan_msg(u"--", inf, t, False)
            self.build_nick_re()
            self.client.save_config()

        elif cmd == u"hsy":
            t = u"Hilights/mentions-log in status channel enabled. Disable with /hsn"
            self.client.hilog = True
            self.world.send_chan_msg(u"--", inf, t, False)
            self.client.save_config()

        elif cmd == u"hsn":
            t = u"Hilights/mentions-log in status channel disabled. Enable with /hsy"
            self.client.hilog = False
            self.world.send_chan_msg(u"--", inf, t, False)
            self.client.save_config()

        elif cmd == u"cy":
            self.client.cnicks = True
            self.client.need_full_redraw = True
            self.world.send_chan_msg(
                u"--", inf, u"Colored nicknames enabled. Disable with /cn", False
            )
            self.client.save_config()

        elif cmd == u"cn":
            self.client.cnicks = False
            self.client.need_full_redraw = True
            self.world.send_chan_msg(
                u"--", inf, u"Colored nicknames disabled. Enable with /cy", False
            )
            self.client.save_config()

        elif cmd == u"my":
            self.client.align = True
            self.client.need_full_redraw = True
            self.world.send_chan_msg(
                u"--", inf, u"Wordwrap margin enabled. Disable with /mn", False
            )
            self.client.save_config()

        elif cmd == u"mn":
            self.client.align = False
            self.client.need_full_redraw = True
            self.world.send_chan_msg(
                u"--", inf, u"Wordwrap margin disabled. Enable with /my", False
            )
            self.client.save_config()

        elif cmd == u"sy":
            try:
                arg = int(arg)
            except:
                arg = 1

            if not self.client.slowmo_tx:
                self.world.cserial += 1

            self.client.slowmo_tx = arg
            m = u"Slowmo enabled ({0}). This avoids a bug in telnet.exe on windows, but your memory is probably busted already so you have to reconnect now to fix it. Disable with /sn if you change your mind"
            self.world.send_chan_msg(u"--", inf, m.format(arg), False)
            self.client.save_config()

        elif cmd == u"sn":
            if self.client.slowmo_tx:
                self.client.slowmo_tx = 0
                self.world.cserial += 1

            self.world.send_chan_msg(
                u"--", inf, u"Slowmo disabled. Enable with /sy", False
            )
            self.client.save_config()

        elif cmd == u"cfg":
            m = []
            keys = "slowmo_tx linemode echo_on vt100 crlf codec bell atall cnicks align"
            fmt = u"\033[36m{0}=\033[0m{1!r}" if self.client.vt100 else u"{0}={1!r}"
            for k in keys.split(" "):
                m.append(fmt.format(k, getattr(self.client, k)))

            self.world.send_chan_msg(u"--", inf, u" ".join(m), False)

        elif cmd == u"cmap":
            msg = u"All foreground colours (0 to f) on default background,\n"
            msg += u"each code wrapped in [brackets] for readability:\n  "
            for n in range(16):
                if n == 8:
                    msg += u"\n  \033[1;3{0}m[{1:x}], ".format(n % 8, n)
                else:
                    msg += u"\033[3{0}m[{1:x}], ".format(n % 8, n)

            msg += u"\033[0m\n\nEach background with black text:\n  \033[30m"
            for n in range(8):
                msg += u"\033[4{0}m 0,{0} ".format(n)

            msg += u"\033[0m\n\nEach background with gray text:\n  \033[37m"
            for n in range(8):
                msg += u"\033[4{0}m 7,{0} ".format(n)

            msg += u"\033[0m\n\nEach background with white text:\n  \033[1;37m"
            for n in range(8):
                msg += u"\033[4{0}m f,{0} ".format(n)

            msg += u"\033[0m\n"
            self.world.send_chan_msg(u"-nfo-", inf, msg)

        elif cmd == u"bc":
            if not self.admin_test(cmd, arg):
                return

            self.world.broadcast_message(u"\033[31m{0}".format(arg), 2)

        elif cmd == u"sd":
            if not self.admin_test(cmd, arg):
                return

            msg = u"\033[31mserver shutdown requested by \033[1m{0}".format(self.nick)
            self.world.broadcast_message(msg, 2)

            def delayed_shutdown():
                time.sleep(0.5)
                self.world.core.shutdown()

            Util.Daemon(delayed_shutdown, "shutd")

        elif cmd == u"mem":
            if not self.admin_test(cmd, arg):
                return

            print("memdump started")
            Diag.memory_dump()
            print("memdump done")

        elif cmd == u"repl":
            if not self.admin_test(cmd, arg):
                return

            print("entering repl")
            # code.interact(locals=locals())
            code.InteractiveConsole(locals=globals()).interact()
            print("left repl")

        elif cmd == u"gc":
            if not self.admin_test(cmd, arg):
                return

            gc.collect()

        elif cmd == u"quit" or cmd == u"q" or cmd == u"exit":
            self.client.host.part(self.client)

        else:
            self.world.send_chan_msg(
                u"-err-",
                inf,
                u"""invalid command:  /{0}
  if you meant to send that as a message,
  escape the leading "/" by adding another "/"
""".format(
                    cmd_str
                ),
            )

    def set_nick(self, new_nick):
        if self.lnick in self.world.lusers:
            del self.world.lusers[self.lnick]

        nick_re = u""
        # re.IGNORECASE doesn't work
        # this is dumb
        for ch in re.escape(new_nick):
            if ch not in Util.azAZ:
                nick_re += ch
            else:
                nick_re += u"[{0}{1}]".format(ch.lower(), ch.upper())
                # surprisingly equally fast or faster than haystack.lower()

        self.nick = new_nick
        self.lnick = new_nick.lower()
        self.nick_rep = nick_re
        self.build_nick_re()

        self.nick_len = len(new_nick)
        if self.nick_len > self.client.w * 0.25:
            self.nick_len = int(self.client.w * 0.25)

        self.world.lusers[self.lnick] = self

        if self.active_chan:
            self.client.save_config()

    def build_nick_re(self):
        ptn = self.nick_rep
        if self.client.atall:
            ptn = "(%s|@(all|everyone))" % (ptn,)

        self.nick_re = re.compile("(^|[^a-zA-Z0-9])%s([^a-zA-Z0-9]|$)" % (ptn,))

    def help(self, arg, inf):
        if not arg:
            arg = u"topics"

        txt = None
        if arg == u"intro":
            txt = HELP_INTRO
        else:
            legit_chars = Util.azAZ
            page = u""
            for ch in arg:
                if ch in legit_chars:
                    page += ch
            try:
                with open(EP.doc + "help-{0}.md".format(page), "rb") as f:
                    txt = f.read().decode("utf-8")
            except:
                self.world.send_chan_msg(
                    u"-err-", inf, u"that help page does not exist"
                )
                return

        txt = txt.replace(u"\r", u"")
        txt = txt.replace(u"  \n", u"\n")

        txt = u"\033[0;30;46m{0}\033[K\n\033[0m\n".format(u"=" * 32) + txt

        txt = txt.replace(u"\n\n| | |\n|-|-|\n", u"\n")
        if u"\n| " in txt:
            txt = txt.replace(u"\n| ", u"\n").replace(u" | ", u"  ")
            if txt.startswith(u"| "):
                txt = txt[2:]

        txt = re.sub(r"\*\*`?([^\*`]+)`?\*\*", "\033[1;36m\\1\033[0m", txt)
        txt = re.sub(r"`([^`]+)`", "\033[1;35m\\1\033[0m", txt)
        txt = re.sub(r"\n# ([^\n]*)\n", "\n\033[1;33m=== \\1 ===\033[0m\n", txt)
        txt = txt.replace(u"\n", u"\r\n")

        self.world.send_chan_msg(u"-nfo-", inf, txt)
