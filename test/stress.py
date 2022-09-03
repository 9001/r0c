#!/usr/bin/env python3
# coding: utf-8
from __future__ import print_function

import builtins
import multiprocessing
import threading
import socket
import struct
import signal
import random
import time
import sys
import os

sys.path.insert(1, os.path.join(sys.path[0], ".."))
from r0c import util  # noqa: E402


"""stress.py: retr0chat stress tester"""
__version__ = "0.9"
__author__ = "ed <a@ocv.me>"
__credits__ = ["stackoverflow.com"]
__license__ = "MIT"
__copyright__ = 2018


# config
#

NUM_CLIENTS = 1
NUM_CLIENTS = 512
NUM_PER_MPW = 32

# CHANNELS = ['#1']
CHANNELS = ["#1", "#2", "#3", "#4"]

EVENT_DELAY = 0.01
EVENT_DELAY = 0.005
EVENT_DELAY = 5
# EVENT_DELAY = None

ITERATIONS = 1000000
ITERATIONS = 10000000

IMMEDIATE_TX = True
# IMMEDIATE_TX = False

VISUAL_CLIENT = True
# VISUAL_CLIENT = False

TELNET = False
TELNET = True

#
# config end


try:
    print = __builtin__.print  # noqa: F821
except:
    print = builtins.print

PY2 = sys.version_info[0] == 2

if PY2:
    from Queue import Queue
else:
    from queue import Queue


def get_term_size():
    """
    https://github.com/chrippa/backports.shutil_get_terminal_size
    MIT licensed
    """
    import struct

    try:
        from ctypes import windll, create_string_buffer, WinError

        _handle_ids = {
            0: -10,
            1: -11,
            2: -12,
        }

        def _get_terminal_size(fd):
            handle = windll.kernel32.GetStdHandle(_handle_ids[fd])
            if handle == 0:
                raise OSError("handle cannot be retrieved")
            if handle == -1:
                raise WinError()
            csbi = create_string_buffer(22)
            res = windll.kernel32.GetConsoleScreenBufferInfo(handle, csbi)
            if res:
                res = struct.unpack("hhhhHhhhhhh", csbi.raw)
                left, top, right, bottom = res[5:9]
                columns = right - left + 1
                lines = bottom - top + 1
                return [columns, lines]
            else:
                raise WinError()

    except ImportError:
        import fcntl
        import termios

        def _get_terminal_size(fd):
            try:
                res = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\x00" * 4)
            except IOError as e:
                raise OSError(e)
            lines, columns = struct.unpack("hh", res)

            return [columns, lines]

    try:
        columns = int(os.environ["COLUMNS"])
    except (KeyError, ValueError):
        columns = 0

    try:
        lines = int(os.environ["LINES"])
    except (KeyError, ValueError):
        lines = 0

    # Only query if necessary
    if columns <= 0 or lines <= 0:
        try:
            size = _get_terminal_size(sys.__stdout__.fileno())
        except (NameError, OSError):
            size = [80, 24]

        if columns <= 0:
            columns = size[0]
        if lines <= 0:
            lines = size[1]

    return [columns, lines]


tsz = get_term_size()
tsz[1] -= 1
tszb = struct.pack(">HH", *tsz)
# print(b2hex(tszb))
# sys.exit(0)


class Client(object):
    def __init__(self, core, port, behavior, status_q, n):
        self.core = core
        self.port = port
        self.behavior = behavior
        self.status_q = status_q
        self.n = n
        self.explain = True
        self.explain = False
        self.dead = False
        self.stopping = False
        self.actor_active = False
        self.bootup()

    def bootup(self):
        self.in_text = u""
        self.tx_only = False
        self.outbox = Queue(1000)
        self.backlog = None
        self.num_outbox = 0
        self.num_sent = 0
        self.pkt_sent = 0
        self.stage = "start"
        self.nick = "x"

        self.sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sck.connect(("127.0.0.1", self.port))

        thr = threading.Thread(target=self.actor)
        thr.daemon = True  # for emergency purposes
        thr.start()

        thr = threading.Thread(target=self.rx_loop)
        thr.daemon = True
        thr.start()

        thr = threading.Thread(target=self.tx_loop)
        thr.daemon = True
        thr.start()

    def send_status(self, txt):
        if False:
            print(txt)
        self.status_q.put((self.n, txt))

    def actor(self):
        self.actor_active = True
        print("actor going up")
        while not self.stopping:
            time.sleep(0.02)

            if self.stage == "start":
                self.send_status("start")
                termsize_rsp = b"\xff\xfa\x1f" + tszb + b"\xff\xf0"

                if "verify that your config" in self.in_text:
                    self.txb(termsize_rsp)
                    self.in_text = u""
                    self.tx("n\n")

                if "type the text below, then hit [Enter]:" in self.in_text:
                    self.txb(termsize_rsp)
                    self.stage = "qwer"
                    self.in_text = u""
                    for ch in u"qwer asdf\n":
                        self.tx(ch)
                        time.sleep(0.1)

                continue

            if self.stage == "qwer":
                self.send_status("qwer")
                test_pass = False

                if "your client is stuck in line-buffered mode" in self.in_text:
                    print("WARNING: r0c thinks we are linemode")
                    test_pass = True
                    self.tx(u"a")

                if "text appeared as you typed" in self.in_text:
                    test_pass = True
                    self.tx(u"b")

                if test_pass:
                    self.in_text = u""
                    self.stage = "color"
                continue

            if self.stage == "color":
                self.send_status("color")
                if "does colours work?" in self.in_text:
                    self.stage = "codec"
                    self.in_text = u""
                    self.tx(u"y")
                continue

            if self.stage == "codec":
                self.send_status("codec")
                if "which line looks like" in self.in_text:
                    self.stage = "getnick"
                    self.tx(u"a")
                continue

            if self.stage == "getnick":
                self.send_status("getnick")
                ofs1 = self.in_text.find(u"H\033[0;36m")
                ofs2 = self.in_text.find(u">\033[0m ")
                if ofs1 >= 0 and ofs2 == ofs1 + 8 + 6:
                    if not TELNET:
                        # print('sending vt100 termsize\n'*100)
                        self.tx(u"\033[{1};{0}R".format(*tsz))

                    self.nick = self.in_text[ofs2 - 6 : ofs2]
                    self.in_text = u""
                    self.tx(u"/join {0}\n".format(CHANNELS[0]))
                    self.stage = "ready"

                    self.send_status("{0}:start".format(self.nick))

                    if self.behavior == "flood_single_channel":
                        return self.flood_single_channel()

                    if self.behavior == "jump_channels":
                        return self.jump_channels()

                    if self.behavior == "reconnect_loop":
                        return self.reconnect_loop()

                    if self.behavior == "split_utf8_runes":
                        return self.split_utf8_runes()

                    print("u wot")
                    return

        self.actor_active = False

    def flood_single_channel(self):
        while not self.stopping:
            time.sleep(0.02)

            if self.stage == "ready":
                if "fire/" in self.in_text:
                    self.stage = "main"
                    self.in_Text = u""
                continue

            if self.stage == "main":
                self.stage = "done"
                for n in range(4000):
                    time.sleep(0.01)
                    self.tx(u"{0} {1}\n".format(time.time(), n))
                continue

            if self.stage == "done":
                time.sleep(1)
                self.text = u""  # dont care
                if not self.outbox.empty():
                    continue
                self.tx(u"{0} done\n".format(time.time()))

        self.actor_active = False

    def split_utf8_runes(self):
        charset = u"⢀⣴⣷⣄⠈⠻⡿⠋"
        to_send = charset.encode("utf-8")

        while False:
            # print('tx up')
            for n in range(len(to_send)):
                # print('tx ch')
                self.txb(to_send[n : n + 1])
                time.sleep(0.2)

        self.txb(to_send[0:2])
        to_send = to_send[2:] + to_send[0:2]
        while True:
            for n in range(0, len(to_send), 3):
                self.txb(to_send[n : n + 3])
                time.sleep(0.2)

    def reconnect_loop(self):
        # NOT IMPL, client has no shutdown sequence

        # print('reconnect_loop here')
        channels_avail = CHANNELS
        for chan in channels_avail:
            self.tx(u"/join {0}\n".format(chan))
        time.sleep(1)
        # print('reconnect_loop closing')
        self.close()
        # print('reconnect_loop booting')
        self.bootup()
        # print('reconnect_loop sayonara')

    def expl(self, msg):
        if not self.explain:
            return
        print(msg)
        self.await_continue()

    def await_continue(self):
        self.in_text = u""
        t0 = time.time()
        while not self.stopping and "zxc mkl" not in self.in_text:
            time.sleep(0.1)
            if time.time() - t0 > 10:
                break
        self.in_text = u""

    def jump_channels(self):
        immediate = IMMEDIATE_TX
        delay = EVENT_DELAY
        # print(immediate)
        # sys.exit(0)

        self.tx_only = immediate

        script = []
        active_chan = 0
        member_of = [CHANNELS[0]]
        channels_avail = CHANNELS

        # maps to channels_avail
        msg_id = [0] * len(channels_avail)

        # ---- acts ----
        # next channel
        # join a channel
        # part a channel
        # send a message
        chance = [10, 5, 4, 18]
        chance = [10, 3, 2, 30]
        chance = [10, 30, 2, 130]

        for n in range(len(chance) - 1):
            chance[n + 1] += chance[n]
        print(chance)
        # sys.exit(1)

        odds_next, odds_join, odds_part, odds_send = chance

        for n in range(ITERATIONS):
            if self.stopping:
                break

            if n % 1000 == 0:
                self.send_status("{0}:ev.{1}".format(self.nick, n))
                # self.tx(u'at event {0}\n'.format(n))

            while not self.stopping:
                if not member_of:
                    next_act = 13
                else:
                    next_act = random.randrange(sum(chance))

                if self.explain:
                    print(
                        "in [{0}], active [{1}:{2}], msgid [{3}], next [{4}]".format(
                            ",".join(member_of),
                            active_chan,
                            channels_avail[active_chan],
                            ",".join(str(x) for x in msg_id),
                            next_act,
                        )
                    )

                if next_act <= odds_next:
                    if not member_of:
                        self.expl("tried to jump channel but we are all alone ;_;")
                        continue

                    changed_from_i = active_chan
                    changed_from_t = member_of[active_chan]

                    active_chan += 1
                    script.append(b"\x18")
                    if active_chan >= len(member_of):
                        # we do not consider the status channel
                        script.append(b"\x18")
                        active_chan = 0

                    changed_to_i = active_chan
                    changed_to_t = member_of[active_chan]

                    if self.explain:
                        self.expl(
                            "switching to next channel from {0} to {1} ({2} to {3})".format(
                                changed_from_i,
                                changed_to_i,
                                changed_from_t,
                                changed_to_t,
                            )
                        )
                        for act in script:
                            self.txb(act)
                        self.txb(b"hello\n")
                        self.await_continue()
                        script = []
                    break

                if next_act <= odds_join:
                    if len(member_of) == len(channels_avail):
                        self.expl(
                            "tried to join channel but filled {0} of {1} possible".format(
                                len(member_of), len(channels_avail)
                            )
                        )
                        # out of channels to join, try a different act
                        continue
                    while True:
                        to_join = random.choice(channels_avail)
                        if to_join not in member_of:
                            break
                    member_of.append(to_join)
                    active_chan = len(member_of) - 1
                    self.expl(
                        "going to join {0}:{1}, moving from {2}:{3}".format(
                            len(member_of), to_join, active_chan, member_of[active_chan]
                        )
                    )

                    script.append(u"/join {0}\n".format(to_join).encode("utf-8"))

                    if self.explain:
                        for act in script:
                            self.txb(act)
                        self.txb(b"hello\n")
                        self.await_continue()
                        script = []
                    break

                if next_act <= odds_part:
                    # continue
                    if not member_of:
                        self.expl("tried to leave channel but theres nothing to leave")
                        # out of channels to part, try a different act
                        continue
                    to_part = random.choice(member_of)
                    chan_idx = member_of.index(to_part)
                    self.expl(
                        "gonna leave {0}:{1}, we are in {2}:{3}".format(
                            chan_idx, to_part, active_chan, member_of[active_chan]
                        )
                    )
                    # jump to the channel to part from
                    while active_chan != chan_idx:
                        self.expl(
                            "jumping over from {0} to {1}".format(
                                active_chan, active_chan + 1
                            )
                        )
                        active_chan += 1
                        script.append(b"\x18")
                        if active_chan >= len(member_of):
                            self.expl("wraparound; dodging the status chan")
                            # we do not consider the status channel
                            script.append(b"\x18")
                            active_chan = 0
                    if active_chan == len(member_of) - 1:
                        self.expl(
                            "we are at the end of the channel list, decreasing int"
                        )
                        del member_of[active_chan]
                        active_chan -= 1
                    else:
                        self.expl(
                            "we are not at the end of the channel list, keeping it"
                        )
                        del member_of[active_chan]
                    if member_of:
                        self.expl(
                            "we will end up in {0}:{1}".format(
                                active_chan, member_of[active_chan]
                            )
                        )
                    else:
                        self.expl("we have now left all our channels")

                    script.append(b"/part\n")

                    if self.explain:
                        for act in script:
                            self.txb(act)
                        self.txb(b"hello\n")
                        self.await_continue()
                        script = []
                    break

                if not member_of:
                    # not in any channels, try a different act
                    continue
                chan_name = member_of[active_chan]
                chan_idx = channels_avail.index(chan_name)
                msg_id[chan_idx] += 1
                self.expl(
                    "gonna talk to {0}:{1}, msg #{2}".format(
                        chan_idx, chan_name, msg_id[chan_idx]
                    )
                )

                script.append(
                    u"{0} {1} {2}\n".format(chan_name, msg_id[chan_idx], n).encode(
                        "utf-8"
                    )
                )

                if self.explain:
                    for act in script:
                        self.txb(act)
                    self.txb(b"hello\n")
                    self.await_continue()
                    script = []

                if immediate:
                    for action in script:
                        self.txb(action)
                        if delay:
                            time.sleep(delay)
                    script = []

                break

        self.tx(u"q\n")

        while not self.stopping:
            if "fire/" in self.in_text:
                break
            time.sleep(0.01)

        self.tx_only = True

        for n, ev in enumerate(script):
            if self.stopping:
                break

            if n % 100 == 0:
                print("at event {0}\n".format(n))

            self.txb(ev)
            if delay:
                time.sleep(delay)

        self.tx(u"done")
        print("done")

        self.actor_active = False

    def tx(self, bv):
        self.txb(bv.encode("utf-8"))

    def txb(self, bv):
        self.num_outbox += len(bv)
        self.outbox.put(bv)

    def tx_loop(self):
        while True:
            self.handle_write()

    def rx_loop(self):
        while not self.dead:
            self.handle_read()

    def handle_write(self):
        msg = self.backlog
        if not msg:
            msg = self.outbox.get()
        sent = self.sck.send(msg)
        self.backlog = msg[sent:]
        self.num_sent += sent
        self.pkt_sent += 1
        if self.pkt_sent % 8192 == 8191:
            # print('outbox {0} sent {1} queue {2}'.format(self.num_outbox, self.num_sent, self.num_outbox - self.num_sent))
            self.send_status(
                "{0}:s{1},q{2}".format(
                    self.nick, self.num_sent, self.num_outbox - self.num_sent
                )
            )

    def handle_read(self):
        if self.dead:
            print("!!! read when dead")
            return

        data = self.sck.recv(8192)
        if not data:
            self.dead = True
            return

        if VISUAL_CLIENT:
            print(data.decode("utf-8", "ignore"))

        if not self.tx_only:
            self.in_text += data.decode("utf-8", "ignore")

        # if self.explain:
        # 	print(self.in_text)


class SubCore(object):
    def __init__(self, port, behavior, cmd_q, stat_q, n1):
        self.cmd_q = cmd_q
        self.stat_q = stat_q
        self.port = port
        self.behavior = behavior
        self.stopped = False
        self.clients = []
        for n2 in range(NUM_PER_MPW):
            n = NUM_PER_MPW * n1 + n2
            c = Client(self, self.port, self.behavior, stat_q, n)
            self.clients.append(c)

    def run(self):
        while self.cmd_q.empty():
            time.sleep(0.2)

        for c in self.clients:
            c.stopping = True

        clean_shutdown = False
        for n in range(40):  # 2sec
            time.sleep(0.05)
            if not next((c for c in self.clients if c.actor_active), None):
                break

        # [c.close() for c in self.clients]
        self.stopped = True
        return clean_shutdown


class Core(object):
    def __init__(self):
        if len(sys.argv) < 2:
            print("need 1 argument:  telnet port")
            sys.exit(1)

        port = int(sys.argv[1])

        self.stopping = False

        signal.signal(signal.SIGINT, self.signal_handler)

        behaviors = ["jump_channels"] * int(NUM_CLIENTS / NUM_PER_MPW)
        # behaviors.append('reconnect_loop')
        # behaviors = ['split_utf8_runes'] * int(NUM_CLIENTS / NUM_PER_MPW)
        self.status = ["na"] * NUM_CLIENTS
        self.procs = []
        for n, behavior in enumerate(behaviors):
            cmd_q = multiprocessing.Queue()
            stat_q = multiprocessing.Queue()
            mproc = multiprocessing.Process(
                target=self.new_subcore, args=(cmd_q, stat_q)
            )
            cmd_q.put(port)
            cmd_q.put(behavior)
            cmd_q.put(n)
            mproc.start()
            self.procs.append((mproc, cmd_q, stat_q))

            t = threading.Thread(target=self.get_status, args=(stat_q,))
            t.daemon = True
            t.start()

    def get_status(self, stat_q):
        while True:
            n, st = stat_q.get()
            self.status[n] = st

    def new_subcore(self, cmd_q, stat_q):
        subcore = SubCore(cmd_q.get(), cmd_q.get(), cmd_q, stat_q, cmd_q.get())
        subcore.run()
        cmd_q.get()

    def print_status(self):
        msg = u""
        for st in self.status:
            msg += u"{0}, ".format(st)
        print(msg)

    def run(self):
        print("  *  test is running")

        print_status = not VISUAL_CLIENT

        while not self.stopping:
            for n in range(5):
                time.sleep(0.1)
                if self.stopping:
                    break
            if print_status:
                self.print_status()

        [x[1].put("x") for x in self.procs]
        time.sleep(1)
        for mpw in self.procs:
            mpw[0].terminate()

        print("  *  test ended")

    def shutdown(self):
        self.stopping = True

    def signal_handler(self, signal, frame):
        self.shutdown()


if __name__ == "__main__":
    core = Core()
    core.run()

# cat log | grep -E ' adding msg ' | awk '{printf "%.3f\n", $1-v; v=$1}' | sed -r 's/\.//;s/^0*//;s/^$/0/' | awk 'BEGIN {sum=0} $1<10000 {sum=sum+$1} NR%10==0 {v=sum/32; sum=0; printf "%" v "s\n", "" }' | tr ' ' '#'
