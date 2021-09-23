# coding: utf-8
from __future__ import print_function
from .__init__ import EP, PY2, INTERP
from . import util as Util
from . import chat as Chat

import os
import re
import time
import threading
from datetime import datetime

if PY2:
    from Queue import Queue
else:
    from queue import Queue

print = Util.print


class World(object):
    def __init__(self, core):
        self.core = core
        self.ar = core.ar
        self.users = []  # User instances
        self.pub_ch = []  # NChannel instances (public)
        self.priv_ch = []  # NChannel instances (private)
        self.dirty_ch = {}  # Channels that have pending tx
        self.cntab = {}  # nick color cache
        self.cserial = 0  # selector configuration serial number
        self.task_queue = Queue()  # Delayed processing of expensive tasks
        self.mutex = threading.RLock()
        self.dirty_flag = threading.Event()  # raise after setting dirty_ch
        Util.py26_threading_event_wait(self.dirty_flag)

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

    def find_user(self, nick):
        with self.mutex:
            nick = nick.lower()
            for usr in self.users:
                if usr.nick and usr.nick.lower() == nick:
                    return usr
            return None

    def refresh_chans(self):
        while not self.core.shutdown_flag.is_set():
            # no latency unless multiple messages within 0.05 sec
            time.sleep(0.05)

            self.dirty_flag.wait()
            self.dirty_flag.clear()

            with self.mutex:
                if not self.dirty_ch:
                    # raised with no pending work; maybe shutdown signal
                    continue

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

        for uchan in nchan.uchans:
            uchan.update_activity_flags(False, last_msg)
            if uchan.user.active_chan == uchan:
                if (
                    not uchan.user.client.handshake_sz
                    or uchan.user.client.wizard_stage is not None
                ):
                    continue

                # print('refreshing {0} for {1}'.format(nchan.get_name(), uchan.user.nick))
                uchan.user.client.refresh(False)

    def send_chan_msg(self, from_nick, nchan, text, ping_self=True):
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
                nchan.user_act_ts[from_nick] = now

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
                if nchan.name is None or uchan.user.nick_re.search(text):
                    # if len(nchan.uchans) == 1:
                    # 	break
                    if PY2 and INTERP != "IronPython":
                        if isinstance(uchan.user.nick, str):
                            Util.whoops("uchan.user.nick is bytestring")
                        if isinstance(from_nick, str):
                            Util.whoops("from_nick is bytestring")

                    if uchan.alias == u"r0c-status":
                        if ping_self:
                            uchan.last_ping = msg.sno
                    else:
                        if ping_self or uchan.user.nick != from_nick:
                            uchan.last_ping = msg.sno

            if nchan not in self.dirty_ch:
                self.dirty_ch[nchan] = 1
                self.dirty_flag.set()

            if nchan.log_fh:
                # print('logrotate counter at {0}'.format(nchan.log_ctr))
                if nchan.log_ctr >= self.messages_per_log_file:
                    self.start_logging(nchan)

                nchan.log_ctr += 1
                nchan.log_fh.write(
                    (
                        u" ".join(
                            [hex(int(msg.ts * 8.0))[2:].rstrip("L"), msg.user, msg.txt]
                        )
                        + u"\n"
                    ).encode("utf-8")
                )

    def join_chan_obj(self, user, nchan, alias=None):
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
            nchan.user_act_ts[user.nick] = time.time()
            self.send_chan_msg(
                u"--",
                nchan,
                u"\033[1;32m{0}\033[22m has joined".format(user.nick),
                False,
            )
            uchan.last_read = nchan.msgs[-1].sno
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
            name = name.strip().lower()
            nchan = self.get_pub_chan(name)
            if nchan is None:
                nchan = Chat.NChannel(
                    name, u"#{0} - no topic has been set".format(name)
                )
                nchan.msgs.append(
                    Chat.Message(
                        nchan,
                        time.time(),
                        u"--",
                        u"\033[36mchannel created at \033[1m{0}".format(
                            datetime.utcnow().strftime("%Y-%m-%d, %H:%M:%SZ")
                        ),
                    )
                )
                if nchan.name != "scrolltest":
                    self.load_chat_log(nchan)
                    # self.task_queue.put([self.load_chat_log, [nchan], {}])
                else:
                    for n1 in range(10):
                        txt = u""
                        for n2 in range(10):
                            txt += u"{0}{1}".format(n1, n2) * 20 + " "

                        msg = Chat.Message(nchan, time.time(), u"--", txt)
                        nchan.msgs.append(msg)

                    txt = u"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa " * 6
                    msg = Chat.Message(nchan, time.time(), u"--", txt)
                    nchan.msgs.append(msg)

                self.pub_ch.append(nchan)

            ret = self.join_chan_obj(user, nchan)
            user.new_active_chan = ret
            return ret

    def join_priv_chan(self, user, alias):
        with self.mutex:
            uchan = self.get_priv_chan(user, alias)
            if uchan is None:
                nchan = Chat.NChannel(None, u"DM with [[uch_a]]")
                self.priv_ch.append(nchan)
                uchan = self.join_chan_obj(user, nchan)
                uchan.alias = alias
            return uchan

    def broadcast_banner(self, msg):
        with self.mutex:
            chans = {}
            for user in self.users:
                if user.active_chan and user.active_chan.nchan not in chans:
                    chans[user.active_chan.nchan] = 1

            if not msg:
                for nchan in chans:
                    if hasattr(nchan, "topic_bak"):
                        nchan.topic = nchan.topic_bak
                        del nchan.topic_bak
                for user in self.users:
                    if user.active_chan:
                        user.client.refresh(False)
            else:
                for nchan in chans:
                    if not hasattr(nchan, "topic_bak"):
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

    def broadcast_message(self, msg, severity=1):
        """1=append, 2=append+scroll"""
        with self.mutex:
            for nchan in self.pub_ch:
                self.send_chan_msg(u"--", nchan, msg)

            for nchan in self.priv_ch:
                self.send_chan_msg(u"--", nchan, msg)

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
                del nchan.user_act_ts[user.nick]
            except:
                pass

            if i:
                if len(user.chans) <= i:
                    i -= 1
                user.new_active_chan = user.chans[i]

            if not quiet:
                self.send_chan_msg(
                    u"--", nchan, u"\033[1;33m{0}\033[22m has left".format(user.nick)
                )

            if not nchan.uchans:
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
        # 	self.broadcast_banner('\033[1;37;45m [ LOADING CHATLOG ] \033[0;42m')
        # 	# daily dose

        # print('  chan hist:  reading files')
        ln = u"???"
        t2 = time.time()
        chunks = [nchan.msgs]
        n_left = self.ar.hist_rd - len(nchan.msgs)
        bytes_loaded = 0
        try:
            for fn in reversed(sorted(files)):
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
            "  chan hist:  {0} msgs, {1:.0f} kB, {2:.2f} + {3:.2f} sec, #{5}".format(
                self.ar.hist_rd - n_left,
                bytes_loaded / 1024.0,
                t2 - t1,
                t3 - t2,
                t3 - t1,
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

        ts = datetime.utcnow().strftime("%Y-%m%d-%H%M%S")
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
                nchan.log_ctr += 1
                nchan.log_fh.write(
                    (
                        u" ".join(
                            [hex(int(msg.ts * 8.0))[2:].rstrip("L"), msg.user, msg.txt]
                        )
                        + u"\n"
                    ).encode("utf-8")
                )

            # potential chance that a render goes through
            # before the async job processor kicks in
            self.dirty_ch[nchan] = 1
            self.dirty_flag.set()
            for uchan in nchan.uchans:
                uchan.user.client.need_full_redraw = True
