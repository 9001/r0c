# coding: utf-8
from __future__ import print_function
from .__init__ import EP, PY2, INTERP, TYPE_CHECKING
from . import util as Util
from . import chat as Chat
from .util import t2ymd_hm, t2ymd_hms

import os
import re
import time
import threading
from datetime import datetime

if PY2:
    from Queue import Queue
else:
    from queue import Queue

if TYPE_CHECKING:
    from . import __main__ as Main
    from . import user as User
    from .chat import NChannel, UChannel
    from .irc import IRC_Chan, IRC_Net

print = Util.print
UTC = Util.UTC


class World(object):
    def __init__(self, core):
        # type: (Main.Core) -> World
        self.core = core
        self.ar = core.ar
        self.users = []  # User instances
        self.lusers = {}  # lowercase hashmap
        self.pub_ch = []  # NChannel instances (public)
        self.priv_ch = []  # NChannel instances (private)
        self.dirty_ch = {}  # Channels that have pending tx
        self.cntab = {}  # nick color cache
        self.cserial = 0  # selector configuration serial number
        self.task_queue = Queue()  # Delayed processing of expensive tasks
        self.mutex = threading.RLock()
        self.dirty_flag = threading.Event()  # raise after setting dirty_ch
        self.last_dirty = 0  # scheduler hint
        Util.py26_threading_event_wait(self.dirty_flag)

        # irc bridges
        self.ircn = {}  # type: dict[str, IRC_Net]  # netname:ircnet
        self.ircb = {}  # type: dict[NChannel, IRC_Chan]

        # config
        self.messages_per_log_file = self.ar.rot_msg

        # stats for benchmarking
        self.num_joins = 0
        self.num_parts = 0
        self.num_messages = 0

        threading.Thread(target=self.refresh_chans, name="tx_chan").start()

    def shutdown(self):
        with self.mutex:
            for chanlist in [self.pub_ch, self.priv_ch]:
                ucs = [y for x in chanlist for y in x.uchans]
                ucs = [x for x in ucs if x.alias != u"r0c-status"]
                for uc in ucs:
                    self.part_chan(uc, True)

    def add_user(self, user):
        with self.mutex:
            self.users.append(user)
            if user.lnick:
                self.lusers[user.lnick] = user

    def find_user(self, nick):
        with self.mutex:
            return self.lusers.get(nick.lower(), None)

    def refresh_chans(self):
        while not self.core.shutdown_flag.is_set():
            # no latency unless multiple messages within 0.05 sec
            time.sleep(0.05)

            self.dirty_flag.wait()
            with self.mutex:
                self.dirty_flag.clear()
                if not self.dirty_ch:
                    # raised with no pending work; maybe shutdown signal
                    continue

                self.last_dirty = time.time()
                dirty_ch = list(self.dirty_ch)
                self.dirty_ch = {}

                for chan in dirty_ch:
                    self.refresh_chan(chan)

        print("  *  terminated refresh_chans")

    def refresh_chan(self, nchan):
        if not nchan.uchans:
            # all users left since this channel got scheduled for refresh
            return

        last_msg = nchan.msgs[-1].sno if nchan.msgs else 0

        upd_users = set()  # users with clients to repaint

        for uchan in nchan.uchans:
            if uchan.update_activity_flags(False, last_msg):
                # update status bar immediately
                if uchan.user.active_chan != uchan:
                    upd_users.add(uchan.user)

            if uchan.user.active_chan == uchan:
                if (
                    not uchan.user.client.handshake_sz
                    or uchan.user.client.wizard_stage is not None
                ):
                    continue

                # print('refreshing {0} for {1}'.format(nchan.get_name(), uchan.user.nick))
                upd_users.add(uchan.user)

        for user in upd_users:
            user.client.refresh(False)

    def send_chan_msg(self, from_nick, nchan, text, ping_self=True):
        # type: (str, NChannel, str, bool) -> None
        max_hist_mem = self.ar.hist_mem
        msg_trunc_size = self.ar.hist_tsz
        with self.mutex:
            self.num_messages += 1
            if nchan.name is None and not from_nick.startswith(u"-"):
                # private chan, check if we have anyone to send to
                if len(nchan.uchans) == 1:
                    if nchan.uchans[0].alias == u"r0c-status":
                        if nchan.uchans[0].user.nick == from_nick:
                            self.send_chan_msg(
                                u"-err-",
                                nchan,
                                u"this buffer does not accept messages, only commands\n",
                            )
                            return

                    else:
                        # private chat without the other user added yet;
                        # pull in the other user
                        utarget = None
                        target = nchan.uchans[0].alias
                        if target != from_nick:
                            utarget = self.find_user(target)
                            if utarget is None:
                                self.send_chan_msg(
                                    u"-err-",
                                    nchan,
                                    u'\033[1;31mfailed to locate user "{0}"'.format(
                                        nchan.uchans[0].alias
                                    ),
                                )
                                return

                            self.join_chan_obj(utarget, nchan, from_nick)
                            self.start_logging(nchan)
                            # fallthrough to send message

            now = time.time()
            msg = Chat.Message(nchan, now, from_nick, text)
            nchan.msgs.append(msg)
            nchan.latest = msg.ts

            if not from_nick.startswith(u"-") and not from_nick == u"***":
                if len(nchan.user_act_ts) > 9000:
                    nchan.user_act_ts = {}
                nchan.user_act_ts[from_nick] = now
                nchan.update_usernames()

            if len(nchan.msgs) > max_hist_mem:
                new_len = len(nchan.msgs) - msg_trunc_size
                print(
                    " hist trunc:  [{0}] from {1} to {2}".format(
                        nchan.get_name(), len(nchan.msgs), new_len
                    )
                )
                while new_len > max_hist_mem:
                    print("\033[1;31!!!\033[0m")
                    new_len -= msg_trunc_size
                nchan.msgs = nchan.msgs[msg_trunc_size:]

            # self.refresh_chan(nchan)
            for uchan in nchan.uchans:
                if nchan.name and not uchan.user.nick_re.search(text):
                    continue

                if PY2 and INTERP != "IronPython":
                    if isinstance(uchan.user.nick, str):
                        Util.whoops("uchan.user.nick is bytestring")
                    if isinstance(from_nick, str):
                        Util.whoops("from_nick is bytestring")

                if uchan.alias != u"r0c-status" and uchan.user.nick != from_nick:
                    uchan.last_ping = msg.sno
                    if uchan.user.client.hilog and nchan.name:
                        inf = self.get_priv_chan(uchan.user, u"r0c-status").nchan
                        t = "you were mentioned in \033[1m#%s:\033[0m <%s> %s"
                        t = t % (nchan.name, msg.user, msg.txt)
                        self.send_chan_msg(u"-nfo-", inf, t, False)
                elif ping_self:
                    uchan.last_ping = msg.sno

            if nchan not in self.dirty_ch:
                self.dirty_ch[nchan] = 1
                self.dirty_flag.set()

            if nchan.log_fh:
                # print('logrotate counter at {0}'.format(nchan.log_ctr))
                if nchan.log_ctr >= self.messages_per_log_file:
                    self.start_logging(nchan)

                ltxt = u"%s %s %s\n" % (
                    hex(int(msg.ts * 8.0))[2:].rstrip("L"),
                    msg.user,
                    msg.txt,
                )
                nchan.log_fh.write(ltxt.encode("utf-8"))
                nchan.log_ctr += 1

    def join_chan_obj(self, user, nchan, alias=None):
        # type: (User.User, Chat.NChannel, str) -> Chat.UChannel
        with self.mutex:
            # print('{0} users in {1}, {2} messages; {3} is in {4} channels'.format(
            # 	len(nchan.uchans), nchan.get_name(), len(nchan.msgs), user.nick, len(user.chans)))

            for uchan in user.chans:
                if uchan.nchan == nchan:
                    return uchan

            self.num_joins += 1
            uchan = Chat.UChannel(user, nchan, alias)
            user.chans.append(uchan)
            nchan.uchans.append(uchan)
            if len(nchan.user_act_ts) > 9000:
                nchan.user_act_ts = {}
            nchan.user_act_ts[user.nick] = time.time()
            nchan.update_usernames()
            self.send_chan_msg(
                u"--",
                nchan,
                u"\033[1;32m{0}\033[22m has joined".format(user.nick),
                False,
            )
            if not alias:
                uchan.last_read = -1

            return uchan

    def get_pub_chan(self, name):
        # type: (str) -> NChannel
        for ch in self.pub_ch:
            if ch.name == name:
                return ch
        return None

    def get_priv_chan(self, user, alias):
        # type: (User.User, str) -> UChannel
        for ch in user.chans:
            if ch.alias == alias:
                return ch
        return None

    def join_pub_chan(self, user, name):
        # type: (User.User, str) -> Optional[UChannel]
        with self.mutex:
            name = name.strip().lower()
            nchan = self.get_pub_chan(name)
            if nchan is None:
                st = t2ymd_hms(datetime.now(UTC), "%04d-%02d-%02d, %02d:%02d:%02dZ")
                nchan = Chat.NChannel(
                    name, u"#{0} - no topic has been set".format(name)
                )
                nchan.msgs.append(
                    Chat.Message(
                        nchan,
                        time.time(),
                        u"--",
                        u"\033[36mchannel created at \033[1m%s" % (st,),
                    )
                )
                if nchan.name != u"scrolltest":
                    self.load_chat_log(nchan)
                    # self.task_queue.put([self.load_chat_log, [nchan], {}])
                else:
                    for n1 in range(10):
                        txt = u""
                        for n2 in range(10):
                            txt += u"{0}{1}".format(n1, n2) * 20 + u" "

                        msg = Chat.Message(nchan, time.time(), u"--", txt)
                        nchan.msgs.append(msg)

                    txt = u"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa " * 6
                    msg = Chat.Message(nchan, time.time(), u"--", txt)
                    nchan.msgs.append(msg)

                self.pub_ch.append(nchan)

            if not user:
                nchan.immortal = True
                return None

            ret = self.join_chan_obj(user, nchan)
            user.new_active_chan = ret
            if user.client.hilog:
                hls = []
                nmsg = 0
                ptn = user.nick_re
                for msg in reversed(nchan.msgs):
                    if len(hls) >= 50 or nmsg > 9000:
                        break

                    nmsg += 1
                    if ptn.search(msg.txt):
                        hls.append(msg)

                inf = self.get_priv_chan(user, u"r0c-status").nchan
                tf = "%d %ss ago (%s) you were mentioned in \033[1m#%s:\033[0m <%s> %s"
                for msg in reversed(hls):
                    dt = t2ymd_hm(msg.dt, "%04d-%02d-%02d %02d:%02d")
                    td = int(time.time() - msg.ts)
                    if td >= 172800:
                        tu = "day"
                        td //= 86400
                    elif td >= 7200:
                        tu = "hour"
                        td //= 3600
                    elif td >= 300:
                        tu = "minute"
                        td //= 60
                    else:
                        tu = "second"

                    t = tf % (td, tu, dt, nchan.name, msg.user, msg.txt)
                    self.send_chan_msg(u"-nfo-", inf, t, False)

            return ret

    def join_priv_chan(self, user, alias):
        with self.mutex:
            uchan = self.get_priv_chan(user, alias)
            if uchan is None:
                nchan = Chat.NChannel(None, u"DM with [[uch_a]]")
                self.priv_ch.append(nchan)
                uchan = self.join_chan_obj(user, nchan, alias)
            return uchan

    """
    def broadcast_banner(self, msg):
        with self.mutex:
            chans = {}
            for user in self.users:
                if user.active_chan and user.active_chan.nchan not in chans:
                    chans[user.active_chan.nchan] = 1

            if not msg:
                for nchan in chans:
                    if nchan.topic_bak is not None:
                        nchan.topic = nchan.topic_bak
                        nchan.topic_bak = None
                for user in self.users:
                    if user.active_chan:
                        user.client.refresh(False)
            else:
                for nchan in chans:
                    if nchan.topic_bak is None:
                        nchan.topic_bak = nchan.topic
                    nchan.topic = msg

                # print('broadcast: {0}'.format(msg))
                for user in self.users:
                    if user.active_chan:
                        # print('         : {0} ->'.format(user))
                        to_send = u"\033[H{0}\033[K".format(msg)
                        user.client.screen[0] = to_send
                        user.client.say(
                            to_send.encode(user.client.codec, "backslashreplace")
                        )
    """

    def broadcast_message(self, msg, severity=1):
        """1=append, 2=append+scroll"""
        with self.mutex:
            msg = Util.convert_color_codes(msg, False)

            for nchan in self.pub_ch + self.priv_ch:
                self.send_chan_msg(u"-!-", nchan, msg)

            if severity > 1:
                for user in self.users:
                    if user.active_chan:
                        if not user.active_chan.lock_to_bottom:
                            user.active_chan.lock_to_bottom = True
                            user.client.need_full_redraw = True
                    else:
                        user.client.say(
                            u"\n [[ broadcast message ]]\n {0}\n".format(msg)
                            .replace(u"\n", u"\r\n")
                            .encode("utf-8")
                        )

    def part_chan(self, uchan, quiet=False):
        # type: (Chat.UChannel, bool) -> None
        with self.mutex:
            self.num_parts += 1
            user = uchan.user
            nchan = uchan.nchan
            i = None
            if user.active_chan == uchan:
                i = user.chans.index(uchan)
            user.chans.remove(uchan)
            nchan.uchans.remove(uchan)

            try:
                nchan.user_act_ts.pop(user.nick, None)
                nchan.update_usernames()
            except:
                pass

            if i:
                if len(user.chans) <= i:
                    i -= 1
                user.new_active_chan = user.chans[i]

            if not quiet:
                suf = u""
                if not nchan.name:
                    suf = u"; reinvite by typing another msg here"

                self.send_chan_msg(
                    u"--",
                    nchan,
                    u"\033[1;33m{0}\033[22m has left{1}".format(user.nick, suf),
                )

            if not nchan.uchans and not nchan.immortal:
                print(" close chan:  [{0}]".format(nchan.get_name()))

                if nchan.log_fh:
                    nchan.log_fh.close()

                ch_list = self.pub_ch
                if not nchan.name:
                    ch_list = self.priv_ch

                ch_list.remove(nchan)

    def load_chat_log(self, nchan):
        if not nchan:
            return

        # print('  chan hist:  scanning files')
        t1 = time.time()

        log_dir = u"{0}chan/{1}".format(EP.log, nchan.name)
        try:
            os.makedirs(log_dir)
        except:
            pass

        if PY2:
            # os.walk stats all files (bad over nfs)
            files = os.listdir(log_dir.encode("utf-8"))
        else:
            files = []
            for (dirpath, dirnames, filenames) in os.walk(log_dir):
                files.extend(filenames)
                break

        re_chk = re.compile("^[0-9]{4}-[0-9]{4}-[0-9]{6}-*$")

        # total_size = 0
        # for fn in sorted(files):
        # 	total_size += os.path.getsize(
        # 		'{0}/{1}'.format(log_dir, fn))
        #
        # do_broadcast = (total_size > 1024*1024)
        # if do_broadcast:
        # 	self.broadcast_banner(u'\033[1;37;45m [ LOADING CHATLOG ] \033[0;42m')
        # 	# daily dose

        # print('  chan hist:  reading files')
        ln = u"???"
        t2 = time.time()
        chunks = [nchan.msgs]
        n_left = self.ar.hist_rd - len(nchan.msgs)
        bytes_loaded = 0
        try:
            for fn in sorted(files, reverse=True):
                if not re_chk.match(fn):
                    # unexpected file in log folder, skip it
                    continue

                chunk = []
                with open("{0}/{1}".format(log_dir, fn), "rb") as f:
                    f.readline()  # discard version info
                    for ln in f:
                        ts, user, txt = ln.decode("utf-8").rstrip(u"\n").split(u" ", 2)

                        chunk.append(Chat.Message(None, int(ts, 16) / 8.0, user, txt))

                    bytes_loaded += f.tell()

                # if chunk:
                # 	chunk.append(Message(None, int(ts, 16)/8.0, '--', \
                # 		'\033[36mend of log file "{0}"'.format(fn)))

                if len(chunk) > n_left:
                    chunk = chunk[-n_left:]

                chunks.append(chunk)
                n_left -= len(chunk)
                if n_left <= 0:
                    break
        except:
            Util.whoops(ln)

        # print('  chan hist:  merging {0} chunks'.format(len(chunks)))
        nchan.msgs = []
        for chunk in reversed(chunks):
            # print('\nadding {0} messages:\n  {1}'.format(
            # 	len(chunk), '\n  '.join(str(x) for x in chunk)))
            nchan.msgs.extend(chunk)

        # print('  chan hist:  setting {0} serials'.format(len(nchan.msgs)))
        for n, msg in enumerate(nchan.msgs):
            msg.sno = n

        t3 = time.time()
        print(
            "  chan hist:  {0} msgs, {1:.0f} kB, {2:.2f} + {3:.2f} sec, #{4}".format(
                self.ar.hist_rd - n_left,
                bytes_loaded / 1024.0,
                t2 - t1,
                t3 - t2,
                nchan.name,
            )
        )

        # if do_broadcast:
        # 	self.broadcast_banner(None)

        # if nchan.name != 'xst':
        self.start_logging(nchan, chunks[0])

    def start_logging(self, nchan, chat_backlog=None):
        if nchan.name is not None:
            log_dir = u"{0}chan/{1}".format(EP.log, Util.sanitize_fn(nchan.name))
        else:
            log_dir = u"{0}pm/{1}".format(
                EP.log, u"/".join([Util.sanitize_fn(x.user.nick) for x in nchan.uchans])
            )

        if nchan.log_fh:
            nchan.log_fh.close()

        # always mkdir because direction can turn on reconnect
        try:
            os.makedirs(log_dir)
        except:
            if not os.path.isdir(log_dir):
                raise

        ts = t2ymd_hms(datetime.now(UTC), "%04d-%02d%02d-%02d%02d%02d")
        log_fn = u"{0}/{1}".format(log_dir, ts)

        while os.path.isfile(log_fn):
            log_fn += u"-"

        nchan.log_ctr = 0
        nchan.log_fh = open(log_fn, "wb")
        nchan.log_fh.write(u"1 {0:x}\n".format(int(time.time())).encode("utf-8"))

        # print('opened log file {0}'.format(log_fn))

        if chat_backlog:
            # print('appending backlog ({0} messages)'.format(len(chat_backlog)))
            for msg in chat_backlog:
                ltxt = u"%s %s %s\n" % (
                    hex(int(msg.ts * 8.0))[2:].rstrip("L"),
                    msg.user,
                    msg.txt,
                )
                nchan.log_fh.write(ltxt.encode("utf-8"))
                nchan.log_ctr += 1

            # potential chance that a render goes through
            # before the async job processor kicks in
            self.dirty_ch[nchan] = 1
            self.dirty_flag.set()
            for uchan in nchan.uchans:
                uchan.user.client.need_full_redraw = True
