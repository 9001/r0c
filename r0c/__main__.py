#!/usr/bin/env python3
# coding: utf-8
from __future__ import print_function
from .__version__ import S_VERSION
from .__init__ import EP, WINDOWS, COLORS, unicode
from . import util as Util
from . import inetcat as Inetcat
from . import itelnet as Itelnet
from . import world as World
from .irc import IRC_Net

import os
import sys
import time
import signal
import select
import threading
from datetime import datetime

print = Util.print
UTC = Util.UTC


"""r0c.py: retr0chat Telnet/Netcat Server"""
__author__ = "ed <a@ocv.me>"
__credits__ = ["stackoverflow.com"]
__license__ = "MIT"
__copyright__ = 2018
__url__ = "https://github.com/9001/r0c"


if "r0c" not in sys.modules:
    print(
        "\r\n  retr0chat must be launched as a module.\r\n  in the project root, run this:\r\n\r\n    python3 -m r0c\r\n"
    )
    sys.exit(1)


def optgen(ap, pwd):
    ac = ap
    u = unicode
    pt, pn = [23, 531] if WINDOWS or not os.getuid() else [2323, 1531]

    # fmt: off
    ac.add_argument("-i", metavar="IP", type=u, default="0.0.0.0", help="address to listen on")
    ac.add_argument("-pt", metavar="PORT", type=int, default=pt, help="telnet port (disable with 0)")
    ac.add_argument("-pn", metavar="PORT", type=int, default=pn, help="netcat port (disable with 0)")
    ac.add_argument("-tpt", metavar="PORT", type=int, default=0, help="TLS telnet port, e.g. 2424 (disable with 0)")
    ac.add_argument("-tpn", metavar="PORT", type=int, default=0, help="TLS netcat port, e.g. 1515 (disable with 0)")
    ac.add_argument("-pw", metavar="PWD", type=u, default=pwd, help="admin password")
    ac.add_argument("--ara", action="store_true", help="admin-access requires auth (even for localhost)")
    ac.add_argument("--nsalt", metavar="TXT", type=u, default="lammo/", help="salt for generated nicknames based on IP")
    ac.add_argument("--proxy", metavar="A,A", type=u, default="", help="comma-sep. list of IPs which are relays to disable config persistence on")

    ac = ap.add_argument_group("logging")
    ac.add_argument("--log-rx", action="store_true", help="log incoming traffic from clients")
    ac.add_argument("--log-tx", action="store_true", help="log outgoing traffic to clients")
    ac.add_argument("--rot-msg", metavar="N", type=int, default=131072, help="max num msgs per logfile")

    ac = ap.add_argument_group("tls")
    ac.add_argument("--ciphers", metavar="S", type=u, default="", help="specify allowed TLS ciphers; python default if unset")
    ac.add_argument("--tls-min", metavar="S", type=u, default="", help="oldest ver to allow; SSLv3 TLSv1 TLSv1_1 TLSv1_2 TLSv1_3")
    ac.add_argument("--old-tls", action="store_true", help="support old clients (centos6/powershell), bad ciphers")

    ac = ap.add_argument_group("irc-bridge")
    ac.add_argument("--ircn", metavar="TXT", type=u, action="append", help='connect to an irc server; TXT is: "netname,hostname,[+]port,nick[,username[,password]]" (if password contains "," then use ", " as separator)')
    ac.add_argument("--ircb", metavar="N,C,L", type=u, action="append", help="bridge irc-netname N, irc-channel #C with r0c-channel #L")
    ac.add_argument("--i-rate", metavar="B,R", type=u, default="4,2", help="rate limit; burst of B messages, then R seconds between each")
    ac.add_argument("--ctcp-ver", metavar="S", type=u, default="r0c v%s" % (S_VERSION), help="reply to CTCP VERSION")

    ac = ap.add_argument_group("ux")
    ac.add_argument("--no-all", action="store_true", help="default-disable @all / @everyone")
    ac.add_argument("--motd", metavar="PATH", type=u, default="", help="file to include at the end of the welcome-text (can be edited at runtime)")

    ac = ap.add_argument_group("perf")
    ac.add_argument("--hist-rd", metavar="N", type=int, default=65535, help="max num msgs to load from disk when joining a channel")
    ac.add_argument("--hist-mem", metavar="N", type=int, default=98303, help="max num msgs to keep in channel scrollback")
    ac.add_argument("--hist-tsz", metavar="N", type=int, default=16384, help="num msgs to discard when chat exceeds hist-mem")

    ac = ap.add_argument_group("debug")
    ac.add_argument("--dbg", action="store_true", help="show negotiations etc")
    ac.add_argument("--dbg-irc", action="store_true", help="show irc traffic")
    ac.add_argument("--hex-rx", action="store_true", help="print incoming traffic from clients")
    ac.add_argument("--hex-tx", action="store_true", help="print outgoing traffic to clients")
    ac.add_argument("--hex-lim", metavar="N", type=int, default=128, help="filter packets larger than N bytes from being hexdumped")
    ac.add_argument("--hex-w", metavar="N", type=int, default=16, help="width of the hexdump, in bytes per line, mod-8")
    ac.add_argument("--dev", action="store_true", help="enable dangerous shortcuts (devmode)")
    ac.add_argument("--thr-mon", action="store_true", help="start monitoring threads on ctrl-c")
    if WINDOWS:
        ac.add_argument("--reuseaddr", action="store_true", help="allow rapid server restart (DANGER: lets you accidentally start multiple instances)")
    ac.add_argument("--linemode", action="store_true", help="force clients into linemode (to debug linemode UI)")
    ac.add_argument("--bench", action="store_true", help="dump statistics every 2 sec")
    # fmt: on


class Fargparse(object):
    def __init__(self):
        pass

    def add_argument_group(self, *a, **ka):
        return self

    def add_argument(self, opt, default=False, **ka):
        setattr(self, opt.lstrip("-").replace("-", "_"), default)


def run_fap(argv, pwd):
    ap = Fargparse()
    optgen(ap, pwd)

    if u"-h" in unicode(([""] + argv)[-1]):
        print()
        print("arg 1: Telnet port (0=disable), default: {0}".format(ap.pt))
        print("arg 2: NetCat port (0=disable), default: {0}".format(ap.pn))
        print("arg 3: admin password, default: {0}".format(ap.pw))
        print()
        sys.exit(0)

    try:
        setattr(ap, "pt", int(argv[1]))
        setattr(ap, "pn", int(argv[2]))
        setattr(ap, "pw", unicode(argv[3]))
    except IndexError:
        pass

    return ap


try:
    import argparse

    class RiceFormatter(argparse.HelpFormatter):
        def _get_help_string(self, action):
            """
            same as ArgumentDefaultsHelpFormatter(HelpFormatter)
            except the help += [...] line now has colors
            """
            fmt = "\033[36m (default: \033[35m%(default)s\033[36m)\033[0m"
            if not COLORS:
                fmt = " (default: %(default)s)"

            help = action.help
            if "%(default)" not in action.help:
                if action.default is not argparse.SUPPRESS:
                    defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
                    if action.option_strings or action.nargs in defaulting_nargs:
                        help += fmt
            return help

        def _fill_text(self, text, width, indent):
            """same as RawDescriptionHelpFormatter(HelpFormatter)"""
            return "".join(indent + line + "\n" for line in text.splitlines())

    class Dodge11874(RiceFormatter):
        def __init__(self, *args, **kwargs):
            kwargs["width"] = 9003
            super(Dodge11874, self).__init__(*args, **kwargs)

    def run_ap(argv, pwd):
        throw = False
        for formatter in [RiceFormatter, Dodge11874]:
            try:
                ap = argparse.ArgumentParser(formatter_class=formatter, prog="r0c")

                optgen(ap, pwd)
                return ap.parse_args(args=argv[1:])
            except AssertionError:
                if throw:
                    raise
                throw = True

except:
    run_ap = run_fap


class Core(object):
    def __init__(self):
        pass

    def start(self, argv=None):
        if WINDOWS and COLORS:
            os.system("rem")  # best girl

        if argv is None:
            argv = sys.argv

        for d in ["pm", "chan", "wire"]:
            try:
                os.makedirs(EP.log + d)
            except:
                pass

        print("  *  r0c {0}, py {1}".format(S_VERSION, Util.host_os()))

        pwd = "hunter2"
        pwd_file = os.path.join(EP.app, "password.txt")
        if os.path.isfile(pwd_file):
            print("  *  Password from " + pwd_file)
            with open(pwd_file, "rb") as f:
                pwd = f.read().decode("utf-8").strip()

        # old argv syntax compat
        try:
            _ = int(argv[1])
            rap = run_fap
        except:
            rap = run_ap

        ar = self.ar = rap(argv, pwd)  # type: argparse.Namespace
        ar.ircn = ar.ircn or []
        ar.ircb = ar.ircb or []
        ar.i_rate_b, ar.i_rate_s = [float(x) for x in ar.i_rate.split(",")]
        ar.proxy = ar.proxy.split(",")
        if "127.0.0.1" in ar.proxy or "::1" in ar.proxy:
            t = "\033[33mWARNING: you have localhost in --proxy, you probably want --ara too\033[0m"
            print(t)

        Util.HEX_WIDTH = ar.hex_w
        Itelnet.init(ar)

        cert = EP.app + "cert.pem"
        if ar.tpt or ar.tpn:
            print("  *  Loading certificate {0}".format(cert))
            import ssl

            if not os.path.exists(cert):
                Util.builtins.print(
                    """\033[1;31m
tls was requested, but certificate not found at {0}pem
create the certificate (replacing "r0c.int" with the server's external ip or fqdn) and try again:

printf '%s\\n' GK . . . . r0c.int . | openssl req -newkey rsa:2048 -sha256 -keyout "{0}key" -nodes -x509 -days 365 -out "{0}crt" && cat "{0}key" "{0}crt" > "{0}pem"
\033[0m""".format(
                        EP.app + "cert."
                    )
                )
                raise Exception("TLS certificate not found")

            if ar.old_tls:
                ar.tls_min = ar.tls_min or "TLSv1"
                ar.ciphers = "EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH:ECDHE-RSA-AES128-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA128:DHE-RSA-AES128-GCM-SHA384:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES128-GCM-SHA128:ECDHE-RSA-AES128-SHA384:ECDHE-RSA-AES128-SHA128:ECDHE-RSA-AES128-SHA:ECDHE-RSA-AES128-SHA:DHE-RSA-AES128-SHA128:DHE-RSA-AES128-SHA128:DHE-RSA-AES128-SHA:DHE-RSA-AES128-SHA:ECDHE-RSA-DES-CBC3-SHA:EDH-RSA-DES-CBC3-SHA:AES128-GCM-SHA384:AES128-GCM-SHA128:AES128-SHA128:AES128-SHA128:AES128-SHA:AES128-SHA:DES-CBC3-SHA:HIGH:!aNULL:!eNULL:!EXPORT:!DES:!MD5:!PSK:!RC4"

        for srv, port in [
            ["Telnet", ar.pt],
            ["NetCat", ar.pn],
            ["TLS-Telnet", ar.tpt],
            ["TLS-NetCat", ar.tpn],
        ]:
            if port:
                print("  *  {0} server on port {1}".format(srv, port))
            else:
                print("  *  {0} server disabled".format(srv))

        if ar.pw == "hunter2":
            print("\033[1;31m")
            print("  using default password '{0}'".format(ar.pw))
            print("  change it with argument -pw or save it here:")
            print("  " + pwd_file)
            print("\033[0m")

        print("  *  Logs at " + EP.log)

        self.stopping = 0
        self.threadmon = False
        self.shutdown_flag = threading.Event()
        Util.py26_threading_event_wait(self.shutdown_flag)

        print("  *  Capturing ^C")
        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, self.signal_handler)

        print("  *  Creating world")
        self.world = World.World(self)

        self.servers = []
        for name, ctor, p1, p2, tls in [
            ["Telnet", Itelnet.TelnetServer, ar.pt, ar.pn, False],
            ["NetCat", Inetcat.NetcatServer, ar.pn, ar.pt, False],
            ["TLS-Telnet", Itelnet.TelnetServer, ar.tpt, ar.tpn, True],
            ["TLS-NetCat", Inetcat.NetcatServer, ar.tpn, ar.tpt, True],
        ]:
            if not p1:
                continue

            print("  *  Starting {0} server".format(name))
            srv = ctor(ar.i, p1, self.world, p2, tls)
            self.servers.append(srv)

        print("  *  Loading user configs")
        for server in self.servers:
            server.load_configs()

        print("  *  Starting push driver")
        self.push_thr = threading.Thread(
            target=self.push_worker,
            args=(self.world, self.servers),
            name="push",
        )
        # self.push_thr.daemon = True
        self.push_thr.start()

        for irc_cfg in ar.ircn:
            self.add_irc_net(irc_cfg)

        for irc_cfg in ar.ircb:
            self.add_irc_ch(irc_cfg)

        for ircn in self.world.ircn.values():
            ircn.connect()

        print("  *  Running")
        self.select_thr = Util.Daemon(self.select_worker, "selector")

        return True

    def add_irc_net(self, scfg):
        acfg = scfg.split(", " if ", " in scfg else ",")
        try:
            netname, hostname, sport, nick = acfg[:4]
            netname = netname.lower()
        except:
            raise Exception("invalid argument to --ircn: [%s]" % (scfg,))

        username = ""
        password = ""
        try:
            username = acfg[4]
            password = acfg[5]
        except:
            pass

        port = int(sport.lstrip("+"))
        tls = sport.startswith("+")

        print("  *  Adding irc-net %s (%s:%s)" % (netname, hostname, sport))
        self.world.ircn[netname] = IRC_Net(
            self.world, netname, hostname, port, tls, nick, username, password
        )

    def add_irc_ch(self, scfg):
        try:
            netname, irc_cname, r0c_cname = scfg.lower().split(",")
        except:
            raise Exception("invalid argument to --ircb: [%s]" % (scfg,))

        if netname not in self.world.ircn:
            t = "ircnet '%s' (mentioned in --ircb %s) not defined by --ircn"
            raise Exception(t % (netname, scfg))

        t = "  *  Adding irc-bridge <%s:#%s> #%s"
        print(t % (netname, irc_cname, r0c_cname))

        ircn = self.world.ircn[netname]
        ircn.addchan(irc_cname, r0c_cname)

    def run(self):
        print("  *  r0c is up  ^^,")

        if not self.ar.bench:
            try:
                timeout = 69
                if WINDOWS:
                    # ctrl-c does not raise
                    timeout = 0.69

                while not self.shutdown_flag.wait(timeout):
                    pass
            except:
                pass
        else:
            last_joins = 0
            last_parts = 0
            last_messages = 0
            while not self.shutdown_flag.is_set():
                for n in range(20):
                    if self.shutdown_flag.is_set():
                        break
                    time.sleep(0.1)

                print(
                    "{0:.3f}  j {1}  p {2}  m {3}  d {4},{5},{6}".format(
                        time.time(),
                        self.world.num_joins,
                        self.world.num_parts,
                        self.world.num_messages,
                        self.world.num_joins - last_joins,
                        self.world.num_parts - last_parts,
                        self.world.num_messages - last_messages,
                    )
                )

                last_joins = self.world.num_joins
                last_parts = self.world.num_parts
                last_messages = self.world.num_messages

        # termiante refresh_chans
        self.world.dirty_ch = {}
        self.world.dirty_flag.set()

        with self.world.mutex:
            pass

        print("  *  saving user configs")
        for server in self.servers:
            server.save_configs()

        print("  *  terminating world")
        self.world.shutdown()

        print("  *  selector cleanup")
        for server in self.servers:
            server.srv_sck.close()

        print("  *  r0c is down")
        return True

    def select_worker(self):
        srvs = {}
        for iface in self.servers:
            srvs[iface.srv_sck] = iface

        t_fast = 0.5 if self.ar.ircn else 1

        sn = -1
        sc = {}
        slow = {}  # sck:cli
        fast = {}
        nfast = 0
        dirty_ref = 0
        next_slow = 0
        timeout = None
        while not self.shutdown_flag.is_set():
            nsn = self.world.cserial
            if sn != nsn:
                sn = nsn
                sc = {}
                slow = {}
                fast = {}
                for srv in self.servers:
                    for c in srv.clients:
                        if c.slowmo_tx or (c.wizard_stage is not None and not c.is_bot):
                            slow[c.sck] = c
                        else:
                            fast[c.sck] = c

                        sc[c.sck] = c

                timeout = 0.2 if slow else t_fast if fast else 69

            want_tx = [s for s, c in fast.items() if c.writable()]
            want_rx = [s for s, c in sc.items() if c.readable()]
            want_rx += list(srvs.keys())

            now = time.time()
            if slow and now >= next_slow:
                next_slow = now + 0.18

                for c in slow.values():
                    if c.slowmo_skips:
                        c.slowmo_skips -= 1

                want_tx += [
                    s for s, c in slow.items() if c.writable() and not c.slowmo_skips
                ]

            if dirty_ref != self.world.last_dirty or self.world.dirty_flag.is_set():
                dirty_ref = self.world.last_dirty
                nfast = 0
            else:
                nfast += 1

            ct = 0.09 if nfast < 2 else timeout

            try:
                # print("sel", len(want_rx), len(want_tx), ct)
                rxs, txs, _ = select.select(want_rx, want_tx, [], ct)
                if self.stopping:
                    break

                with self.world.mutex:
                    if sn != self.world.cserial:
                        continue

                    for s in rxs:
                        if s in srvs:
                            srvs[s].handle_accept()
                        else:
                            sc[s].handle_read()

                    for s in txs:
                        sc[s].handle_write()

            except Exception as ex:
                if "Bad file descriptor" in str(ex):
                    # print('osx bug ignored')
                    continue
                Util.whoops()

    def push_worker(self, world, ifaces):
        last_action_ts = time.time()
        last_its = None
        last_date = None
        c_refresh = 0
        while not self.shutdown_flag.is_set():
            if any(srv.clients for srv in self.servers):
                # sleep until the start of the next mod5 utc second
                while True:
                    ts = time.time()
                    its = int(ts / 5) * 5
                    if its != last_its:
                        last_its = its
                        break
                    if ts - its < 4.99:
                        if self.shutdown_flag.wait((5 - (ts - its))):
                            break
                    else:
                        time.sleep(0.02)
            else:
                # less precision if there's nobody connected
                self.world.dirty_flag.wait(100)
                ts = time.time()
                last_its = int(ts / 5) * 5

            if c_refresh < 6:
                c_refresh += 1
            else:
                c_refresh = 1

            with world.mutex:
                if self.stopping:
                    break

                zd = datetime.fromtimestamp(ts, UTC)
                date = u"%04d-%02d-%02d" % (zd.year, zd.month, zd.day)

                if date != last_date:
                    if last_date:
                        world.broadcast_message(
                            u"\033[36mday changed to \033[1m{0}".format(date), False
                        )
                    last_date = date

                for iface in ifaces:
                    for client in iface.clients:
                        if client.handshake_sz and not c_refresh % client.m_refresh:
                            client.refresh(False)

                    # print('next scheduled kick: {0}'.format('x' if iface.next_scheduled_kick is None else iface.next_scheduled_kick - ts))

                    if (
                        iface.next_scheduled_kick is not None
                        and iface.next_scheduled_kick <= ts
                    ):
                        to_kick = []
                        next_min = None
                        for sch in iface.scheduled_kicks:
                            if sch[0] <= ts:
                                to_kick.append(sch)
                            else:
                                if next_min is None or next_min > sch[0]:
                                    next_min = sch[0]

                        for sch in to_kick:
                            timeout, remote, msg = sch
                            iface.scheduled_kicks.remove(sch)
                            if remote in iface.clients:
                                if msg is None:
                                    iface.part(remote)
                                else:
                                    iface.part(remote, False)
                                    print(msg)

                        iface.next_scheduled_kick = next_min

                if ts - last_action_ts >= 600:
                    last_action_ts = ts

                    # flush client configs
                    for iface in ifaces:
                        iface.save_configs()

                        # flush wire logs
                        if self.ar.log_rx or self.ar.log_tx:
                            for client in iface.clients:
                                if client.wire_log:
                                    try:
                                        client.wire_log.flush()
                                    except:
                                        Util.whoops()

                    # flush chan logs
                    for chan_list in [world.pub_ch, world.priv_ch]:
                        for chan in chan_list:
                            if chan.log_fh:
                                try:
                                    chan.log_fh.flush()
                                except:
                                    Util.whoops()

        print("  *  terminated push_worker")

    def shutdown(self):
        # monitor_threads()
        self.stopping += 1
        if self.stopping >= 3:
            os._exit(1)

        self.shutdown_flag.set()

    def signal_handler(self, sig, frame):
        if self.ar.thr_mon and not self.threadmon:
            self.threadmon = True
            Util.monitor_threads()
        else:
            self.shutdown()


def start_r0c(argv):
    core = Core()
    try:
        if core.start(argv):
            return core.run()
    except SystemExit:
        raise
    except:
        Util.whoops()
        os._exit(1)


def main(argv=None):
    mode = "normal"
    # mode = "profiler"
    # mode = 'test-ansi-annotation'
    # test_hexdump()

    if mode == "normal":
        if not start_r0c(argv):
            sys.exit(1)


"""
    if mode == "profiler":
        print("  *  PROFILER ENABLED")
        statfile = "profiler-results"
        import yappi

        yappi.start()
        start_r0c(argv)
        yappi.stop()

        fn_stats = yappi.get_func_stats()
        thr_stats = yappi.get_thread_stats()

        print()
        for ext in ["pstat", "callgrind", "ystat"]:
            print("writing {0}.{1}".format(statfile, ext))
            fn_stats.save("{0}.{1}".format(statfile, ext), type=ext)

        with open("{0}.func".format(statfile), "w") as f:
            fn_stats.print_all(out=f)

        with open("{0}.thr".format(statfile), "w") as f:
            thr_stats.print_all(out=f)

        print("\n\n{0}\n  func stats\n{0}\n".format("-" * 72))
        fn_stats.print_all()

        print("\n\n{0}\n  thread stats\n{0}\n".format("-" * 72))
        thr_stats.print_all()

    if mode == "test-ansi-annotation":
        Util.test_ansi_annotation()
"""


if __name__ == "__main__":
    main()
