#!/usr/bin/env python3
# coding: utf-8
from __future__ import print_function
from .__version__ import S_VERSION
from .__init__ import EP, WINDOWS, COLORS
from . import config as Config
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


class Core(object):
    def __init__(self):
        pass

    def start(self, args=None):
        if WINDOWS and COLORS:
            os.system("rem")  # best girl

        if args is None:
            args = sys.argv

        if len(args) < 3:
            print()
            print("  need argument 1:  Telnet port  (or 0 to disable)")
            print("  need argument 2:  NetCat port  (or 0 to disable)")
            print("  optional arg. 3:  Password")
            print()
            print("  example 1:")
            print("    python3 -m r0c 2323 1531 hunter2")
            print()
            print("  example 2:")
            print("    python3 -m r0c 23 531")
            print()
            return False

        for d in ["pm", "chan", "wire"]:
            try:
                os.makedirs(EP.log + d)
            except:
                pass

        print("  *  r0c {0}, py {1}".format(S_VERSION, Util.host_os()))

        self.telnet_port = int(args[1])
        self.netcat_port = int(args[2])

        print("  *  Telnet server on port " + str(self.telnet_port))
        print("  *  NetCat server on port " + str(self.netcat_port))

        if not self.read_password(args):
            return False

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

        print("  *  Starting Telnet server")
        self.telnet_server = Itelnet.TelnetServer(
            "0.0.0.0", self.telnet_port, self.world, self.netcat_port
        )

        print("  *  Starting NetCat server")
        self.netcat_server = Inetcat.NetcatServer(
            "0.0.0.0", self.netcat_port, self.world, self.telnet_port
        )

        print("  *  Loading user configs")
        self.telnet_server.load_configs()
        self.netcat_server.load_configs()

        print("  *  Starting push driver")
        self.push_thr = threading.Thread(
            target=self.push_worker,
            args=(
                self.world,
                [self.telnet_server, self.netcat_server],
            ),
            name="push",
        )
        # self.push_thr.daemon = True
        self.push_thr.start()

        print("  *  Running")
        self.select_thr = threading.Thread(target=self.select_worker, name="selector")
        self.select_thr.daemon = True
        self.select_thr.start()

        return True

    def read_password(self, args):
        self.password = Config.ADMIN_PWD

        # password as argument overrides all others
        if len(args) > 3:
            self.password = args[3]
            print("  *  Password from argument")
            return True

        # password file in home directory overrides config
        pwd_file = os.path.join(EP.app, "password.txt")
        if os.path.isfile(pwd_file):
            print("  *  Password from " + pwd_file)
            with open(pwd_file, "rb") as f:
                self.password = f.read().decode("utf-8").strip()
                return True

        # fallback to config.py
        print("  *  Password from " + os.path.join(EP.src, "config.py"))
        if self.password != u"hunter2":
            return True

        # default password is verboten
        print()
        print("\033[1;31m  change the ADMIN_PWD in the path above \033[0m")
        print("\033[1;31m  or provide your password as an argument \033[0m")
        print("\033[1;31m  or save it here: " + pwd_file + "\033[0m")
        print()
        return False

    def run(self):
        print("  *  r0c is up  ^^,")

        if not Config.BENCHMARK:
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
        self.world.dirty_flag.set()

        print("  *  saving user configs")
        self.telnet_server.save_configs()
        self.netcat_server.save_configs()

        print("  *  terminating world")
        self.world.shutdown()

        print("  *  selector cleanup")
        self.telnet_server.srv_sck.close()
        self.netcat_server.srv_sck.close()

        print("  *  r0c is down")
        return True

    def select_worker(self):
        srvs = {}
        for iface in [self.telnet_server, self.netcat_server]:
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
                for c in self.telnet_server.clients + self.netcat_server.clients:
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
            if self.telnet_server.clients or self.netcat_server.clients:
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
                        if Config.LOG_RX or Config.LOG_TX:
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
        if Config.THREADMON and not self.threadmon:
            self.threadmon = True
            Util.monitor_threads()
        else:
            self.shutdown()


def start_r0c(args):
    core = Core()
    try:
        if core.start(args):
            return core.run()
    except:
        Util.whoops()
        os._exit(1)


def main(args=None):
    mode = "normal"
    # mode = "profiler"
    # mode = 'test-ansi-annotation'
    # test_hexdump()

    if mode == "normal":
        if not start_r0c(args):
            sys.exit(1)


"""
    if mode == "profiler":
        print("  *  PROFILER ENABLED")
        statfile = "profiler-results"
        import yappi

        yappi.start()
        start_r0c(args)
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
