# coding: utf-8
from __future__ import print_function
from .__init__ import TYPE_CHECKING
from . import util as Util

import time
import socket
import threading

print = Util.print
whoops = Util.whoops

if TYPE_CHECKING:
    from .world import World


class IRC_Net(object):
    def __init__(self, world, netname, host, port, tls, nick, uname, pwd):
        # type: (World, str, str, int, bool, str, str, str) -> None
        self.world = world
        self.netname = netname
        self.host = host
        self.port = port
        self.tls = tls
        self.nick = nick
        self.uname = uname
        self.pwd = pwd

        self.ar = world.ar
        self.sck = None
        self.backlog = b""
        self.nick_suf = 0
        self.generation = 0
        self.cnick = ""
        self.chans = {}  # type: dict[str, IRC_Chan]
        self.msg_q = []
        self.hist = []
        self.mutex = threading.Lock()

    def tx(self, msg):
        if self.ar.dbg_irc:
            for ln in msg.split("\r\n"):
                print("\033[90mirc <%s [%s]\033[0m" % (self.host, ln))
        try:
            self.sck.sendall((msg + "\r\n").encode("utf-8", "replace"))
        except:
            t = "XXX lost connection to irc during write: %s"
            print(t % (msg,))

    def say(self, msg):
        with self.mutex:
            if self._enqueue_msg(msg):
                return
        self.tx(msg)

    def _say(self, msg):
        if not self._enqueue_msg(msg):
            self.tx(msg)

    def _enqueue_msg(self, msg):
        if self._is_rate_limited():
            self.msg_q.append(msg)
            return True
        self._tick_ratelimit()

    def _is_rate_limited(self):
        if len(self.hist) < self.ar.i_rate_b:
            return False

        now = time.time()
        return (
            now - self.hist[0] < self.ar.i_rate_s * self.ar.i_rate_b
            and now - self.hist[-1] < self.ar.i_rate_s
        )

    def _tick_ratelimit(self):
        self.hist.append(time.time())
        while len(self.hist) > self.ar.i_rate_b:
            self.hist.pop(0)

    def addchan(self, irc_cname, r0c_cname):
        # type: (str, str) -> None
        self.world.join_pub_chan(None, r0c_cname)
        nch = self.world.get_pub_chan(r0c_cname)

        ichan = IRC_Chan(self, irc_cname, r0c_cname)
        self.chans[irc_cname] = ichan
        self.world.ircb[nch] = ichan
        nch.ircb.append(ichan)

    def destroy(self):
        self.nick = ""
        self.sck.close()

    def connect(self):
        Util.Daemon(self._connect, "irc_c_%s" % (self.host,))

    def _connect(self):
        n = 0
        while True:
            try:
                self._connect_once()
                if n:
                    t = "finally connected to irc<%s> after %d failed attempts (nice)"
                    print(t % (self.host, n))
                return
            except Exception as ex:
                n += 1
                t = "XXX connecting irc<%s> failed (attempt %d): %s"
                print(t % (self.host, n, ex))
                time.sleep(5)

    def _connect_once(self):
        if not self.nick:
            t = "XXX irc connection to %s disabled due to critical error"
            print(t % (self.host,))
            return

        with self.mutex:
            self.generation += 1

        sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sck.connect((self.host, int(self.port)))
        if self.tls:
            import ssl

            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            sck = ctx.wrap_socket(sck)

        self.sck = sck
        self.nick_suf = 0
        self.cnick = self.nick
        Util.Daemon(self._main, "ircm_%s" % (self.host,))
        Util.Daemon(self._recv, "ircr_%s" % (self.host,))

    def _main(self):
        generation = self.generation
        t = "NICK {0}\r\nUSER {0} {0} {1} :{0}"
        self.tx(t.format(self.nick, self.host))
        while True:
            time.sleep(1)
            with self.mutex:
                if generation != self.generation:
                    break

                while self.msg_q and not self._is_rate_limited():
                    self._tick_ratelimit()
                    self.tx(self.msg_q.pop(0))

                for ch in self.chans.values():
                    if ch.joined:
                        continue

                    t = "JOIN #%s" % (ch.irc_cname,)
                    if t not in self.msg_q:
                        self._say(t)

    def _recv(self):
        sck = self.sck
        generation = self.generation
        while generation == self.generation:
            bmsg = sck.recv(4096)
            if not bmsg:
                print("XXX lost connection to irc")
                with self.mutex:
                    self.generation += 1

                time.sleep(2)
                Util.Daemon(self._connect, "irc_re_%s" % (self.host,))
                return

            bmsg = self.backlog + bmsg
            if bmsg.endswith(b"\n"):
                self.backlog = b""
            else:
                ofs = bmsg.rfind(b"\n")
                self.backlog = bmsg[ofs + 1 :]
                bmsg = bmsg[:ofs]
                if not bmsg:
                    return

            msg = bmsg.decode("utf-8", "replace")
            for ln in msg.rstrip("\r\n").split("\n"):
                ln = ln.rstrip("\r")
                self.handle_msg(ln)

    def handle_msg(self, msg):
        if self.ar.dbg_irc:
            print("\033[90mirc %s> [%s]\033[0m" % (self.host, msg))

        mw = msg.split(" ", 3)

        if mw[0] == "PING":
            self.tx("PO" + msg[2:])
            return

        if len(mw) < 3:
            return

        if mw[1] in ("JOIN", "PART"):
            nick = mw[0].split("!")[0].split(":")[-1]
            ch_name = mw[2][1:].lower()
            if ch_name not in self.chans or nick == self.cnick:
                return

            print("irc<%s #%s> %s [%s]" % (self.host, ch_name, mw[1], nick))
            try:
                nch = self.world.get_pub_chan(self.chans[ch_name].r0c_cname)
                t = u"irc: \033[1;32m%s\033[22m has %sed" % (nick, mw[1].lower())
                if len(mw) > 3:
                    t += " (%s)" % (mw[3][1:])

                self.world.send_chan_msg(u"--", nch, t, False)
            except:
                whoops()

        if len(mw) < 4:
            return

        if mw[1] == "PRIVMSG":
            nick = mw[0].split("!")[0].split(":")[-1]
            if mw[3] == ":\x01VERSION\x01":  # ctcp required by rizon
                self.say("NOTICE %s :\x01VERSION %s\x01" % (nick, self.ar.ctcp_ver))
                return

            ch_name = mw[2][1:].lower()
            if ch_name not in self.chans:
                t = "XXX msg from chan [%s] not in %s ???"
                print(t % (ch_name, list(self.chans)))
                return

            txt = mw[3][1:]
            txt = Util.convert_color_codes(Util.color_from_irc(txt))
            print("irc<%s #%s> [%s] %s\033[0m" % (self.host, ch_name, nick, txt))
            try:
                nch = self.world.get_pub_chan(self.chans[ch_name].r0c_cname)
                self.world.send_chan_msg(nick, nch, txt, False)
            except:
                whoops()

            return

        mw = msg.split(" ")
        if len(mw) < 5:
            return

        sc = mw[1]

        if sc in ("331", "366") and mw[3].startswith("#"):
            ch_name = mw[3][1:].lower()
            if ch_name in self.chans:
                self.chans[ch_name].joined = True
            else:
                t = "XXX joined chan [%s] not in %s ???"
                print(t % (ch_name, list(self.chans)))
            return

        if sc == "433":
            self.nick_suf += 1
            if self.nick_suf > 5:
                print("XXX all nicks taken")
                self.destroy()
                return

            self.cnick = "%s%s" % (self.nick, self.nick_suf)
            self.tx("NICK {0}\r\nUSER {0} {0} {1} :{0}".format(self.cnick, self.host))
            return

        if sc == "464":
            if self.pwd:
                self.tx("PASS %s:%s" % (self.uname, self.pwd))
            else:
                print("XXX irc server requires a password to connect")
                self.destroy()
            return


class IRC_Chan(object):
    def __init__(self, net, irc_cname, r0c_cname):
        # type: (IRC_Net, str, str) -> None
        self.net = net
        self.irc_cname = irc_cname
        self.r0c_cname = r0c_cname

        self.joined = False
