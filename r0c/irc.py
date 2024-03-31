# coding: utf-8
from __future__ import print_function
from .__init__ import TYPE_CHECKING
from . import chat as Chat
from . import util as Util
from . import user as User

import time
import socket

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
        self.chans = {}  # type: dict[str, IRC_Chan]

    def say(self, msg):
        try:
            self.sck.sendall((msg + "\r\n").encode("utf-8", "replace"))
        except:
            t = "XXX lost connection to irc during write: %s"
            print(t % (msg,))

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
        while True:
            try:
                self._connect_once()
                return
            except Exception as ex:
                print("XXX connecting irc<%s> failed: %s" % (self.host, ex))
                time.sleep(5)

    def _connect_once(self):
        if not self.nick:
            t = "XXX irc connection to %s disabled due to critical error"
            print(t % (self.host,))
            return

        self.generation += 1
        sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sck.connect((self.host, int(self.port)))
        if self.tls:
            import ssl

            ctx = ssl.create_default_context()
            ctx.verify_mode = ssl.CERT_NONE
            sck = ctx.wrap_socket(sck)

        self.sck = sck
        self.nick_suf = 0
        Util.Daemon(self._main, "ircm_%s" % (self.host,))
        Util.Daemon(self._recv, "ircr_%s" % (self.host,))

    def _main(self):
        generation = self.generation
        t = "NICK {0}\r\nUSER {0} {0} {1} :{0}"
        self.say(t.format(self.nick, self.host))
        while True:
            time.sleep(1)
            if generation != self.generation:
                break

            for ch in self.chans.values():
                if ch.joined:
                    continue

                self.say("JOIN #%s" % (ch.irc_cname,))

    def _recv(self):
        sck = self.sck
        generation = self.generation
        while generation == self.generation:
            bmsg = sck.recv(4096)
            if not bmsg:
                print("XXX lost connection to irc")
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
            print("\033[90mirc<%s> [%s]\033[0m" % (self.host, msg))

        mw = msg.split(" ", 3)
        if len(mw) < 4:
            return

        if mw[1] == "PRIVMSG":
            nick = mw[0].split("!")[0].split(":")[-1]
            ch_name = mw[2][1:]
            if ch_name not in self.chans:
                t = "XXX msg from chan [%s] not in %s ???"
                print(t % (ch_name, list(self.chans)))
                return

            txt = mw[3][1:]
            print("irc<%s #%s> [%s] %s" % (self.host, ch_name, nick, txt))
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
            ch_name = mw[3][1:]
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

            t = "NICK {0}{1}\r\nUSER {0} {0} {2} :{0}"
            self.say(t.format(self.nick, self.nick_suf, self.host))
            return

        if sc == "464":
            if self.pwd:
                self.say("PASS %s:%s" % (self.uname, self.pwd))
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
