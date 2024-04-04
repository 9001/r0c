# coding: utf-8
from __future__ import print_function
from .__init__ import EP, PY2, COLORS, IRONPY, TYPE_CHECKING, WINDOWS, unicode
from . import util as Util
from . import chat as Chat
from . import user as User
from .util import t2hms

import os
import re
import time
import zlib
import socket
import threading
import binascii
from datetime import datetime
import operator

print = Util.print
UTC = Util.UTC

# dont try-import ssl; avoids crash on systems with broken openssl libs
ssl = None


if PY2:
    from Queue import Queue
else:
    from queue import Queue


if TYPE_CHECKING:
    from . import world as World
    from . import user as User
    from .chat import Message, NChannel, UChannel


class VT100_Server(object):
    def __init__(self, host, port, world, other_if, tls):
        global ssl
        if tls:
            import importlib

            ssl = importlib.import_module("ssl")

        self.ar = world.ar
        self.other_if = other_if
        self.world = world
        self.tls = tls
        self.clients = []
        self.user_config = {}
        self.user_config_path = None
        self.user_config_changed = False
        self.re_bot = re.compile(
            "root|Admin|admin|default|support|user|password|telnet|"
            + "guest|operator|supervisor|daemon|service|enable|system|"
            + "[Mm]anage|baby|netman|tele[kc]om|volition|davox|sysadm|"
            + "tech|888888|666666|mg3500|merlin|nmspw|super|setup|vizxv|"
            + "HTTP/1|222222|xxyyzz|synnet|PlcmSpIp|Glo|e8ehome|xc3511|"
            + "taZz@|aquario|1001chin|Oxhlw|S2fGq|Zte521|ttnet|tlJwp|"
            + "t0tal|gpon|anko|changeme|hi3518|antslq|juantech|zlxx|"
            + "xmhdipc|ipcam|cat10|synnet|ezdvr|vstarcam|klv123|"
            + "ubnt|hunt57|Alphanet|epicrout|annie20|realtek|netscreen"
            + "|telco|ftp|oracle|[Cc]isco|backdoor|Huawei|MIRAI|TABLE"
            + "|rapport|mother|hikvision|vodafon|tutor|rewt|private"
            + "|patrol|mediator|nokia|letmein|friday|install|OutOfBox"
            + "|GDE|EDG|SNNU|ECGG|ECGN|DFG[BC]|toor|busybox"
            + "|e8ehome|ruijie|keomeo|draytek|secret|qmik|ximo|Intra"
        )
        self.scheduled_kicks = []
        self.next_scheduled_kick = None

        self.ep = (host, port)
        self.srv_sck = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if not WINDOWS or self.ar.reuseaddr:
            self.srv_sck.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.srv_sck.bind(self.ep)
            self.srv_sck.listen(1)
        except:
            print("\nERROR: failed to listen on", host, "port", port)
            try:
                if port < 1024 and os.geteuid():
                    t = "ports below 1024 cannot be used without root, so try a higher port"
                    print(t)
            except:
                pass
            raise

        if IRONPY:
            self.__eq__ = self.ipy__eq__
            self.__ne__ = self.ipy__ne__

    def ipy__eq__(self, other):
        return id(self) == id(other)

    def ipy__ne__(self, other):
        return id(self) != id(other)

    def gen_remote(self, sck, addr, usr):
        if sck:
            raise RuntimeError("inherit me")

    def handle_error(self):
        Util.whoops()

    def handle_accept(self):
        with self.world.mutex:

            # https://github.com/9001/r0c/issues/1
            #    self.addr becomes None when a client disconnects,
            #    and socket.getpeername()[0] will raise exceptions
            #
            # smoke test:
            # yes 127.0.0.1 | nmap -v -iL - -Pn -sT -p 2323,1531 -T 5

            try:
                sck, addr = self.srv_sck.accept()
                adr = [addr[0], addr[1]]
                if len(sck.getpeername()[0]) < 3:
                    raise Exception
            except:
                print("[!] handshake error (probably a port scanner)")
                return

            if self.tls:
                try:
                    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                    if self.ar.ciphers:
                        ctx.set_ciphers(self.ar.ciphers)

                    minver = self.ar.tls_min
                    if minver == "TLSv1_0":
                        minver = "TLSv1"

                    if minver:
                        names = "SSLv3 TLSv1 TLSv1_1 TLSv1_2 TLSv1_3".split(" ")
                        if minver not in names:
                            err = "unknown TLS version {0}, only know {1}"
                            raise Exception(err.format(minver, names))

                        try:
                            en = False
                            for name in names:
                                bit = getattr(ssl, "OP_NO_" + name)
                                if minver == name:
                                    en = True
                                if en:
                                    ctx.options &= ~bit
                                else:
                                    ctx.options |= bit
                        except Exception as ex:
                            print("[*] failed to apply --tls-min: " + str(ex))

                        if hasattr(ctx, "minimum_version"):
                            ctx.minimum_version = getattr(ssl.TLSVersion, minver)

                    ctx.load_cert_chain(EP.app + "cert.pem")
                    sck = ctx.wrap_socket(sck, server_side=True)
                except Exception as ex:
                    print("[*] TLS client: " + str(ex))
                    print(
                        "  `- if you want to support old/insecure clients (centos6, powershell) please run r0c with argument --old-tls"
                    )
                    return

            usr = User.User(self.world, adr)
            remote = self.gen_remote(sck, adr, usr)
            self.world.add_user(usr)
            self.clients.append(remote)
            self.world.cserial += 1
            remote.conf_wizard(0)

            kick_msg = " wizardkick:  {0}  {1}".format(remote.user.nick, remote.adr[0])
            self.schedule_kick(remote, 600, kick_msg)

            print(
                "client join:  {0}  {2}  {3}  {1}".format(
                    remote.user.nick, len(self.clients), *list(remote.adr)
                )
            )

    def part(self, remote, announce=True):
        # TODO should probably set this inside the lock? check if that's safe
        remote.dead = True

        with self.world.mutex:
            # Util.whoops("client part")
            Util.Daemon(Util.close_sck, "sclose", (remote.sck,))

            if announce:
                print(
                    "client part:  {0}  {2}  {3}  {1}".format(
                        remote.user.nick, len(self.clients) - 1, *list(remote.adr)
                    )
                )
            self.clients.remove(remote)
            self.world.cserial += 1
            try:
                remote.user.active_chan = None
                remote.user.old_active_chan = None
                remote.user.new_active_chan = None
            except:
                pass
            for uchan in list(remote.user.chans):
                self.world.part_chan(uchan)
            if remote.user and remote.user in self.world.users:
                self.world.users.remove(remote.user)
                if remote.user.lnick in self.world.lusers:
                    del self.world.lusers[remote.user.lnick]
            if remote.wire_log is not None:
                remote.wire_log.write(
                    unicode(int(time.time() * 1000)).encode("utf-8") + b"\n"
                )
                remote.wire_log.close()

    def schedule_kick(self, remote, timeout, msg=None):
        timeout += time.time()
        self.scheduled_kicks.append([timeout, remote, msg])
        if self.next_scheduled_kick is None or self.next_scheduled_kick > timeout:
            self.next_scheduled_kick = timeout

    def unschedule_kick(self, remote):
        self.scheduled_kicks = [x for x in self.scheduled_kicks if x[1] != remote]

    def load_configs(self):
        name = ("TLS-" if self.tls else "") + self.__class__.__name__
        with self.world.mutex:
            if not self.user_config_path:
                raise RuntimeError("inheritance bug: self.user_config_path not set")

            self.user_config = {}
            self.user_config_changed = False
            if not os.path.isfile(self.user_config_path):
                print("  *    {0} knows 0 clients".format(name))
                return

            panic = False
            with open(self.user_config_path, "rb") as f:
                f.readline()  # discard version info
                try:
                    for ln in [x.decode("utf-8").strip() for x in f]:
                        k, v = ln.split(u" ", 1)
                        self.user_config[k] = v
                except:
                    print(" /!\\ invalid config line")
                    try:
                        print(ln)
                    except:
                        pass

            if panic:
                raise RuntimeError("see above")

            print("  *    {0} knows {1} clients".format(name, len(self.user_config)))

    def save_configs(self):
        with self.world.mutex:
            if not self.user_config_changed:
                return

            self.user_config_changed = False
            with open(self.user_config_path, "wb") as f:
                f.write(b"1\n")
                for k, v in sorted(self.user_config.items()):
                    f.write((u" ".join([k, v]) + u"\n").encode("utf-8"))

            print(
                "  *  {0} saved {1} client configs".format(
                    self.__class__.__name__, len(self.user_config)
                )
            )


class VT100_Client(object):
    def __init__(self, host, sck, address, world, usr):
        # type: (VT100_Server, socket.socket, tuple[str, int], World.World, User.User) -> VT100_Client
        self.ar = world.ar
        self.host = host
        self.sck = sck
        self.adr = address
        self.world = world
        self.user = usr
        self.dead = False  # set true at disconnect
        self.is_bot = False

        # config; values are dontcare, default_config will overwrite
        self.m_refresh = 6
        self.slowmo_tx = 0
        self.y_input = 0
        self.y_status = 1
        self.linemode = False
        self.echo_on = False
        self.vt100 = True
        self.cnicks = False
        self.align = True
        self.view = False
        self.bell = 1
        self.atall = True
        self.hilog = True
        self.crlf = u"\n"
        self.bps = 0
        self.codec = "utf-8"
        self.multibyte_codec = True
        self.inband_will_fail_decode = True

        self.wire_log = None
        if self.ar.log_rx or self.ar.log_tx:
            log_fn = "{0}wire/{1}_{2}_{3}".format(
                EP.log, int(time.time()), *list(self.adr)
            )

            while os.path.isfile(log_fn):
                log_fn += "_"

            self.wire_log = open(log_fn, "wb")
            self.wire_log.write(
                unicode(int(time.time() * 1000)).encode("utf-8") + b"\n"
            )

        self.uee_offset = 0
        try:
            x = b"\xfe"
            x.decode("utf-8")
        except UnicodeDecodeError as uee:
            self.uee_offset = -uee.start

        # outgoing data
        self.outbox = []
        self.replies = []
        self.last_tx = None

        # incoming data
        self.backlog = b""
        self.in_bytes = b""
        self.in_text = u""
        self.in_text_full = u""
        self.num_telnet_negotiations = 0
        self.slowmo_tx = 0
        self.slowmo_skips = 0  # remaining cycles to skip
        self.set_codec("utf-8")

        # incoming requests
        self.scroll_cmd = 0
        self.scroll_i = None
        self.scroll_f = 1

        # input buffer
        self.linebuf = u""
        self.linepos = 0
        self.lineview = 0
        self.msg_hist = []
        self.msg_hist_n = None
        self.msg_not_from_hist = False
        self.left_chrome = u""

        # tabcomplete registers
        self.tc_nicks = None
        self.tc_msg_pre = None
        self.tc_msg_post = None

        # state registers
        self.wizard_stage = "start"
        self.wizard_lastlen = 0
        self.wizard_maxdelta = 0
        self.wizard_mindelta = 9001
        self.iface_confirmed = False
        self.handshake_sz = False
        self.handshake_world = False
        self.last_2smol = 0
        self.last_beep = 0
        self.show_hilight_tutorial = True
        self.need_full_redraw = False
        self.too_small = False
        self.screen = []
        self.w = 80
        self.h = 24
        self.first_dsr = 0.0
        self.pending_size_request = 0.0
        self.size_request_action = None
        self.re_cursor_pos = re.compile(r"\033\[([0-9]{1,4});([0-9]{1,4})R")

        self.msg_too_small = [
            u"your screen is too small",
            u"screen is too small",
            u"screen too small",
            u"screen 2 small",
            u"scrn 2 small",
            u"too small",
            u"2 small",
            u"2 smol",
            u"2smol",
            u":(",
        ]

        self.codec_map = [
            "utf-8",
            0,
            "cp437",
            0,
            "shift_jis",
            0,
            "latin1",
            1,
            "ascii",
            2,
        ]
        self.codec_uni = [u"├┐ ┌┬┐ ┌ ", u"Ð Ñ Ã ", u"all the above are messed up "]
        self.codec_asc = [u"hmr", u"DNA", u"n/a"]

        self.read_markers = set("cl cr cu cd home end bs tab".split())

        self.esc_tab = {}
        self.add_esc(u"\x1b\x5bD", "cl")
        self.add_esc(u"\x1b\x5bC", "cr")
        self.add_esc(u"\x1b\x5bA", "cu")
        self.add_esc(u"\x1b\x5bB", "cd")
        self.add_esc(u"\x1b\x5b\x31\x7e", "home")
        self.add_esc(u"\x1b\x5b\x34\x7e", "end")
        self.add_esc(u"\x1b\x5b\x35\x7e", "pgup")
        self.add_esc(u"\x1b\x5b\x36\x7e", "pgdn")
        self.add_esc(u"\x08", "bs")
        self.add_esc(u"\x09", "tab")
        self.add_esc(u"\x0d\x0a", "ret")
        self.add_esc(u"\x0d\x00", "ret")

        # inetutils-1.9.4
        self.add_esc(u"\x7f", "bs")  # this is DEL on windows-telnet
        self.add_esc(u"\x1b\x4f\x48", "home")
        self.add_esc(u"\x1b\x4f\x46", "end")

        # debian 9.3
        self.add_esc(u"\x1b\x5b\x48", "home")
        self.add_esc(u"\x1b\x5b\x46", "end")

        # putty
        self.add_esc(u"\x1b\x5b\x33\x7e", "del")

        # hotkeys
        self.add_esc(u"\x0c", "redraw")  # ^L (readline-compat)
        self.add_esc(u"\x12", "redraw")  # ^R
        self.add_esc(u"\x0e", "view")  # ^N
        self.add_esc(u"\x01", "prev-chan")  # ^A
        self.add_esc(u"\x18", "next-chan")  # ^X
        self.add_esc(u"\x05", "alt-tab")  # ^E

        Util.Daemon(self.handshake_timeout, "hs_to")

        if IRONPY:
            self.__eq__ = self.ipy__eq__
            self.__ne__ = self.ipy__ne__

    def ipy__eq__(self, other):
        return id(self) == id(other)

    def ipy__ne__(self, other):
        return id(self) != id(other)

    def default_config(self):
        self.m_refresh = 6  # refresh interval, 1..6
        self.slowmo_tx = 0
        self.y_input = 0  # offset from bottom of screen
        self.y_status = 1  # offset from bottom of screen
        self.linemode = False  # set true by buggy clients
        self.echo_on = False  # set true by buffy clients
        self.vt100 = True  # set nope by butty clients
        self.cnicks = False  # colored nicknames
        self.align = True  # fixed left margin
        self.bell = 1  # doot on hilights in other channels
        self.atall = not self.ar.no_all  # hilight on @all / @everyone
        self.hilog = True  # hilights/mentions log in status chan
        self.crlf = u"\n"  # return key
        self.bps = 0  # will autodetect
        self.set_codec("utf-8")

    def load_config(self):
        load_ok = False
        with self.world.mutex:
            self.default_config()
            self.user.client = self
            self.user.admin = self.adr[0] == "127.0.0.1" and not self.ar.ara

            try:
                if self.adr[0] in self.ar.proxy:
                    raise Exception()

                (
                    ts,
                    nick,
                    slowmo,
                    linemode,
                    vt100,
                    echo_on,
                    crlf,
                    codec,
                    bell,
                    atall,
                    hilog,
                    cnicks,
                    align,
                ) = self.host.user_config[self.adr[0]].split(u" ")

                # print('],['.join([nick,linemode,vt100,echo_on,codec,bell]))

                # terminal behavior
                self.slowmo_tx = int(slowmo)
                self.linemode = 1 == int(linemode)
                self.vt100 = 1 == int(vt100)
                self.echo_on = 1 == int(echo_on)
                self.crlf = binascii.unhexlify(crlf).decode("utf-8")
                self.set_codec(codec)

                # user config
                self.bell = int(bell)
                self.atall = 1 == int(atall)
                self.hilog = 1 == int(hilog)
                self.cnicks = 1 == int(cnicks)
                self.align = 1 == int(align)

                if not self.world.find_user(nick):
                    self.user.set_nick(nick)

                load_ok = True

            except:
                self.default_config()

            if self.echo_on:
                # if echo enabled, swap status and input:
                # that way the screen won't scroll on enter
                self.y_input = 1
                self.y_status = 0

            if not self.user.nick:
                self.user.set_rand_nick()

        return load_ok

    def save_config(self):
        with self.world.mutex:
            conf_str = u" ".join(
                [
                    hex(int(time.time() * 8.0))[2:].rstrip("L"),
                    self.user.nick,
                    # terminal behavior
                    unicode(self.slowmo_tx),
                    u"1" if self.linemode else u"0",
                    u"1" if self.vt100 else u"0",
                    u"1" if self.echo_on else u"0",
                    binascii.hexlify(self.crlf.encode("utf-8")).decode("utf-8"),
                    self.codec,
                    # user config
                    unicode(self.bell),
                    u"1" if self.atall else u"0",
                    u"1" if self.hilog else u"0",
                    u"1" if self.cnicks else u"0",
                    u"1" if self.align else u"0",
                ]
            )

            try:
                if self.host.user_config[self.adr[0]] == conf_str:
                    return
            except:
                pass

            self.host.user_config[self.adr[0]] = conf_str
            self.host.user_config_changed = True

            if self.echo_on:
                self.y_input = 1
                self.y_status = 0

    def set_codec(self, codec_name):
        multibyte = ["utf-8", "shift_jis"]
        ff_illegal = ["utf-8", "shift_jis"]
        self.codec = codec_name
        self.multibyte_codec = self.codec in multibyte
        self.inband_will_fail_decode = self.codec in ff_illegal

    def reassign_retkey(self, crlf):
        etab = self.esc_tab.iteritems if PY2 else self.esc_tab.items
        drop = []
        for key, value in etab():
            if value == "ret" and key != u"\x0d\x00":
                # \x0d \x00 gets special treatment because
                # putty sends it for pastes but not keystrokes
                # and it's unique enough to not cause any issues
                drop.append(key)
        for key in drop:
            del self.esc_tab[key]
        self.crlf = crlf
        self.esc_tab[self.crlf] = "ret"

    def determine_retkey(self, verify_only=False):
        nline = b"\x0d\x0a\x00"
        btext = self.in_text.encode("utf-8")
        nonl = btext.rstrip(nline)
        if nonl == btext:
            return None

        # asked for 2x Enter; verify
        nl = btext[len(nonl) :][-4:]
        i = len(nl) // 2
        nl2 = nl[i:]
        nl = nl[:i]
        if nl != nl2:
            return None

        crlf = nl.decode("utf-8")
        if verify_only:
            return self.crlf == crlf

        self.reassign_retkey(crlf)
        t = "client crlf:  {0}  {1}  {2}"
        print(t.format(self.user.nick, self.adr[0], Util.b2hex(nl)))
        return len(nonl)

    def set_term_size(self, w, h):
        self.w = w
        self.h = h
        if self.ar.dbg:
            print("terminal sz:  {0}x{1}".format(self.w, self.h))

        if self.w >= 512:
            print("screen width {0} reduced to 80".format(self.w))
            self.w = 80
        if self.h >= 512:
            print("screen height {0} reduced to 24".format(self.h))
            self.h = 24

        self.user.nick_len = len(self.user.nick)
        if self.user.nick_len > self.w * 0.25:
            self.user.nick_len = int(self.w * 0.25)

        self.handshake_sz = True

    def handshake_timeout(self):
        if self.ar.dbg:
            print("handshake_sz  init")

        time.sleep(1)

        if self.ar.dbg:
            if self.handshake_sz:
                print("handshake_sz  ok")
            else:
                print("handshake_sz  timeout")

        self.handshake_sz = True

    def add_esc(self, key, act):
        hist = u""
        for c in key:
            hist += c
            if hist == key:
                break
            if hist in self.esc_tab and self.esc_tab[hist]:
                raise RuntimeError(
                    "partial escape code [{0}] matching fully defined escape code for [{1}]".format(
                        Util.b2hex(hist), act
                    )
                )
            self.esc_tab[hist] = False
        if key in self.esc_tab and self.esc_tab[key] != act:
            raise RuntimeError(
                "fully defined escape code [{0}] for [{1}] matches other escape code for [{2}]".format(
                    Util.b2hex(key), act, self.esc_tab[key]
                )
            )
        self.esc_tab[key] = act

    def request_terminal_size(self, scheduled_task=None):
        if not self.vt100:
            return False  # can't be helped

        self.pending_size_request = time.time()
        self.size_request_action = scheduled_task
        req = b"\033[s\033[999;999H\033[6n\033[u"
        if not self.bps and not self.linemode:
            # req+req adds 20 bytes between each dsr;
            req += (b"\033[0m" * 30) + req  # 1120 bits
        self.say(req)
        if self.linemode:
            self.say(
                b"\033[H\033[J\r\n   *** please press ENTER  (due to linemode) ***\r\n\r\n   "
            )
        return True

    def say(self, message):
        self.outbox.append(message)

    def readable(self):
        return not self.dead

    def writable(self):
        # if not self.replies.empty() or self.backlog:
        # 	print('REPLY!!')
        # else:
        # 	print('@' if self.backlog or not self.replies.empty() or not self.outbox.empty() else '.', end='')
        # 	sys.stdout.flush()

        # if self.slowmo_tx:
        # 	#print('x')
        # 	now = time.time()
        # 	if self.last_tx is not None and now - self.last_tx < 0.01:
        # 		return False
        # 	#print('ooo')

        # looks like we might end up here after all,
        # TODO: safeguard against similar issues (thanks asyncore)
        try:
            return not self.dead and (self.backlog or self.replies or self.outbox)
        except:
            # terrible print-once guard
            try:
                self.crash_case_1 += 1
            except:
                self.crash_case_1 = 1
                Util.whoops()
            if not self.dead:
                self.host.part(self)

    def handle_close(self):
        if not self.dead:
            self.host.part(self)

    def handle_error(self):
        Util.whoops()
        if not self.dead:
            self.host.part(self)

    def handle_write(self):
        if not self.writable():
            return

        msg = self.backlog
        self.backlog = b""

        for src in [self.replies, self.outbox]:
            while len(msg) < 480 and src:
                msg += src.pop(0)

        if self.ar.hex_tx:
            if len(msg) < self.ar.hex_lim:
                Util.hexdump(msg, "<<--")
            else:
                print("<<--       :  [{0} byte]".format(len(msg)))

        if self.wire_log and self.ar.log_tx:
            self.wire_log.write(
                unicode(int(time.time() * 1000)).encode("utf-8") + b"\n"
            )
            Util.hexdump(msg, "<", self.wire_log)

        if self.slowmo_tx:
            end_pos = next(
                (
                    i
                    for i, ch in enumerate(msg)
                    if i >= 510 or (i > 480 and ch in [b" "[0], b"\033"[0]])
                ),
                len(msg),
            )
            self.backlog = msg[end_pos:]
            sent = self.sck.send(msg[:end_pos])
            self.backlog = msg[sent:]
            self.slowmo_skips = self.slowmo_tx
            # hexdump(msg[:sent])
            # print('@@@ sent = {0}    backlog = {1}'.format(sent, len(self.backlog)))
        else:
            sent = self.sck.send(msg)
            self.backlog = msg[sent:]
            # print('@@@ sent = {0}    backlog = {1}'.format(sent, len(self.backlog)))

    def refresh(self, cursor_moved, mark_read=False):
        """compose necessary ansi text and send to client"""
        with self.world.mutex:
            if (
                self.too_small
                or not self.handshake_sz
                or not self.handshake_world
                or self.wizard_stage is not None
            ):
                return

            if self.dead:
                Util.whoops("refreshing dead client #wow #whoa")
                try:
                    print("*** i am {0}".format(self.adr))
                except:
                    pass
                try:
                    print("*** i am [{0}]".format(self.user.nick))
                except:
                    pass
                if self in self.host.clients:
                    print("*** dead client still in host.clients")

                    def delayed_drop():
                        time.sleep(5)
                        if self in self.host.clients:
                            print("*** dead client STILL in host.clients, removing")
                            self.host.clients.remove(self)
                            self.world.cserial += 1
                        else:
                            print("*** its fine")

                    Util.Daemon(delayed_drop, "dropcli")

                return

            if not self.user:
                Util.whoops("how did you get here without a user?")
                return

            if not self.user.active_chan and not self.user.new_active_chan:
                Util.whoops(
                    "how did you get here without a chan? {0} {1}".format(
                        self.user.active_chan, self.user.new_active_chan
                    )
                )
                return

            # full redraw if requested by anything stateful
            full_redraw = self.need_full_redraw
            self.need_full_redraw = False

            # full redraw if the screen buffer has been invalidated
            if not self.screen or len(self.screen) != self.h:
                full_redraw = True

            status_changed = False  # set true to force status bar update
            scroll_performed = False  # scroll events might affect status bar

            # switch to new channel,
            # storing the last viewed message for notification purposes
            if self.user.new_active_chan:
                usr = self.user
                if usr.new_active_chan not in usr.chans:
                    t = "new_active_chan (%s) not in user.chans (%s |%d|)"
                    Util.whoops(t % (usr.new_active_chan, usr, len(usr.chans)))
                    usr.new_active_chan = usr.chans[0]

                if self.user.active_chan:
                    self.user.active_chan.update_activity_flags(True)

                # print("         /w:  %s  %s" % (usr.active_chan, usr.new_active_chan))

                if usr.active_chan in usr.chans:
                    usr.old_active_chan = usr.active_chan
                else:
                    usr.old_active_chan = None

                self.user.active_chan = self.user.new_active_chan
                self.user.active_chan.update_activity_flags(True)
                self.user.new_active_chan = None
                full_redraw = True

            # check if user input has caused any unread messages
            # in the active channel to be considered read
            # (check linepos/linebuf to not trigger on CR after /join)
            elif mark_read or (cursor_moved and (self.linepos or self.linebuf)):
                status_changed = self.user.active_chan.update_activity_flags(True)

            if self.scroll_cmd:
                # we don't know which messages will be displayed yet,
                # schedule a recheck after message processing
                scroll_performed = True

            to_send = u""
            fix_color = False

            # invalidate screen buffer if full redraw
            if full_redraw:
                self.screen = [u"x"] * self.h
                if not self.vt100:
                    to_send = u"\r\n" * self.h

            mark_messages_read = (
                status_changed and not self.user.active_chan.display_notification
            )

            # update chat view
            to_send += self.update_chat_view(full_redraw, mark_messages_read)
            full_redraw_0 = full_redraw
            if to_send:
                full_redraw = True

            # update_chat_view computes which messages are visible
            # once a scroll has completed, so we have to redo this
            if scroll_performed:
                if self.user.active_chan.update_activity_flags(True):
                    status_changed = True

            if self.vt100:
                # update top bar
                to_send += self.update_top_bar(full_redraw)

                # update status bar
                if (status_changed or not cursor_moved) and (
                    self.bps > 3000 or not to_send or full_redraw_0
                ):
                    to_send += self.update_status_bar(full_redraw)

                # anything sent so far would require an SGR reset
                if to_send:
                    fix_color = True

            else:
                # always clear and resend the status bar for non-vt100
                to_send += self.update_status_bar(True)

            # handle keyboard strokes from non-linemode clients,
            # but redraw text input field for linemode clients
            txi = self.update_text_input(full_redraw or self.echo_on)
            to_send += txi

            # reset colours if necessary
            if u"\033[" in self.linebuf or fix_color:
                to_send += u"\033[0m"

            # position cursor after CLeft/CRight/Home/End
            if (
                self.vt100
                and (to_send or cursor_moved)
                and (
                    not txi
                    or self.bps > 3000
                    or full_redraw
                    or len(self.linebuf) > self.linepos
                )
            ):
                to_send += u"\033[%d;%dH" % (
                    self.h - self.y_input,
                    self.user.nick_len + 2 + self.linepos + 1 - self.lineview,
                )

            # do it
            if to_send:
                self.say(to_send.encode(self.codec, "backslashreplace"))

    def beep(self, min_lvl):
        if self.bell < min_lvl:
            return

        now = time.time()
        if now - self.last_beep < 1:
            return

        self.last_beep = now
        self.say(b"\x07")

    def notify_new_hilight(self, uchan):
        self.beep(2)
        if uchan == self.user.active_chan:
            return

        # print('ping in {0} while in {1}'.format(uchan.nchan.get_name(), self.user.active_chan.nchan.get_name()))

        if len(uchan.nchan.uchans) > 1:
            self.beep(1)

        if self.show_hilight_tutorial:
            self.show_hilight_tutorial = False
            inf_u = self.user.chans[0]
            inf_n = inf_u.nchan

            cause = u""
            if len(uchan.nchan.uchans) > 1:
                ch_name = uchan.nchan.get_name()
                if u" " in ch_name:
                    cause = u"\nsomeone sent you a private message.\n".format()
                else:
                    cause = u"\nsomeone mentioned your nick in {0}.\n".format(ch_name)

            self.world.send_chan_msg(
                u"-nfo-",
                inf_n,
                u"""[about notifications]{0}
  to jump through unread channels
  (or return to previous channel),
  press CTRL-E or use the command /a

  to disable audible alerts,
  use the command /b0
""".format(
                    cause
                ),
            )
            self.user.new_active_chan = inf_u
            self.refresh(False)

    def update_top_bar(self, full_redraw):
        """no need to optimize this tbh"""
        uchan = self.user.active_chan
        nchan = uchan.nchan
        topic = nchan.topic
        if nchan.name is None:
            title = uchan.alias
            if uchan.alias == self.user.nick:
                title += u" (You) (why)"
            else:
                if len(uchan.nchan.uchans) < 2:
                    title += u" (disconnected)"

            topic = topic.replace(u"[[uch_a]]", title)

        top_bar = u"\033[1H\033[44;48;5;235;38;5;220m%s\033[K" % (topic,)

        if self.screen[0] != top_bar:
            self.screen[0] = top_bar
            return Util.trunc(top_bar, self.w)[0]
        return u""

    def update_status_bar(self, full_redraw):
        preface = u"\033[%dH\033[0;37;44;48;5;235m" % (self.h - self.y_status,)
        hhmmss = t2hms(datetime.now(UTC), "%02d%02d%02d")
        uchan = self.user.active_chan
        nchan = uchan.nchan

        # print('@@@ active chan = {0}, other chans {1}'.format(
        # 	self.user.active_chan.alias or self.user.active_chan.nchan.name,
        # 	u', '.join(x.alias or x.nchan.name for x in self.user.chans)))

        nbuf = self.user.chans.index(uchan)
        chan_name = nchan.name
        if chan_name is None:
            # private chat
            chan_hash = u""
            chan_name = uchan.alias + u"\033[22m"
        else:
            chan_hash = u"#"
            chan_name = u"%s\033[22m(%d)" % (chan_name, len(nchan.uchans))

        hilights = []
        activity = []
        for i, chan in enumerate(self.user.chans):
            # print('testing {0} ({1}): h {2:1}, a {3:1}, dn {4:1}'.format(
            # 	chan, chan.nchan.get_name(), chan.hilights, chan.activity, chan.display_notification))

            if not chan.display_notification:
                continue

            if chan.hilights:
                hilights.append(i)

            if chan.activity:
                activity.append(i)

        if hilights:
            hilights = u"   \033[33mh:\033[1m%s\033[22;39m" % (
                u",".join(str(x) for x in hilights),
            )

        if activity:
            activity = u"   \033[32ma:\033[1m%s\033[22;39m" % (
                u",".join(str(x) for x in activity),
            )

        offscreen = None
        if not uchan.lock_to_bottom and uchan.vis[-1].im < len(nchan.msgs):
            offscreen = u"  \033[1;36m+%d\033[22;39m" % (
                len(nchan.msgs) - uchan.vis[-1].im,
            )

        if nchan.name and self.vt100:
            online = u"\033[22;36m   %s" % (nchan.usernames,)
        else:
            online = u""

        line = Util.trunc(
            u"%s%s   %s: \033[1;37m%s%s%s%s%s%s\033[K"
            % (
                preface,
                hhmmss,
                nbuf,
                chan_hash,
                chan_name,
                offscreen or u"",
                hilights or u"",
                activity or u"",
                online,
            ),
            self.w,
        )[0]

        if not self.vt100:
            self.left_chrome = u"%s   %s> " % (
                Util.strip_ansi(line),
                self.user.nick,
            )
            return u"\r%s\r%s" % (u" " * 78, self.left_chrome)

        elif full_redraw:
            if self.screen[self.h - (self.y_status + 1)] != line:
                self.screen[self.h - (self.y_status + 1)] = line
                return Util.trunc(line, self.w)[0]

        else:
            old = self.screen[self.h - (self.y_status + 1)]
            self.screen[self.h - (self.y_status + 1)] = line

            if len(old) != len(line):
                return Util.trunc(line, self.w)[0]

            cutoff = len(preface) + len(hhmmss)
            changed_part1 = old[:cutoff] != line[:cutoff]
            changed_part2 = old[cutoff:] != line[cutoff:]

            if changed_part2:
                # send all of it
                return Util.trunc(line, self.w)[0]

            if changed_part1:
                if int(time.time()) % 5 == 0:
                    # send just the timestamp
                    return line[:cutoff]

        return u""

    def compute_lineview(self, free_space, chi, ansi):
        # ensure at least 1/3 of the available space is
        # dedicated to text on the left side of the cursor
        left_margin = int(free_space * 0.334)
        if self.linepos - self.lineview < left_margin:
            self.lineview = self.linepos - left_margin

            if self.lineview < 0:
                self.lineview = 0

        # cursor is beyond right side of screen
        elif self.linepos > self.lineview + free_space:
            self.lineview = self.linepos - free_space

        # text is partially displayed,
        # but cursor is not sufficiently far to the right
        midways = int(free_space * 0.5)
        if self.lineview > 0 and len(chi) - self.lineview < midways:
            self.lineview = len(chi) - midways
            if self.lineview < 0:
                # not sure if this could actually happen
                # but the test is cheap enough so might as well
                self.lineview = 0

        start = 0
        if self.lineview > 0:
            # lineview is the first visible character to display,
            # we want to include any colour codes that precede it
            # so start from character lineview-1 into the ansi text
            try:
                start = chi[self.lineview - 1] + 1
            except:
                # seen in the wild, likely caused by that one guy with
                # the stupidly long nickname; adding this just in case
                Util.whoops("IT HAPPENED")
                print("user     = {0}".format(self.user.nick))
                try:
                    n = self.user.active_chan.nchan.get_name()
                    print("chan     = {0}".format(n))
                except:
                    pass
                print("linepos  = " + str(self.linepos))
                print("lineview = " + str(self.lineview))
                print("chi      = " + ",".join([str(x) for x in chi]))
                print("line     = " + Util.b2hex(self.linebuf.encode("utf-8")))
                print("termsize = " + str(self.w) + "x" + str(self.h))
                print("free_spa = " + str(free_space))
                print("-" * 72)
                # reset to sane defaults
                self.lineview = 0
                start = 0

        end = len(ansi)
        if self.lineview + free_space < len(chi) - 1:  # off-by-one?
            # no such concerns about control sequences after the last
            # visible character; just don't read past the end of chi
            end = chi[self.lineview + free_space]

        return ansi[start:end]

    def update_text_input(self, full_redraw):
        if not self.vt100:
            # cant believe this works
            free_space = 72 - len(self.left_chrome)
            p1 = self.linebuf[: self.linepos]
            p2 = self.linebuf[self.linepos :]
            ansi = Util.convert_color_codes(p1 + u"█" + p2, True)
            chi = Util.visual_indices(ansi)
            ret = self.compute_lineview(free_space, chi, ansi)
            return Util.strip_ansi(ret)

        if not full_redraw and not self.linebuf and self.linemode:
            return u""

        line_fmt = u"\033[0;36m%s>\033[0m %s"
        print_fmt = u"\033[%sH%s\033[K"

        if self.pending_size_request and (
            self.linemode
            or time.time() - self.pending_size_request
            > (0.5 if self.bps > 12000 else 10)
        ):
            line = line_fmt % (
                self.user.nick[: self.user.nick_len],
                u"#\033[7m             please press ENTER  (due to linemode) \033[0m",
            )
            if self.screen[self.h - (self.y_input + 1)] != line or full_redraw:
                self.screen[self.h - (self.y_input + 1)] = line
                return print_fmt % (self.h - self.y_input, line)
            return u""

        if (
            u"\x02" in self.linebuf
            or u"\x0b" in self.linebuf
            or u"\x0f" in self.linebuf
        ):
            ansi = Util.convert_color_codes(self.linebuf, True)
            chi = Util.visual_indices(ansi)
        else:
            ansi = self.linebuf
            chi = list(range(len(ansi)))

        # nick chrome + final char on screen
        free_space = self.w - (self.user.nick_len + 2 + 1)
        if len(chi) <= free_space:
            self.lineview = 0
        else:
            ansi = self.compute_lineview(free_space, chi, ansi)

        if u"\033" in ansi:
            # reset colours if the visible segment contains any
            ansi += u"\033[0m"

        line = line_fmt % (self.user.nick[: self.user.nick_len], ansi)
        was = self.screen[self.h - (self.y_input + 1)]
        if line == was and not full_redraw:
            return u""

        self.screen[self.h - (self.y_input + 1)] = line
        coord = self.h - self.y_input

        if self.bps < 12000 and not full_redraw:
            endpos = min(len(was), len(line))
            ofs = next((i for i in range(endpos) if was[i] != line[i]), endpos)

            # dont corrupt color terminators
            color = u""
            eofs = was[:ofs].rfind(u"\033")
            if eofs + 1 and ofs - eofs < 10:  # "0;33;44m"
                ofs = eofs
            else:
                # reapply active colorset
                colors = was[1:ofs].split(u"\033[")
                for ctxt in reversed(colors[1:]):
                    cval = ctxt.split(u"m")[0]
                    if cval == u"0":
                        break
                    elif len(cval) < 8:  # "0;33;44"
                        color = u"%s;%s" % (cval, color)

                if color:
                    color = u"\033[%sm" % (color.rstrip(u";"),)

            vtxt = Util.strip_ansi(was[:ofs])
            coord = u"%s;%d" % (coord, len(vtxt) + 1)
            line = color + line[ofs:]

        return print_fmt % (coord, line)

    def msg2ansi(self, msg, msg_fmt, nfmt, ts_fmt, msg_nl, msg_w, msg_w2, nick_w):
        ts = ts_fmt % {"h": msg.dt.hour, "m": msg.dt.minute, "s": msg.dt.second}

        txt = []
        for ln in [x.rstrip() for x in msg.txt.split(u"\n")]:
            if len(ln) < msg_w or Util.visual_length(ln) < msg_w:
                txt.append(ln)
            elif self.view:
                txt.extend(Util.hardwrap(ln.rstrip(), msg_w, self.vt100))
            else:
                txt.extend(Util.wrap(ln.rstrip(), msg_w, msg_w2))

        for n, line in enumerate(txt):
            if u"\033" in line:
                if self.vt100:
                    line += u"\033[0m"
                else:
                    line = Util.strip_ansi(line)

            if n == 0:
                c1 = u""
                c2 = u""
                if self.vt100:
                    c1 = u"\033[1m"
                    c2 = u"\033[0m"
                    if msg.user == u"-nfo-":
                        c1 = u"\033[0;32m"
                    elif msg.user == u"-err-":
                        c1 = u"\033[1;33m"
                    elif msg.user == u"***":
                        c1 = u"\033[36m"
                    elif msg.user != u"--" and self.cnicks:
                        try:
                            c1 = self.world.cntab[msg.user]
                        except:
                            crc = zlib.crc32(msg.user.encode("utf-8")) & 0xFFFFFFFF
                            c1 = Util.BRI_256[crc % len(Util.BRI_256)]
                            c1 = u"\033[1;48;5;16;38;5;%dm" % (c1,)
                            self.world.cntab[msg.user] = c1

                if nfmt == 1:
                    txt[n] = msg_fmt % (line,)
                elif nfmt == 4:
                    txt[n] = msg_fmt % (c1, msg.user[:nick_w], c2, line)
                else:
                    txt[n] = msg_fmt % (ts, c1, msg.user[:nick_w], c2, line)
            else:
                txt[n] = msg_nl + line

        return txt

    def update_chat_view(self, full_redraw, mark_messages_read, call_depth=0):
        ch = self.user.active_chan
        nch = ch.nchan
        ret = u""

        if call_depth > 3:
            # the famous "should never happen"
            Util.whoops("ch={0} usr={1}".format(nch.get_name(), self.user.nick))
            return None

        debug_scrolling = False

        nick_w = None
        if self.user.active_chan.alias == u"r0c-status":
            nick_w = 6

        if self.view:
            nick_w = 0
            msg_w = self.w
            msg_nl = u""
            ts_fmt = ""
            msg_fmt = u"%s"
            nfmt = 1  # line
        elif self.w >= 140:
            nick_w = nick_w or 14
            msg_w = self.w - (nick_w + 10)
            msg_nl = u" " * (nick_w + 10)
            ts_fmt = "%(h)02d:%(m)02d:%(s)02d"
            msg_fmt = u"%%s %%s%%%ds%%s %%s" % (nick_w,)
            nfmt = 5  # ts,c1,nick,c2,line
        elif self.w >= 100:
            nick_w = nick_w or 12
            msg_w = self.w - (nick_w + 10)
            msg_nl = u" " * (nick_w + 10)
            ts_fmt = "%(h)02d:%(m)02d:%(s)02d"
            msg_fmt = u"%%s %%s%%%ds%%s %%s" % (nick_w,)
            nfmt = 5  # ts,c1,nick,c2,line
        elif self.w >= 80:
            nick_w = nick_w or 10
            msg_w = self.w - (nick_w + 8)
            msg_nl = u" " * (nick_w + 8)
            ts_fmt = "%(h)02d%(m)02d%(s)02d"
            msg_fmt = u"%%s %%s%%%ds%%s %%s" % (nick_w,)
            nfmt = 5  # ts,c1,nick,c2,line
        elif self.w >= 60:
            nick_w = nick_w or 8
            msg_w = self.w - (nick_w + 6)
            msg_nl = u" " * (nick_w + 6)
            ts_fmt = "%(h)02d%(m)02d"
            msg_fmt = u"%%s %%s%%%ds%%s %%s" % (nick_w,)
            nfmt = 5  # ts,c1,nick,c2,line
        else:
            nick_w = nick_w or 8
            msg_w = self.w - (nick_w + 1)
            msg_nl = u" " * (nick_w + 1)
            ts_fmt = ""
            msg_fmt = u"%%s%%%ds%%s %%s" % (nick_w,)
            nfmt = 4  # c1,nick,c2,line

        if self.align:
            msg_w2 = msg_w
        else:
            msg_w2 = self.w - 2
            msg_nl = u"  "

        # first ensure our cache is sane
        if not ch.vis:
            self.scroll_cmd = 0
            ch.lock_to_bottom = True
            full_redraw = True
        else:
            if len(nch.msgs) <= ch.vis[0].im or nch.msgs[ch.vis[0].im] != ch.vis[0].msg:

                try:
                    # some messages got pruned from the channel message list
                    if len(nch.msgs) <= ch.vis[0].im:
                        print(
                            "\033[1;33mcache inval:  [{0}] in [{1}], |{2}| <= {3}\033[0m".format(
                                ch.user.nick,
                                nch.get_name(),
                                len(nch.msgs),
                                ch.vis[0].im,
                            )
                        )
                    else:
                        print(
                            "\033[1;33mcache inval:  [{0}] in [{1}], #{2} <= #{3}\033[0m".format(
                                ch.user.nick,
                                nch.get_name(),
                                nch.msgs[ch.vis[0].im].sno,
                                ch.vis[0].msg.sno,
                            )
                        )

                    im0 = nch.msgs.index(ch.vis[0].msg)
                    for n, vis in enumerate(ch.vis):
                        vis.im = n + im0
                except:
                    # the pruned messages included the visible ones,
                    # scroll client to bottom
                    print(
                        "\033[1;33mviewport NG:  [{0}] in [{1}]\033[0m".format(
                            ch.user.nick, nch.get_name()
                        )
                    )

                    self.scroll_cmd = 0
                    ch.lock_to_bottom = True
                    full_redraw = True

        # we get painfully slow on join/parts when the
        # channel has more than 800 messages or so
        #
        # thanks stress.py
        if (
            ch.lock_to_bottom
            and not full_redraw
            and nch.msgs[-1].sno - ch.vis[-1].msg.sno > self.h * 2
        ):
            # lots of messages since last time, no point in scrolling
            self.scroll_cmd = 0
            full_redraw = True

        if full_redraw:
            if self.scroll_cmd:
                # all the scrolling code assumes a gradual refresh,
                # this is cheap enough to almost be defendable
                self.update_chat_view(False, False, call_depth + 1)

            lines = []
            lines_left = self.h - 3

            if not ch.lock_to_bottom:
                # fixed scroll position:
                # oldest/top message will be added first
                top_msg = ch.vis[0]
                imsg = top_msg.im
                ch.vis = []
                for n, msg in enumerate(nch.msgs[imsg : imsg + self.h - 3]):
                    txt = self.msg2ansi(
                        msg, msg_fmt, nfmt, ts_fmt, msg_nl, msg_w, msg_w2, nick_w
                    )

                    if top_msg is not None and len(top_msg.txt) == len(txt):
                        car = top_msg.car
                        cdr = len(top_msg.txt)
                        n_vis = cdr - car
                        top_msg = None
                        if n_vis > lines_left:
                            delta = n_vis - lines_left
                            n_vis -= delta
                            cdr -= delta

                    else:
                        # not top message,
                        # or no previous top message to compare,
                        # or layout changed
                        n_vis = len(txt)
                        car = 0
                        cdr = n_vis
                        if n_vis > lines_left:
                            n_vis = lines_left
                            cdr = n_vis

                    if cdr > len(txt) or car >= cdr or n_vis == 0:
                        print("bug1 car{0} cdr{1} len{2}".format(car, cdr, len(txt)))

                    vmsg = Chat.VisMessage().c_new(msg, txt, imsg, car, cdr, ch)
                    ch.vis.append(vmsg)

                    for ln in vmsg.txt[car:cdr]:
                        lines.append(ln)

                    imsg += 1
                    lines_left -= n_vis
                    if lines_left <= 0:
                        break

                if lines_left > 0 and ch.vis[0].msg != nch.msgs[0]:
                    # we didn't manage to fill the screen,
                    # TODO:  go above vis[0] rather than cheat
                    ret = u""
                    lines = []
                    lines_left = self.h - 3
                    ch.lock_to_bottom = True

            if ch.lock_to_bottom:
                # lock to bottom, full redraw:
                # newest/bottom message will be added first
                ch.vis = []
                for n, msg in enumerate(reversed(nch.msgs)):
                    imsg = (len(nch.msgs) - 1) - n
                    txt = self.msg2ansi(
                        msg, msg_fmt, nfmt, ts_fmt, msg_nl, msg_w, msg_w2, nick_w
                    )

                    n_vis = len(txt)
                    car = 0
                    cdr = n_vis
                    if n_vis >= lines_left:
                        n_vis = lines_left
                        car = cdr - n_vis

                    if cdr > len(txt) or car >= cdr or n_vis == 0:
                        print("bug2 car{0} cdr{1} len{2}".format(car, cdr, len(txt)))

                    vmsg = Chat.VisMessage().c_new(msg, txt, imsg, car, cdr, ch)
                    ch.vis.append(vmsg)

                    for ln in reversed(vmsg.txt[car:]):
                        lines.append(ln)

                    lines_left -= n_vis
                    if lines_left <= 0:
                        break

                ch.vis.reverse()
                lines.reverse()

            if not self.vt100:
                # ret = u'\r==========================\r\n'
                # print(lines)
                for ln in lines:
                    # print('sending {0} of {1}'.format(ln, len(lines)))
                    # if isinstance(lines, list):
                    # 	print('lines is list')
                    ret += u"\r%s%s\r\n" % (ln, u" " * ((self.w - len(ln)) - 2))
                return ret

            while len(lines) < self.h - 3:
                lines.append(u"--")

            for n in range(self.h - 3):
                self.screen[n + 1] = lines[n]
                ret += u"\033[%dH\033[K%s" % (n + 2, self.screen[n + 1])

        else:
            # full_redraw = False,
            # do relative scrolling if necessary

            t_steps = self.scroll_cmd  # total number of scroll steps
            n_steps = 0  # number of scroll steps performed
            self.scroll_cmd = 0

            lines_in_use = 0
            for msg in ch.vis:
                lines_in_use += msg.cdr - msg.car

            if t_steps:
                # print('@@@ have scroll steps')
                ch.lock_to_bottom = False
            else:
                # print('@@@ no scroll steps')
                if not ch.lock_to_bottom:
                    # fixed viewport
                    # print('@@@ not lock to bottom')
                    return ret

                if nch.msgs[-1] == ch.vis[-1].msg and not mark_messages_read:
                    # no new messages
                    # print('@@@ no new messages: {0}'.format(ch.vis[-1].txt[0][:40]))
                    return ret

                # push all new messages
                t_steps = 99999999999

            abs_steps = abs(t_steps)  # abs(total steps)

            # print('@@@ gonna scroll {0} lines'.format(abs_steps))

            # for msg in ch.vis:
            #     for ln in msg.txt[msg.car : msg.cdr]:
            #         print(ln)

            # set scroll region:  chat pane
            if self.vt100:
                ret += u"\033[2;%dr" % (self.h - 2,)

            # first / last visible message might have lines off-screen;
            # check those first
            partial = None  # currently offscreen text
            partial_org = None  # unmodified original
            partial_old = None  # currently visible segment
            partial_new = None  # currently invisible segment

            # scrolling up; grab offscreen text at top
            if t_steps < 0:
                ref = ch.vis[0]
                if ref.car != 0:

                    partial = Chat.VisMessage().c_segm(ref, 0, ref.car, 0, ref.car, ch)
                    partial_org = ref
                    partial_old = Chat.VisMessage().c_segm(
                        ref, ref.car, ref.cdr, 0, ref.cdr - ref.car, ch
                    )

                    ch.vis[0] = partial_old

                    if debug_scrolling:
                        print(
                            "@@@ slicing len({0}) car,cdr({1},{2}) into nlen({3})+olen({4}), ncar,ncdr({5},{6})? ocar,ocdr({7},{8})".format(
                                len(partial_org.txt),
                                partial_org.car,
                                partial_org.cdr,
                                len(partial.txt),
                                len(partial_old.txt),
                                0,
                                len(partial.txt),
                                partial_old.car,
                                partial_old.cdr,
                            )
                        )
                        for ln in partial.txt:
                            print(ln, "+new")
                        for ln in partial_old.txt:
                            print(ln, "---old")
            else:
                ref = ch.vis[-1]
                if ref.cdr != len(ref.txt):

                    if debug_scrolling:
                        for n, ln in enumerate(ref.txt):
                            if n == ref.car:
                                anchor = "== car"
                            elif n == ref.cdr - 1:
                                anchor = "== cdr"
                            else:
                                anchor = ""

                            print("{0:2} {1} {2}".format(n, ln, anchor))

                    if ref.cdr > len(ref.txt) or ref.car >= ref.cdr:
                        print(
                            "bug3 car{0} cdr{1} len{2}".format(
                                ref.car, ref.cdr, len(ref.txt)
                            )
                        )

                    partial = Chat.VisMessage().c_segm(
                        ref, ref.cdr, len(ref.txt), 0, len(ref.txt) - ref.cdr, ch
                    )
                    partial_org = ref
                    partial_old = Chat.VisMessage().c_segm(
                        ref, ref.car, ref.cdr, 0, ref.cdr - ref.car, ch
                    )

                    ch.vis[-1] = partial_old

                    if debug_scrolling:
                        print(
                            "@@@ slicing len({0}) car,cdr({1},{2}) into olen({3})+nlen({4}), ocar,ocdr({5},{6}) ncar,ncdr({7},{8})?".format(
                                len(partial_org.txt),
                                partial_org.car,
                                partial_org.cdr,
                                len(partial_old.txt),
                                len(partial.txt),
                                partial_old.car,
                                partial_old.cdr,
                                0,
                                len(partial.txt),
                            )
                        )
                        for ln in partial_old.txt:
                            print(ln, "---old")
                        for ln in partial.txt:
                            print(ln, "+new")

            # get message offset to start from
            if t_steps < 0:
                imsg = ch.vis[0].im
            else:
                imsg = ch.vis[-1].im

            if debug_scrolling:
                print(
                    "@@@ num chan messages {0}, num vis messages {1}, retained {2} = {3}".format(
                        len(nch.msgs), len(ch.vis), imsg, nch.msgs[imsg].txt[:6]
                    )
                )
                dbg = ""
                for m in ch.vis:
                    dbg += "{0}, ".format(m.im)
                print("@@@ {0}".format(dbg))

            # scroll until n_steps reaches abs_steps
            while n_steps < abs_steps:
                vmsg = None
                if partial:
                    vmsg = partial
                else:
                    if t_steps < 0:
                        imsg -= 1
                        if imsg < 0:
                            break
                    else:
                        imsg += 1
                        if imsg >= len(nch.msgs):
                            break

                    msg = nch.msgs[imsg]
                    txt = self.msg2ansi(
                        msg, msg_fmt, nfmt, ts_fmt, msg_nl, msg_w, msg_w2, nick_w
                    )

                    vmsg = Chat.VisMessage().c_new(msg, txt, imsg, 0, len(txt), ch)

                txt = vmsg.txt
                msg = vmsg.msg

                if t_steps < 0:
                    txt_order = reversed(txt)
                else:
                    txt_order = txt

                # write lines to send buffer
                n_vis = 0
                for ln in txt_order:
                    # print(u'@@@ vis{0:2} stp{1:2} += {2}'.format(n_vis, n_steps, ln))

                    if not self.vt100:
                        ret += u"\r%s%s\r\n" % (ln, u" " * ((self.w - len(ln)) - 2))

                    elif lines_in_use < self.h - 3:
                        ret += u"\033[%dH\033[K%s" % (lines_in_use + 2, ln)
                        lines_in_use += 1

                    elif t_steps > 0:
                        # official way according to docs,
                        # doesn't work in windows terminals (xp..win10)
                        # ret += u'\033[{0}H\033[S\033[K{1}'.format(self.h - 2, ln)

                        # stopped working in WSL1 terminals on LTSC 2020-09
                        # ret += u"\033[{0}H\033D\033[K{1}".format(self.h - 2, ln)

                        # ok
                        ret += u"\033[%dH\n\n\033[K%s" % (self.h - 3, ln)

                    else:
                        # official way according to docs,
                        # doesn't work on inetutils-1.9.4
                        # ret += u'\033[2H\033[T\033[K{0}'.format(ln)

                        # also works
                        ret += u"\033[2H\033M\033[K%s" % (ln,)

                    n_vis += 1
                    n_steps += 1
                    if n_steps >= abs_steps:
                        break

                if t_steps < 0:
                    new_cdr = len(txt)
                    new_car = new_cdr - n_vis
                else:
                    new_car = 0
                    new_cdr = n_vis

                vmsg.car = new_car
                vmsg.cdr = new_cdr
                # print('@@@ vismsg len({0}) car,cdr({1},{2}) -- {3}'.format(len(txt), new_car, new_cdr, txt[0][-30:]))

                if vmsg.cdr > len(vmsg.txt) or vmsg.car >= vmsg.cdr or n_vis == 0:
                    print(
                        "bug4 car{0} cdr{1} len{2}".format(
                            vmsg.car, vmsg.cdr, len(vmsg.txt)
                        )
                    )

                if t_steps < 0:
                    ch.vis.insert(0, vmsg)
                else:
                    ch.vis.append(vmsg)

                if partial:
                    partial = None
                    partial_new = vmsg

            # release scroll region
            if self.vt100:
                ret += u"\033[r"

            # trim away messages that went off-screen
            if t_steps < 0:
                vis_order = ch.vis
            else:
                vis_order = reversed(ch.vis)

            n_msg = 0
            ln_left = self.h - 3

            for i, vmsg in enumerate(vis_order):
                if ln_left <= 0:
                    break

                n_msg += 1
                msg_sz = vmsg.cdr - vmsg.car

                if msg_sz >= ln_left:
                    if msg_sz > ln_left:
                        if t_steps < 0:
                            vmsg.cdr -= msg_sz - ln_left
                        else:
                            vmsg.car += msg_sz - ln_left
                    msg_sz = ln_left

                ln_left -= msg_sz

                # print('@@@ 1 {0}'.format('\r\n@@@ 1 '.join(vmsg.txt[vmsg.car : vmsg.cdr])))

            if t_steps < 0:
                ch.vis = ch.vis[:n_msg]
            else:
                ch.vis = ch.vis[-n_msg:]

            # glue together the 2 parts forming the formerly off-screen message
            if partial_old:
                if partial_old not in ch.vis:
                    # old segment is gone, discard it
                    if t_steps > 0:
                        partial_new.car += len(partial_old.txt)
                        partial_new.cdr += len(partial_old.txt)
                else:
                    # old segment is partially or fully visible
                    ch.vis.remove(partial_old)
                    if t_steps < 0:
                        partial_new.cdr += partial_old.cdr
                    else:
                        if debug_scrolling:
                            print(
                                "@@@ merging old({0},{1}) new({2},{3}) olen({4}) org({5},{6})".format(
                                    partial_old.car,
                                    partial_old.cdr,
                                    partial_new.car,
                                    partial_new.cdr,
                                    len(partial_old.txt),
                                    partial_org.car,
                                    partial_org.cdr,
                                )
                            )
                            for n, ln in enumerate(partial_old.txt):
                                print(ln, "---old", n)
                            for n, ln in enumerate(partial_new.txt):
                                print(ln, "+new", n)
                        partial_new.car += partial_old.car
                        partial_new.cdr += partial_old.cdr

                        partial_new.car += partial_org.car
                        partial_new.cdr += partial_org.car

                partial_new.txt = partial_org.txt
                partial_new.msg = partial_org.msg

                if debug_scrolling:
                    print(
                        "@@@ car,cdr ({0},{1})".format(partial_new.car, partial_new.cdr)
                    )

            # update message read state on both sides
            if self.vt100:
                y_pos = 2
                for i, vmsg in enumerate(ch.vis):
                    if vmsg.car > 0:
                        y_pos += vmsg.cdr - vmsg.car
                        continue

                    if vmsg.unread and vmsg.msg.sno <= ch.last_read:
                        # print('switching message unread -> read for {0}: this({1}) last_read({2})'.format(
                        # 	ch.user.nick, vmsg.msg.sno, ch.last_read))
                        vmsg.unread = False
                        vmsg.apply_markup()
                        v = vmsg.txt[0]
                        if not v:
                            continue
                        elif self.view:
                            ret += u"\033[%dH%s " % (y_pos, v)
                        elif not v.startswith(u" "):
                            ret += u"\033[%dH%s " % (y_pos, v[: v.find(u" ")])

                    y_pos += vmsg.cdr - vmsg.car

            # update the server-side screen buffer
            new_screen = [self.screen[0]]
            for i, vmsg in enumerate(ch.vis):
                for ln in vmsg.txt[vmsg.car : vmsg.cdr]:
                    new_screen.append(ln)

            while len(new_screen) < self.h - 2:
                new_screen.append(u"--")

            new_screen.append(self.screen[-2])
            new_screen.append(self.screen[-1])
            old_screen = self.screen
            self.screen = new_screen

            ch.lock_to_bottom = ch.vis[-1].msg == nch.msgs[-1] and ch.vis[
                -1
            ].cdr == len(ch.vis[-1].txt)

            # print('@@@ lock_to_bottom:', ch.lock_to_bottom)

            if len(self.screen) != self.h:
                print(
                    "!!! new screen is {0} but client is {1}".format(
                        len(self.screen), self.h
                    )
                )
                for n, ln in enumerate(old_screen):
                    print("o", ln, n)
                for n, ln in enumerate(new_screen):
                    print("new", ln, n)
                time.sleep(100000)

            if not self.vt100:
                if t_steps < 0:
                    # rely on vt100 code to determine the new display
                    # then retransmit the full display  (good enough)
                    ret = self.update_chat_view(True, True, call_depth + 1)
                    if ret is not None:
                        return u"\r\n" * self.h + ret
                    else:
                        return u"\r\n" * self.h + u"somethhing broke\r\n"

        if len(nch.msgs) <= ch.vis[0].im or nch.msgs[ch.vis[0].im] != ch.vis[0].msg:
            print()
            print("\033[1;31mcache inval:  bug in update_chat_view ;_;\033[0m")
            if len(nch.msgs) < 10:
                print("vis.im:   " + ", ".join([str(x.im) for x in ch.vis]))
                print("vis.sno:  " + ", ".join([str(x.msg.sno) for x in ch.vis]))
                print("nch.msgs: " + ", ".join([str(x.sno) for x in nch.msgs]))
            print()

        # lock to bottom if all recent messages are visible
        if not ch.lock_to_bottom:
            vlast = ch.vis[-1]
            if nch.msgs[-1] == vlast.msg and vlast.cdr == len(vlast.txt):
                ch.lock_to_bottom = True

        # print('update_chat:  {0} runes'.format(len(ret)))
        # print(' scroll_cmd:  {0}'.format(self.scroll_cmd))
        return ret

    def adapt_to_modem(self):
        self.m_refresh = 1

        if self.bps > 12000:
            return

        if self.bps < 525:  # (1200-300)/4+300
            self.bps = 300
            self.m_refresh = 6

        elif self.bps < 1500:
            self.bps = 1200
            self.m_refresh = 3

        elif self.bps < 3000:
            self.bps = 2400
            self.m_refresh = 2

        elif self.bps < 6000:
            self.bps = 4800

        else:
            self.bps = 9600

        self.world.send_chan_msg(
            u"-nfo-",
            self.user.chans[0].nchan,
            u"detected {0} bps modem; optimizing\n".format(self.bps),
            ping_self=False,
        )

    def conf_wizard(self, growth):
        # print('conf_wizard:  {0}'.format(self.wizard_stage))
        if u"\x03" in self.in_text:
            if self.ar.dev and self.adr[0] == "127.0.0.1":
                self.world.core.shutdown()
            else:
                self.sck.send(b"ok bye\r\n")
                self.host.part(self)
            return

        # print('{0:8s} {1:12s} {2}'.format(self.wizard_stage, self.in_text, self.in_text_full).replace('\r','.').replace('\n','.'))

        if not self.is_bot:
            if self.host.re_bot.search(self.in_text_full):
                self.wizard_stage = "bot1"
                self.is_bot = True
                self.world.cserial += 1

                m = "{0}  {1}".format(self.user.nick, self.adr[0])
                self.host.schedule_kick(self, 69, "    botkick:  " + m)
                print("     is bot:  " + m)

        if self.wizard_stage.startswith("bot"):
            nline = u"\x0d\x0a\x00"
            while True:
                nl = next((i for i, ch in enumerate(self.in_text) if ch in nline), None)
                if nl is None:
                    break

                growth = 0
                part1 = self.in_text[:nl]
                self.in_text = self.in_text[nl + 1 :].lstrip(nline)
                # print(b2hex(self.in_text.encode('utf-8')))

                if self.wizard_stage == "bot1":
                    self.say(b"\r\nSEGMENTATION FAULT\r\n\r\nroot@IBM_3090:/# ")
                    self.wizard_stage = "bot2"

                elif self.wizard_stage == "bot2":
                    try:
                        self.say(
                            u"\r\nSYNTAX ERROR: {0}\r\n\r\nroot@IBM_3090:/# ".format(
                                part1.strip(u"\x0d\x0a\x00 ")
                            ).encode("utf-8")
                        )
                    except:
                        self.say(b"\r\nSYNTAX ERROR\r\n\r\nroot@IBM_3090:/# ")

                else:
                    Util.whoops("bad bot stage: {0}".format(self.wizard_stage))

            if self.wizard_stage == "bot2":
                self.say(self.in_text[-growth:].encode("utf-8"))

            return

        sep = u"\n%s\n\033[2A" % (u"/" * 71,)
        ftop = u"\n" * 20 + u"\033[H\033[J"
        top = ftop + u" [ r0c configurator ]\n"

        if self.wizard_stage == "start":
            if not self.load_config():
                self.wizard_stage = "qwer_prompt"
                return self.conf_wizard(growth)

            self.wizard_stage = "config_reuse"
            self.in_text = u""

            linemode = "Yes" if int(self.linemode) == 1 else "No"
            vt100 = "Yes" if int(self.vt100) == 1 else "No"
            echo_on = "Yes" if int(self.echo_on) == 1 else "No"

            enc_ascii = None
            enc_unicode = None
            for enc, uni in zip(self.codec_map[::2], self.codec_map[1::2]):
                if self.codec == enc:
                    enc_ascii = self.codec_asc[uni]
                    enc_unicode = self.codec_uni[uni]

            if not enc_ascii:
                self.wizard_stage = "qwer_prompt"
                return self.conf_wizard(growth)

            to_say = (
                (
                    top
                    + u"""
 verify that your config is still OK:
"""
                )
                .replace(u"\n", u"\r\n")
                .encode("utf-8")
            )

            if enc_ascii == "n/a":
                to_say += b"    unicode / extended characters: DISABLED\r\n"
            else:
                to_say += u'    this says "{0}":  " '.format(enc_ascii).encode("utf-8")
                to_say += enc_unicode.encode(self.codec, "backslashreplace")
                to_say += b'"\r\n'

            to_say += (
                u"""\
\033[32m    this sentence is{0} green \033[0m
""".format(
                    u"" if self.vt100 else u" NOT"
                )
                .replace(u"\n", u"\r\n")
                .encode("utf-8")
            )

            ok = "your client is OK"
            ng = "get better software"

            to_say += (
                u"""
 technical details:
    linemode:  {l_c}  ({l_g})
    colors:    {c_c}  ({c_g})
    echo:      {e_c}  ({e_g})
    encoding:  {enc_c} + {r_c}{slowmo}

    Y:  correct; continue
    N:  use another config

 press Y or N, followed by [Enter] [Enter]
""".format(
                    l_c=linemode.ljust(3),
                    c_c=vt100.ljust(3),
                    e_c=echo_on.ljust(3),
                    r_c=Util.b2hex(self.crlf.encode("utf-8")),
                    l_g=ok if not self.linemode else ng,
                    c_g=ok if self.vt100 else ng,
                    e_g=ok if not self.echo_on else ng,
                    enc_c=self.codec,
                    slowmo="\n    slowmo:    ENABLED" if self.slowmo_tx else "",
                )
                .replace(u"\n", u"\r\n")
                .encode("utf-8")
            )

            self.say(to_say)
            return

        if self.wizard_stage.startswith("iface_then_"):
            text = self.in_text.lower()
            if u"y" in text:
                ofs = self.wizard_stage.find("_then_")
                self.wizard_stage = self.wizard_stage[ofs + 6 :]
            elif u"n" in text:
                self.host.part(self)

        if self.wizard_stage == "config_reuse":
            delta = len(self.in_text) - self.wizard_lastlen
            oldtxt = self.in_text[: self.wizard_lastlen]
            self.wizard_lastlen = len(self.in_text)

            nline = u"\x0d\x0a\x00"
            if self.wizard_mindelta > delta and oldtxt.rstrip(nline) == oldtxt:
                self.wizard_mindelta = delta

            ret_ok = self.determine_retkey(True)
            if ret_ok is None:
                return

            text = self.in_text.lower()
            if u"y" in text:
                text = text[text.rfind(u"y") :]
                looks_like_linemode = self.wizard_mindelta > 1

                self.wizard_reuse_errors = []
                if self.linemode != looks_like_linemode:
                    self.wizard_reuse_errors.append("linemode changed")
                if not ret_ok:
                    self.wizard_reuse_errors.append("retkey changed")

                if self.wizard_reuse_errors:
                    self.default_config()
                    if not self.check_correct_iface("reuse_impossible"):
                        return
                else:
                    self.reassign_retkey(self.crlf)
                    if not self.check_correct_iface("end"):
                        return

            elif u"n" in text:
                self.default_config()
                old_nick = self.user.nick
                self.user.set_rand_nick()
                print(" regen nick:  %s  %s" % (old_nick, self.user.nick))
                if not self.check_correct_iface("qwer_prompt"):
                    return

        if self.wizard_stage == "reuse_impossible":
            self.wizard_stage = "qwer_read"
            self.wizard_lastlen = 0
            self.in_text = u""
            self.say(
                (
                    top
                    + u"""
 sorry, your config is definitely incorrect:

   -- {0}

 type the text below, then hit [Enter] [Enter]:

   qwer asdf

 """.format(
                        "\n   -- ".join(self.wizard_reuse_errors)
                    )
                )
                .replace(u"\n", u"\r\n")
                .encode("utf-8")
            )
            # \033[10Hasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdf

            return

        if self.wizard_stage == "qwer_prompt":
            self.wizard_stage = "qwer_read"
            self.in_text = u""
            self.say(
                (
                    top
                    + u"""
 type the text below, then hit [Enter] [Enter]:

   qwer asdf

 """
                )
                .replace(u"\n", u"\r\n")
                .encode("utf-8")
            )
            # \033[10Hasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasdf

            return

        if self.wizard_stage == "qwer_read":
            nline = b"\x0d\x0a\x00"
            btext = self.in_text.encode("utf-8")
            delta = len(self.in_text) - self.wizard_lastlen
            self.wizard_lastlen = len(self.in_text)
            if delta > 1:
                # acceptable if delta is exactly 2
                # and the final characters are newline-ish
                print(
                    "client burst  {0}  {1}  {2}".format(
                        self.user.nick, self.adr[0], delta
                    )
                )

                if delta > 2 or btext[-1] not in nline:
                    if self.wizard_maxdelta < delta:
                        self.wizard_maxdelta = delta

            if self.determine_retkey():
                non_nl = [x for x in btext if x not in nline]
                if self.wizard_maxdelta >= max(len(non_nl) - 2, 2):
                    self.echo_on = True
                    self.linemode = True
                    print(
                        "setting linemode+echo since d{0} and {1}ch; {2}".format(
                            self.wizard_maxdelta,
                            len(self.in_text),
                            Util.b2hex(self.in_text.encode("utf-8")),
                        )
                    )

                self.wizard_stage = "echo"

                join_ch = None

                # cheatcode: windows netcat
                if self.in_text.startswith("wncat"):
                    self.linemode = True
                    self.echo_on = True
                    self.vt100 = False
                    self.set_codec("cp437")
                    self.wizard_stage = "end"

                # cheatcode: windows telnet + join
                elif self.in_text.startswith("wtn"):
                    self.slowmo_tx = 1
                    self.set_codec("cp437")
                    self.wizard_stage = "end"
                    join_ch = self.in_text[3:]

                # cheatcode: linux telnet + join
                elif self.in_text.startswith("ltn"):
                    self.set_codec("utf-8")
                    self.wizard_stage = "end"
                    join_ch = self.in_text[3:]

                # this is just for the stress tests,
                # i don't feel bad about this at all
                if join_ch:

                    def delayed_join(usr, chan):
                        chan = chan.rstrip("\r\n\0 ")  # \0 ??
                        time.sleep(0.2)
                        if chan:
                            print(" delay join:  [{0}]".format(chan))
                            usr.world.join_pub_chan(usr, chan)
                            usr.client.refresh(False)

                    Util.Daemon(delayed_join, "d_join", (self.user, join_ch))

        if self.wizard_stage == "echo":
            if self.linemode:
                # echo is always enabled if linemode, skip this stage
                if not self.check_correct_iface("linemode"):
                    return
            else:
                self.wizard_stage = "echo_answer"
                self.in_text = u""
                self.say(
                    (
                        u"""

   A:  your text appeared as you typed

   B:  nothing happened

 press A or B&lm
 """
                    )
                    .replace(u"\n", u"\r\n")
                    .replace(
                        u"&lm", u", followed by [Enter]" if self.linemode else u":"
                    )
                    .encode("utf-8")
                )
                return

        if self.wizard_stage == "echo_answer":
            text = self.in_text.lower()
            if u"a" in text:
                self.echo_on = True
                if not self.check_correct_iface("linemode"):
                    return
            elif u"b" in text:
                if not self.check_correct_iface("linemode"):
                    return

        if self.wizard_stage == "linemode":
            if self.linemode:
                self.wizard_stage = "linemode_warn"
                self.in_text = u""
                self.say(
                    (
                        top
                        + u"""
 WARNING:
   your client is stuck in line-buffered mode,
   this will cause visual glitches in text input.
   Keys like PgUp and CTRL-Z are also buggy;
   you must press the key twice followed by Enter.

 if you are using Linux or Mac OSX, disconnect and
 run the following command before reconnecting:
   macOS:  stty -f /dev/stdin -icanon
   Linux:  stty -icanon

 press A to accept or Q to quit&lm
 """
                    )
                    .replace(u"\n", u"\r\n")
                    .replace(
                        u"&lm", u", followed by [Enter]" if self.linemode else u":"
                    )
                    .encode("utf-8")
                )
                return

            self.wizard_stage = "color"

        if self.wizard_stage == "linemode_warn":
            text = self.in_text.lower()
            if u"a" in text:
                self.wizard_stage = "color"
            elif u"q" in text:
                self.host.part(self)

        if self.wizard_stage == "color":
            self.wizard_stage = "color_answer"
            self.in_text = u""
            self.say(
                (
                    top
                    + u"""
 does colours work?
 \033[1;31mred, \033[32mgreen, \033[33myellow, \033[34mblue\033[0m

 press Y or N&lm
 """
                )
                .replace(u"\n", u"\r\n")
                .replace(u"&lm", u", followed by [Enter]" if self.linemode else u":")
                .encode("utf-8")
            )
            return

        if self.wizard_stage == "color_answer":

            text = self.in_text.lower()
            if u"y" in text:
                self.wizard_stage = "codec"
                self.in_text = u""

            elif u"n" in text:
                self.wizard_stage = "vt100"
                self.in_text = u""

                self.say(
                    (
                        sep
                        + u"""
 what did you see instead?

   A:  "red, green, yellow, blue"
       -- either in just one colour
          or otherwise incorrect colours

   B:  "[1;31mred, [32mgreen, [33myellow, [34mblue[0m"

 press A or B&lm
 """
                    )
                    .replace(u"\n", u"\r\n")
                    .replace(
                        u"&lm", u", followed by [Enter]" if self.linemode else u":"
                    )
                    .encode("utf-8")
                )
                return

        if self.wizard_stage == "vt100":
            text = self.in_text.lower()
            if u"a" in text:
                # vt100 itself is probably fine, don't care
                self.wizard_stage = "codec"
                self.in_text = u""

            elif u"b" in text:
                self.wizard_stage = "vt100_warn"
                self.vt100 = False
                self.in_text = u""
                self.say(
                    (
                        top
                        + u"""
 WARNING:
   your client or terminal is not vt100 compatible!
   I will reduce features to a bare minimum,
   but this is gonna be bad regardless

   whenever the screen turns too glitchy
   you can press CTRL-L and Enter to redraw
   or run the command "/r" if that doesn't work

 press A to accept or Q to quit&lm
 """
                    )
                    .replace(u"\n", u"\r\n")
                    .replace(
                        u"&lm", u", followed by [Enter]" if self.linemode else u":"
                    )
                    .encode("utf-8")
                )
                return

        if self.wizard_stage == "vt100_warn":
            text = self.in_text.lower()
            if u"a" in text:
                self.wizard_stage = "codec"
                self.in_text = u""
            elif u"q" in text:
                self.host.part(self)

        AZ = u"ABCDEFGHIJKLMNOPQRSTUVWXYZ"

        if self.wizard_stage == "codec":
            self.wizard_stage = "codec_answer"
            self.in_text = u""

            def u8(tx):
                return tx.encode("utf-8", "backslashreplace")

            to_send = u8(
                (ftop + u'\n which line looks like  "hmr"  or  "dna" ?').replace(
                    u"\n", u"\r\n"
                )
            )

            nth = -1
            if not self.vt100:
                for nth, (enc, uni) in enumerate(
                    zip(self.codec_map[::2], self.codec_map[1::2])
                ):
                    to_send += u8(u"\r\n\r\n   {0}:  ".format(AZ[nth]))
                    try:
                        to_send += self.codec_uni[uni].encode(enc, "backslashreplace")
                    except:
                        to_send += u8("<codec not available>")
                to_send += u8(u"\r\n")
            else:
                for nth, (enc, uni) in enumerate(
                    zip(self.codec_map[::2], self.codec_map[1::2])
                ):
                    to_send += u8(u"\033[{0}H   {1}:  ".format(nth * 2 + 4, AZ[nth]))
                    try:
                        to_send += self.codec_uni[uni].encode(enc, "backslashreplace")
                    except:
                        to_send += u8("<codec not available>")
                    to_send += u8(u"\033[J\033[{0}H\033[J".format(nth * 2 + 5))

            to_send += u8(
                u"\r\n press {0}{1}\r\n".format(
                    u"/".join(AZ[: nth + 1]),
                    u", followed by [Enter]" if self.linemode else u":",
                )
            )

            self.say(to_send)
            return

        if self.wizard_stage == "codec_answer":
            text = self.in_text.lower()
            for n, letter in enumerate(AZ[: int(len(self.codec_map) / 2)].lower()):
                if letter in text:
                    self.set_codec(self.codec_map[n * 2])
                    if self.crlf == u"\r\n" and self.codec != "utf-8" and self.vt100:
                        self.wizard_stage = "texe"
                    else:
                        self.wizard_stage = "end"

                    break

        if self.wizard_stage == "texe":
            self.wizard_stage = "texe_answer"
            self.in_text = u""
            m = (
                top
                + u"""
 are you using telnet.exe on \033[1mWindows 7 \033[31mor newer\033[0m?

   Y:  Yes; this enables slowmo (network throttle)
       which avoids a rendering bug in telnet.exe

   N:  No, you are using another client
       (including \033[1;32mtelnet.exe on Win98 or WinXP\033[0m)

 press Y or N&lm
"""
            )
            self.say(
                m.replace(u"\n", u"\r\n")
                .replace(u"&lm", u", followed by [Enter]" if self.linemode else u":")
                .encode("utf-8")
            )
            return

        if self.wizard_stage == "texe_answer":
            text = self.in_text.lower()
            if u"y" in text:
                self.slowmo_tx = 1
                self.in_text = u""

            elif u"n" in text:
                self.in_text = u""

            else:
                return

            self.wizard_stage = "end"

        if self.wizard_stage == "end":
            self.save_config()
            if not COLORS:
                print(
                    "client conf:  stream={0}  vt100={1}  no-echo={2}  enc={3}\n           :  {4}  {5}  #{6}".format(
                        u"n" if self.linemode else u"Y",
                        u"Y" if self.vt100 else u"n",
                        u"n" if self.echo_on else u"Y",
                        self.codec,
                        self.user.nick,
                        self.adr[0],
                        len(self.host.clients),
                    )
                )
            else:
                print(
                    "client conf:  {0}stream  {1}vt100  {2}no-echo  \033[0m{3}\n           :  {4}  {5}  #{6}".format(
                        u"\033[1;31m" if self.linemode else u"\033[1;32m",
                        u"\033[32m" if self.vt100 else u"\033[31m",
                        u"\033[31m" if self.echo_on else u"\033[32m",
                        self.codec,
                        self.user.nick,
                        self.adr[0],
                        len(self.host.clients),
                    )
                )

            self.say(b"\n running speedtest... ")
            self.request_terminal_size("naws" if self.num_telnet_negotiations else None)

            self.host.unschedule_kick(self)
            self.wizard_stage = None
            self.in_text = u""
            self.in_text_full = u""
            self.user.create_channels()
            if not self.slowmo_tx:
                self.world.cserial += 1

    def check_correct_iface(self, next_stage):
        self.wizard_stage = next_stage

        if self.iface_confirmed or not self.host.other_if:
            return True

        self.iface_confirmed = True

        to_say = None
        ftop = u"\n" * 20 + u"\033[H\033[J"
        top = ftop + u" [ r0c configurator ]\n"

        if (
            self.__class__.__name__ == "TelnetClient"
            and self.num_telnet_negotiations < 1
        ):
            print("client negs:  {0} bad_if".format(self.num_telnet_negotiations))
            to_say = (
                top
                + u"""
 your client is not responding to negotiations.

   if you are NOT using Telnet,
   please connect to port {0}
"""
            ).format(self.host.other_if)

        elif (
            self.__class__.__name__ == "NetcatClient"
            and self.num_telnet_negotiations > 0
        ):
            print("client negs:  {0} bad_if".format(self.num_telnet_negotiations))
            to_say = (
                top
                + u"""
 your client has sent {1} Telnet negotiation{2}.

   if you are using Telnet,
   please connect to port {0}
"""
            ).format(
                self.host.other_if,
                self.num_telnet_negotiations,
                u"s" if self.num_telnet_negotiations != 1 else u"",
            )

        if to_say:
            to_say += u"""
 are you sure the port is correct?

   Y:  yes, ignore and continue
   N:  no, quit

 press Y or N, followed by [Enter]
"""

            self.in_text = u""
            self.wizard_stage = "iface_then_" + next_stage
            self.say(to_say.replace(u"\n", u"\r\n").encode("utf-8"))
            return False

        print("client negs:  {0} ok".format(self.num_telnet_negotiations))
        return True

    def read_cb(self, full_redraw, growth):
        # only called by (telnet|netcat).py:handle_read,
        # only called within locks on self.world.mutex

        # self.wizard_stage = None
        if self.wizard_stage is not None:
            self.conf_wizard(growth)

            if self.wizard_stage is not None:
                return

            full_redraw = True

        old_cursor = self.linepos
        mark_read = False

        esc_scan = True
        while esc_scan:
            esc_scan = False

            aside = u""
            for nth, ch in enumerate(self.in_text):

                was_esc = None
                if aside and aside in self.esc_tab:
                    # text until now is an incomplete escape sequence;
                    # if the new character turns into an invalid sequence
                    # we'll turn the old one into a plaintext string
                    was_esc = aside

                aside += ch
                csi = (aside == u"\033") or aside.startswith(u"\033[")
                bad_csi = csi and len(aside) > 12

                if aside not in self.esc_tab and (bad_csi or not csi):

                    if bad_csi:
                        # escape the ESC and take it from the top:
                        # there might be esc_tab sequences within
                        self.in_text = u"[ESC]" + aside[1:] + self.in_text[nth + 1 :]
                        esc_scan = True
                        break

                    if was_esc:
                        # new character made the escape sequence invalid;
                        # print old buffer as plaintext and create a new
                        # escape sequence buffer for just the new char

                        if ch in self.esc_tab:
                            # ...but only if the new character is
                            # potentially the start of a new esc.seq.
                            aside = was_esc
                        else:
                            # in this case it isn't
                            was_esc = False

                    self.linebuf = (
                        self.linebuf[: self.linepos]
                        + Util.sanitize_ctl_codes(aside)
                        + self.linebuf[self.linepos :]
                    )
                    self.linepos += len(aside)

                    self.msg_not_from_hist = True
                    self.msg_hist_n = None
                    self.tabcomplete_end()

                    if was_esc:
                        aside = ch
                    else:
                        aside = u""

                else:
                    # this is an escape sequence; handle it
                    act = False
                    if aside in self.esc_tab:
                        act = self.esc_tab[aside]

                    if not act:
                        if not csi:
                            continue

                        m = self.re_cursor_pos.match(aside)
                        if not m:
                            continue

                        now = time.time()
                        if not self.first_dsr:
                            self.first_dsr = now
                            if self.pending_size_request:
                                t = "  dsr reply:  {0:.2f} sec"
                                print(t.format(now - self.pending_size_request))

                        elif not self.bps and not self.linemode:
                            diff = 0.001 + now - self.first_dsr
                            self.bps = int(1120 * 1.25 / diff)
                            # 1.25 = magic coeff. from ffmpeg -re
                            t = " client bps:  {0} ({1:.3f}s)"
                            print(t.format(self.bps, diff))
                            self.adapt_to_modem()

                        sh, sw = [int(x) for x in m.groups()]
                        self.pending_size_request = 0.0
                        self.handshake_sz = True

                        naws = self.size_request_action == "naws"
                        if (self.w != sw or self.h != sh) and (
                            not naws or sw > self.w + 128 or sh > self.h + 128
                        ):
                            if naws:
                                t = " naws-patch:  {0}x{1} => {2}x{3}"
                                print(t.format(self.w, self.h, sw, sh))

                            full_redraw = True
                            self.set_term_size(sw, sh)

                        aside = aside[len(m.group(0)) :]
                        continue

                    if act in self.read_markers:
                        mark_read = True

                    if self.ar.dbg:
                        print(" escape seq:  {0} = {1}".format(Util.b2hex(aside), act))

                    if self.tc_nicks and act != "tab":
                        self.tabcomplete_end()

                    hist_step = 0
                    chan_shift = 0

                    aside = u""
                    if act == "cl":
                        self.linepos -= 1
                        if self.linepos < 0:
                            self.linepos = 0
                    elif act == "cr":
                        self.linepos += 1
                        if self.linepos > len(self.linebuf):
                            self.linepos = len(self.linebuf)
                    elif act == "cu":
                        hist_step = -1
                        if self.echo_on:
                            self.need_full_redraw = True
                    elif act == "cd":
                        hist_step = 1
                    elif act == "home":
                        self.linepos = 0
                    elif act == "end":
                        self.linepos = len(self.linebuf)
                    elif act == "bs":
                        if self.linepos > 0:
                            self.linebuf = (
                                self.linebuf[: self.linepos - 1]
                                + self.linebuf[self.linepos :]
                            )
                            self.linepos -= 1
                    elif act == "ret":
                        self.last_beep = time.time() - 0.9
                        if self.echo_on:
                            self.need_full_redraw = True
                        if self.linebuf:
                            # add this to the message/command ("input") history
                            if not self.msg_hist or self.msg_hist[-1] != self.linebuf:
                                self.msg_hist.append(self.linebuf)

                            self.msg_not_from_hist = False
                            self.pending_size_request = 0.0

                            single = self.linebuf.startswith(u"/")
                            double = self.linebuf.startswith(u"//")
                            if single and not double:
                                # this is a command
                                self.user.exec_cmd(self.linebuf[1:])
                            else:
                                if double:
                                    # remove escape character
                                    self.linebuf = self.linebuf[1:]

                                nch = self.user.active_chan.nchan
                                self.world.send_chan_msg(
                                    self.user.nick,
                                    nch,
                                    Util.convert_color_codes(self.linebuf),
                                )
                                for ircb in nch.ircb:
                                    t = Util.color_to_irc(self.linebuf)
                                    ircb.net.say(
                                        "PRIVMSG #%s :<%s> %s"
                                        % (ircb.irc_cname, self.user.nick, t)
                                    )

                            self.msg_hist_n = None
                            self.linebuf = u""
                            self.linepos = 0

                    elif act == "pgup" or act == "pgdn":

                        steps = self.h - 4
                        if self.scroll_i is not None:
                            steps = self.scroll_i
                        elif self.scroll_f is not None:
                            steps = int(steps * self.scroll_f)
                        else:
                            print("no scroll size?!")

                        if act == "pgup":
                            steps *= -1

                        self.scroll_cmd += steps

                    elif act == "redraw":
                        self.user.exec_cmd("r")
                    elif act == "view":
                        self.user.exec_cmd("v")
                    elif act == "prev-chan":
                        chan_shift = -1
                    elif act == "next-chan":
                        chan_shift = +1
                    elif act == "alt-tab":
                        self.user.exec_cmd("a")
                    elif act == "tab":
                        self.tabcomplete()
                    elif act == "del":
                        self.linepos += 1
                        if self.linepos > len(self.linebuf):
                            self.linepos = len(self.linebuf)
                        if self.linepos > 0:
                            self.linebuf = (
                                self.linebuf[: self.linepos - 1]
                                + self.linebuf[self.linepos :]
                            )
                            self.linepos -= 1
                    else:
                        print("unimplemented action: {0}".format(act))

                    if chan_shift != 0:
                        i = self.user.chans.index(self.user.active_chan) + chan_shift
                        if i < 0:
                            i = len(self.user.chans) - 1
                        if i >= len(self.user.chans):
                            i = 0
                        self.user.new_active_chan = self.user.chans[i]

                    elif hist_step == 0:
                        self.msg_hist_n = None

                    else:
                        if self.msg_hist_n is None:
                            if hist_step < 0:
                                self.msg_hist_n = len(self.msg_hist) - 1
                        else:
                            self.msg_hist_n += hist_step

                        if self.msg_hist_n is not None:
                            if self.msg_hist_n < 0 or self.msg_hist_n >= len(
                                self.msg_hist
                            ):
                                self.msg_hist_n = None

                        # capture unfinished entries so they can be resumed
                        if self.linebuf and self.msg_not_from_hist:
                            self.msg_hist.append(self.linebuf)

                        self.msg_not_from_hist = False

                        if self.msg_hist_n is None:
                            self.linebuf = u""
                        else:
                            self.linebuf = self.msg_hist[self.msg_hist_n]
                        self.linepos = len(self.linebuf)
        if aside:
            if self.ar.dbg:
                print(
                    "need more data for {0} runes: {1}".format(
                        len(aside), Util.b2hex(aside)
                    )
                )
            self.in_text = aside
        else:
            self.in_text = u""

        if self.w < 20 or self.h < 4:
            msg = "x"
            for cand in self.msg_too_small:
                # print('{0} <= {1}'.format(len(cand), self.w))
                if len(cand) <= self.w:
                    msg = cand
                    break
            y = int(self.h / 3)
            x = int((self.w - len(msg)) / 2)
            x += 1
            y += 1
            now = time.time()
            if now - self.last_2smol > 1:
                print("2smol @ {0} {1}".format(x, y))
                self.last_2smol = now
            msg = u"\033[H\033[1;37;41m\033[J\033[{0};{1}H{2}\033[0m".format(y, x, msg)
            self.say(msg.encode(self.codec, "backslashreplace"))
            self.too_small = True
            return

        if self.size_request_action and not self.pending_size_request:
            if self.size_request_action == "redraw":
                full_redraw = True

            if self.too_small:
                self.say(b"\033[H\033[J")  # clear rsod asap
                full_redraw = True

            self.size_request_action = None

        self.too_small = False

        if self.ar.dbg:
            if self.dead:
                print("CANT_ANSWER:  dead")
            if not self.handshake_sz:
                print("CANT_ANSWER:  handshake_sz")
            if not self.handshake_world:
                print("CANT_ANSWER:  handshake_world")

        if not self.dead:
            with self.world.mutex:
                if full_redraw:
                    self.need_full_redraw = True

                if self.handshake_sz:
                    self.refresh(old_cursor != self.linepos, mark_read)

    def tabcomplete(self):
        if self.tc_nicks:
            self.tabcomplete_cycle()
        else:
            self.tabcomplete_init()

    def tabcomplete_init(self):
        try:
            chan = self.user.active_chan.nchan
        except:
            return

        txt = self.linebuf[: self.linepos]
        ofs = txt.rfind(u" ")
        if ofs >= 0:
            prefix = txt[ofs + 1 :].lower()
        else:
            prefix = txt.lower()

        self.tc_nicks = [prefix]
        for usr, ts in sorted(
            chan.user_act_ts.items(), key=operator.itemgetter(1), reverse=True
        ):
            if usr != self.user.nick and usr.lower().startswith(prefix):
                self.tc_nicks.append(usr)

        if len(self.tc_nicks) == 1:
            self.tc_nicks = None
            return

        self.tc_msg_pre = self.linebuf[: self.linepos - len(prefix)]
        self.tc_msg_post = self.linebuf[self.linepos :]
        self.tc_n = 0

        self.tabcomplete_cycle()

    def tabcomplete_cycle(self):
        self.tc_n += 1
        if self.tc_n >= len(self.tc_nicks):
            self.tc_n = 0

        if not self.tc_msg_pre:
            nick_suffix = u": "
        else:
            nick_suffix = u" "

        nick = self.tc_nicks[self.tc_n]
        if nick == u"":
            nick_suffix = u""

        self.linebuf = self.tc_msg_pre + nick + nick_suffix
        self.linepos = len(self.linebuf)
        self.linebuf += self.tc_msg_post

    def tabcomplete_end(self):
        self.tc_nicks = None
        self.tc_post = None
        self.tc_pre = None
