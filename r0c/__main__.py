#!/usr/bin/env python3
# coding: utf-8
from __future__ import print_function
from .__version__ import S_VERSION
from .__init__ import EP, WINDOWS, COLORS, unicode
from . import util as Util
from . import inetcat as Inetcat
from . import itelnet as Itelnet
from . import world as World

import os
import sys
import time
import signal
import select
import threading
from datetime import datetime

print = Util.print


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
    ac.add_argument("-pt", type=int, default=pt, help="telnet port (disable with 0)")
    ac.add_argument("-pn", type=int, default=pn, help="netcat port (disable with 0)")
    ac.add_argument("-pw", metavar="PWD", type=u, default=pwd, help="admin password")
    ac.add_argument("--nsalt", metavar="TXT", type=u, default="lammo/", help="salt for generated nicknames based on IP")

    ac = ap.add_argument_group("logging")
    ac.add_argument("--log-rx", action="store_true", help="log incoming traffic from clients")
    ac.add_argument("--log-tx", action="store_true", help="log outgoing traffic to clients")
    ac.add_argument("--rot-msg", metavar="N", type=int, default=131072, help="max num msgs per logfile")

    ac = ap.add_argument_group("perf")
    ac.add_argument("--hist-rd", metavar="N", type=int, default=65535, help="max num msgs to load from disk when joining a channel")
    ac.add_argument("--hist-mem", metavar="N", type=int, default=98303, help="max num msgs to keep in channel scrollback")
    ac.add_argument("--hist-tsz", metavar="N", type=int, default=16384, help="num msgs to discard when chat exceeds hist-mem")

    ac = ap.add_argument_group("debug")
    ac.add_argument("--dbg", action="store_true", help="show negotiations etc")
    ac.add_argument("--hex-rx", action="store_true", help="print incoming traffic from clients")
    ac.add_argument("--hex-tx", action="store_true", help="print outgoing traffic to clients")
    ac.add_argument("--hex-lim", metavar="N", type=int, default=128, help="filter packets larger than N bytes from being hexdumped")
    ac.add_argument("--hex-w", metavar="N", type=int, default=16, help="width of the hexdump, in bytes per line, mod-8")
    ac.add_argument("--thr-mon", action="store_true", help="start monitoring threads on ctrl-c")
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

    if "-h" in unicode(argv + [""])[1]:
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
    except:
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

        ar = self.ar = rap(argv, pwd)
        Util.HEX_WIDTH = ar.hex_w
        Itelnet.init(ar)

        for srv, port in [["Telnet", ar.pt], ["NetCat", ar.pn]]:
            if port:
                print("  *  {0} server on port {1}".format(srv, port))
            else:
                print("  *  {0} server disabled".format(srv))

        if ar.pw == "hunter2":
            print("\033[1;31m")
            print("  using the default password;")
            print("  change it with argument -pw")
            print("  or save it here: " + pwd_file)
            print("\033[0m")

        print("  *  Logs at " + EP.log)
        Util.compat_chans_in_root()

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
        if ar.pt:
            print("  *  Starting Telnet server")
            self.telnet_server = Itelnet.TelnetServer(ar.i, ar.pt, self.world, ar.pn)
            self.servers.append(self.telnet_server)

        if ar.pn:
            print("  *  Starting NetCat server")
            self.netcat_server = Inetcat.NetcatServer(ar.i, ar.pn, self.world, ar.pt)
            self.servers.append(self.netcat_server)

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

        print("  *  Running")
        self.select_thr = threading.Thread(target=self.select_worker, name="selector")
        self.select_thr.daemon = True
        self.select_thr.start()

        return True

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

        sn = -1
        sc = {}
        slow = {}  # sck:cli
        fast = {}
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
                        if c.slowmo_tx or c.wizard_stage is not None:
                            slow[c.socket] = c
                        else:
                            fast[c.socket] = c

                        sc[c.socket] = c

                timeout = 0.2 if slow else 0.34 if fast else 69

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

            try:
                rxs, txs, _ = select.select(want_rx, want_tx, [], timeout)
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

            with world.mutex:
                if self.stopping:
                    break

                date = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                if date != last_date:
                    if last_date:
                        world.broadcast_message(
                            u"\033[36mday changed to \033[1m{0}".format(date), False
                        )
                    last_date = date

                for iface in ifaces:
                    for client in iface.clients:
                        if client.handshake_sz:
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
